# file: ops_rag.py
# description: 运维知识库检索服务（chroma 四库 + 零依赖 BM25 + RRF 融合 + rerank 精排，含降级链）
# author: YanYuCloudCube Team
# version: v1.2.0
# created: 2026-09-27
# status: active
# tags: [service],[rag],[ops],[bm25],[rrf],[rerank]
#
# 设计要点（评审说明）：
# 1. 出站端点全部为编译期字面量（ENDPOINTS 注册表），配置只选择键名，无任何 URL 拼接；
# 2. BM25 为零依赖实现（Okapi），索引 JSON 落盘，reindex 从 chroma 主库全量拉取重建；
# 3. 降级链：8B 嵌入离线 → 0.6b+online 库（notes 留痕）；chroma 不可达 → 返回 503 明确错误；
# 4. 评测基线（2026-09-27, golden set v2 · 40 题 Top3）：online 31% / premium 45% / main 55%；
# 5. rerank 精排（v1.1.0 P1）：候选池（≤top_k×4）经 rerank_svc 生成式打分重排；
#    失败自动降级原序（notes 留痕），检索不因重排失败而失败。

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.rerank_svc import rerank_scores

# ── 端点字面量注册表（配置选键，不拼 URL）─────────────────────
# 注：N2 服务走 tailscale IP（100.76.167.103）。原 10.100.168.1 为 N1↔N2
# 背对背直连网段（mtu9000），NAS 网关容器不可达（2026-09-28 P1 生产实测发现：
# 出站挂起 60s 超时）——网关出站唯一稳定路由为 tailscale 链。
EMB_ENDPOINTS = {
    "n2_8b": "http://100.76.167.103:8103/v1/embeddings",
    "n1_06b": "http://100.65.64.49:8100/v1/embeddings",
}
EMB_MODELS = {"n2_8b": "qwen3-embedding-8b", "n1_06b": "qwen3-embedding-0.6b"}

# 注：URL 为不可拆分的整串字面量（安全设计），超长行 noqa
CHROMA_QUERY_URLS = {
    "main": "http://100.76.167.103:8102/api/v2/tenants/default_tenant/databases/default_database/collections/89ba3e52-ad0d-42ae-a66c-1f7dbfc5e1a0/query",  # noqa: E501
    "prompts": "http://100.76.167.103:8102/api/v2/tenants/default_tenant/databases/default_database/collections/7500800b-d076-46f7-b75e-bda9cea1e949/query",  # noqa: E501
    "premium": "http://100.76.167.103:8102/api/v2/tenants/default_tenant/databases/default_database/collections/8feb7b7a-1725-4384-92bb-66e454d41c30/query",  # noqa: E501
    "online": "http://100.76.167.103:8102/api/v2/tenants/default_tenant/databases/default_database/collections/f505a0b4-f5e9-45f3-9938-a650c9566cb6/query",  # noqa: E501
}
CHROMA_GET_MAIN_URL = "http://100.76.167.103:8102/api/v2/tenants/default_tenant/databases/default_database/collections/89ba3e52-ad0d-42ae-a66c-1f7dbfc5e1a0/get"  # noqa: E501
EMB_MODELS_PROBE_URLS = {
    "n2_8b": "http://100.76.167.103:8103/v1/models",
    "n1_06b": "http://100.65.64.49:8100/v1/models",
}

# 库 → 嵌入引擎配对（8B 库必须配 8B 嵌入；online 库配 0.6b）
LIBRARY_ENGINE = {
    "main": "n2_8b",
    "prompts": "n2_8b",
    "premium": "n2_8b",
    "online": "n1_06b",
}

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+")
_RRF_K = 60  # Reciprocal Rank Fusion 常数


def _tokenize(text: str) -> List[str]:
    """轻量分词：中文单字+bigram + 英数词（bigram 消单字歧义，v1.2.0 hybrid 修复）"""
    base = [t for t in _TOKEN_RE.findall(text.lower()) if t.strip()]
    out = list(base)
    prev = None
    for t in base:
        is_cjk = len(t) == 1 and "\u4e00" <= t <= "\u9fff"
        if is_cjk and prev is not None:
            out.append(prev + t)
        prev = t if is_cjk else None
    return out


def _index_text(d: Dict[str, str]) -> List[str]:
    """BM25 索引文本 = heading 前置 + 正文（标题词面直配，v1.2.0 hybrid 修复）"""
    return _tokenize((str(d.get("heading", "")) + "\n" + str(d.get("text", "")))[:4000])


class BM25Okapi:
    """零依赖 Okapi BM25（语料全量内存索引，主库 441 块量级毫秒级检索）"""

    def __init__(self, corpus_tokens: List[List[str]]):
        self.k1, self.b = 1.5, 0.75
        self.N = len(corpus_tokens)
        self.doclens = [len(t) for t in corpus_tokens]
        self.avgdl = sum(self.doclens) / max(self.N, 1)
        self.doc_tf: List[Dict[str, int]] = []
        df: Dict[str, int] = {}
        for toks in corpus_tokens:
            tf: Dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self.doc_tf.append(tf)
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self.idf = {
            t: math.log(1 + (self.N - c + 0.5) / (c + 0.5)) for t, c in df.items()
        }

    def score(self, query: str, index: int) -> float:
        s = 0.0
        dl = self.doclens[index]
        tf = self.doc_tf[index]
        for t in _tokenize(query):
            c = tf.get(t, 0)
            if c and t in self.idf:
                s += (
                    self.idf[t]
                    * c
                    * (self.k1 + 1)
                    / (c + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                )
        return s

    def search(self, query: str, top_n: int = 20) -> List[int]:
        scored = [(i, self.score(query, i)) for i in range(self.N)]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [i for i, _ in scored[:top_n]]


class OpsRAGService:
    """运维知识检索：chroma 向量 + BM25 词面，RRF 融合，8B→0.6b 降级"""

    def __init__(self) -> None:
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_docs: List[Dict[str, str]] = []
        self._bm25_loaded_at: float = 0.0

    # ── 嵌入 ────────────────────────────────────────────────
    async def _probe(self, engine_key: str, timeout: float = 2.5) -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(EMB_MODELS_PROBE_URLS[engine_key])
            return r.status_code == 200
        except Exception:
            return False

    async def embed(self, query: str, engine_key: str) -> List[float]:
        payload = {"model": EMB_MODELS[engine_key], "input": [query]}
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(EMB_ENDPOINTS[engine_key], json=payload)
            r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        return data[0]["embedding"]

    # ── chroma 向量检索 ─────────────────────────────────────
    async def chroma_query(
        self, library: str, vec: List[float], k: int
    ) -> List[Dict[str, Any]]:
        payload = {
            "query_embeddings": [vec],
            "n_results": min(k * 4, 40),
            "include": ["metadatas", "documents", "distances"],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(CHROMA_QUERY_URLS[library], json=payload)
            r.raise_for_status()
        body = r.json()
        hits = []
        for m, d, dist in zip(
            body["metadatas"][0], body["documents"][0], body["distances"][0]
        ):
            hits.append(
                {
                    "source": m.get("source", ""),
                    "heading": m.get("heading", ""),
                    "text": d,
                    "distance": dist,
                }
            )
        return hits

    # ── BM25 索引管理 ───────────────────────────────────────
    def _index_path(self) -> Path:
        return Path(settings.ops_rag_bm25_index_path)

    def load_bm25(self, force: bool = False) -> bool:
        """加载磁盘索引（存在则毫秒级）；失败返回 False 不致命（仅退化为纯向量）"""
        p = self._index_path()
        if not p.is_file():
            return False
        if (
            self._bm25 is not None
            and not force
            and time.time() - self._bm25_loaded_at < 3600
        ):
            return True
        try:
            idx = json.loads(p.read_text(encoding="utf-8"))
            self._bm25_docs = idx["docs"]
            self._bm25 = BM25Okapi([_index_text(d) for d in idx["docs"]])
            self._bm25_loaded_at = time.time()
            return True
        except Exception:
            self._bm25 = None
            return False

    async def reindex_bm25(self) -> Dict[str, Any]:
        """从 chroma 主库全量拉取重建 BM25 索引（管理端点调用）"""
        payload = {"limit": 5000, "include": ["documents", "metadatas"]}
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(CHROMA_GET_MAIN_URL, json=payload)
            r.raise_for_status()
        body = r.json()
        docs = [
            {
                "id": str(i),
                "source": m.get("source", ""),
                "heading": m.get("heading", ""),
                "text": d,
            }
            for i, (m, d) in enumerate(
                zip(body.get("metadatas", []), body.get("documents", []))
            )
        ]
        self._bm25_docs = docs
        self._bm25 = BM25Okapi([_index_text(d) for d in docs])
        self._bm25_loaded_at = time.time()
        p = self._index_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {
                    "built_at": time.time(),
                    "count": len(docs),
                    "doc_toks": [_index_text(d) for d in docs],
                    "docs": docs,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"count": len(docs), "path": str(p)}

    # ── RRF 融合 ────────────────────────────────────────────
    @staticmethod
    def rrf_fuse(
        vec_hits: List[Dict[str, Any]], bm25_hits: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion：score = Σ 1/(k+rank)，双通道各自排名后融合。

        v1.2.0 修复：同 key（source::heading）在单通道内多 chunk 重复出现时只计
        首现 rank——否则同标题 N 个 chunk 占 N 个 rank 位逐位累加，形成灌分
        霸榜（v4 评测归因：「📂 完整功能模块组件文件树架构」19 chunks 霸榜
        吞掉 5 题，hybrid 61% vs vec 65% 负收益的主因）。
        """
        scores: Dict[str, float] = {}
        pooled: Dict[str, Dict[str, Any]] = {}
        for hits in (vec_hits, bm25_hits):
            counted: set = set()
            for rank, h in enumerate(hits):
                key = f"{h['source']}::{h['heading']}"
                if key in counted:
                    continue
                counted.add(key)
                scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
                if key not in pooled:
                    pooled[key] = dict(h)
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        out = []
        for key, s in ranked:
            h = pooled[key]
            h["score"] = round(s, 5)
            out.append(h)
        return out

    # ── 主入口 ──────────────────────────────────────────────
    async def search(
        self,
        query: str,
        top_k: int = 5,
        library: str = "main",
        hybrid: bool = False,
        rerank: bool = False,
    ) -> Dict[str, Any]:
        notes: List[str] = []
        if library not in CHROMA_QUERY_URLS:
            library = "main"
        want_engine = LIBRARY_ENGINE[library]
        engine_key = want_engine
        if want_engine == "n2_8b" and not await self._probe("n2_8b"):
            engine_key = "n1_06b"
            library = "online"
            notes.append("8B 嵌入离线, 降级 online(0.6b)")

        vec = await self.embed(query, engine_key)
        hits = await self.chroma_query(library, vec, top_k)

        fused = False
        if hybrid and library == "main" and self.load_bm25():
            bm25 = self._bm25
            if bm25 is not None:
                bm25_hits = []
                for i in bm25.search(query, top_k * 4):
                    d = self._bm25_docs[i]
                    bm25_hits.append(
                        {
                            "source": d["source"],
                            "heading": d["heading"],
                            "text": d["text"],
                            "distance": None,
                        }
                    )
                hits = self.rrf_fuse(hits, bm25_hits, top_k)
                fused = True
        else:
            if hybrid and library != "main":
                notes.append("hybrid 仅支持 main 库")

        # rerank 精排（v1.1.0）：候选池整体打分重排，失败降级原序（可用性优先）
        reranked = False
        if rerank and hits:
            try:
                scores, upstream = await rerank_scores(query, [h["text"] for h in hits])
                for i, s in enumerate(scores):
                    hits[i]["_rerank_score"] = round(s, 4)
                order = sorted(range(len(hits)), key=lambda i: -scores[i])
                hits = [hits[i] for i in order]
                reranked = True
                notes.append(f"rerank by {upstream}")
            except Exception as e:
                notes.append(f"rerank 降级原序: {e}")

        def _score(h: Dict[str, Any]) -> float:
            # 分数语义：rerank 分（最终相关性）> RRF 融合分 > 向量相似度
            if reranked:
                return float(h.get("_rerank_score", 0.0))
            if fused:
                return float(h.get("score", 0.0))
            return round(1.0 - h.get("distance", 0.0), 4)

        results = [
            {
                "source": h["source"],
                "heading": h["heading"],
                "score": _score(h),
                "snippet": h["text"][:400],
            }
            for h in hits[:top_k]
        ]
        return {
            "query": query,
            "library": library,
            "embedded_by": EMB_MODELS[engine_key],
            "hybrid": fused,
            "reranked": reranked,
            "notes": notes,
            "results": results,
        }


ops_rag_service = OpsRAGService()
