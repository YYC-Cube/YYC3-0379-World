#!/usr/bin/env python3
"""
@file test_ops_rag.py
@description /v1/rag/ops 运维知识检索测试——BM25/RRF 纯数学+降级链+rerank 精排+契约
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.1.0
@created: 2026-09-27
@tags [test,rag,ops,bm25,rrf,rerank]

零网络设计：embed/chroma/_probe/rerank_scores 全部以 monkeypatch 桩替；
BM25 与 RRF 为纯函数直测。API 层用例标 integration（TestClient 全链路）。
（v1.0.0 于 NAS 生产验证目录孕育，2026-09-28 P1 主线收编入库并扩 rerank 用例）
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

os.environ.setdefault("API_KEYS", "test-key-1")

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.ops_rag import (BM25Okapi, OpsRAGService,  # noqa: E402
                                  _tokenize)

client = TestClient(app)

_HEADERS = {"X-API-Key": os.environ.get("API_KEYS", "test-key-1")}

_FAKE_VEC = [0.1] * 8

_FAKE_HITS = [
    {
        "source": "yyc3-101-DEVICE.md",
        "heading": "旗舰 TP=2 断链",
        "text": "CDI 规格陈旧需再生成",
        "distance": 0.2,
    },
    {
        "source": "README.md",
        "heading": "导航中心",
        "text": "fleet-scan 巡检",
        "distance": 0.5,
    },
    {
        "source": "RAG-管道手册.md",
        "heading": "双库双轨",
        "text": "premium 与 online",
        "distance": 0.7,
    },
]


# ── 纯数学：BM25 ───────────────────────────────────────────
def test_bm25_relevance_ranking():
    docs = [
        ["cdi", "规格", "陈旧", "再生成"],
        ["fleet", "scan", "巡检"],
        ["yanyucloud", "cube"],
    ]
    bm = BM25Okapi(docs)
    assert bm.score("CDI 规格陈旧", 0) > bm.score("CDI 规格陈旧", 1)
    assert bm.search("YanYuCloud", 1) == [2]


def test_tokenize_mixed_cn_en():
    toks = _tokenize("GLM 点火 TP=2")
    assert "GLM".lower() in toks and "点" in toks


# ── 纯数学：RRF 融合 ────────────────────────────────────────
def test_rrf_fuse_cross_channel_promotion():
    vec_hits = [
        {"source": f"a{i}.md", "heading": "h", "text": "t", "distance": 0.1}
        for i in range(5)
    ]
    # bm25 通道的第一名在向量通道垫底 → RRF 应把它提到前列
    bm25_hits = [vec_hits[4]] + [
        {"source": f"b{i}.md", "heading": "h", "text": "t", "distance": None}
        for i in range(4)
    ]
    fused = OpsRAGService.rrf_fuse(vec_hits, bm25_hits, top_k=3)
    top_sources = [h["source"] for h in fused]
    assert "a4.md" in top_sources, "双通道都命中的文档应被 RRF 提权"


def test_rrf_fuse_rank_monotonic():
    hits = [
        {"source": f"x{i}.md", "heading": "h", "text": "t", "distance": 0.1}
        for i in range(10)
    ]
    fused = OpsRAGService.rrf_fuse(hits, hits, top_k=5)
    scores = [h["score"] for h in fused]
    assert scores == sorted(scores, reverse=True)
    assert len(fused) == 5


# ── 服务层：降级链与混合开关（桩替网络）─────────────────────
def _patch_service(monkeypatch, probe_8b: bool):
    svc = OpsRAGService()

    async def fake_embed(query, engine_key):
        return _FAKE_VEC

    async def fake_chroma(library, vec, k):
        return _FAKE_HITS[:k]

    async def fake_probe(engine_key, timeout=2.5):
        return probe_8b if engine_key == "n2_8b" else True

    monkeypatch.setattr(svc, "embed", fake_embed)
    monkeypatch.setattr(svc, "chroma_query", fake_chroma)
    monkeypatch.setattr(svc, "_probe", fake_probe)
    return svc


def test_degrade_8b_offline_to_online(monkeypatch):
    svc = _patch_service(monkeypatch, probe_8b=False)

    out = asyncio.run(
        svc.search("旗舰断链怎么修", top_k=3, library="main", hybrid=False)
    )
    assert out["library"] == "online"
    assert out["embedded_by"] == "qwen3-embedding-0.6b"
    assert any("降级" in n for n in out["notes"])


def test_hybrid_requires_main_library(monkeypatch):
    svc = _patch_service(monkeypatch, probe_8b=True)

    out = asyncio.run(svc.search("任意", top_k=3, library="premium", hybrid=True))
    assert out["hybrid"] is False
    assert any("main" in n for n in out["notes"])


def test_vector_only_contract(monkeypatch):
    svc = _patch_service(monkeypatch, probe_8b=True)

    out = asyncio.run(svc.search("CDI", top_k=2, library="main", hybrid=False))
    assert out["library"] == "main"
    assert out["embedded_by"] == "qwen3-embedding-8b"
    assert len(out["results"]) == 2
    first = out["results"][0]
    assert {"source", "heading", "score", "snippet"} <= set(first.keys())
    # 向量序 score = 1 - distance
    assert abs(first["score"] - 0.8) < 1e-6


# ── 服务层：rerank 精排（v1.1.0，桩替 rerank_scores）────────
def test_rerank_reorders_candidates(monkeypatch):
    svc = _patch_service(monkeypatch, probe_8b=True)

    async def fake_rerank(query, docs):
        # 逆序打分：最后一个文档最相关 → 重排后顺序应翻转
        return [0.1, 0.5, 0.9], "rerank-stub"

    import app.services.ops_rag as m

    monkeypatch.setattr(m, "rerank_scores", fake_rerank)

    out = asyncio.run(svc.search("CDI", top_k=3, library="main", rerank=True))
    assert out["reranked"] is True
    assert any("rerank by rerank-stub" in n for n in out["notes"])
    # 原 distance 序：0.2/0.5/0.7 → rerank 逆序后最后一条（distance=0.7）应居首
    assert out["results"][0]["source"] == "RAG-管道手册.md"
    # 分数语义：rerank 分回写为最终 score
    assert abs(out["results"][0]["score"] - 0.9) < 1e-6


def test_rerank_failure_degrades_original_order(monkeypatch):
    svc = _patch_service(monkeypatch, probe_8b=True)

    async def fake_rerank(query, docs):
        raise RuntimeError("上游降级链全部失败")

    import app.services.ops_rag as m

    monkeypatch.setattr(m, "rerank_scores", fake_rerank)

    out = asyncio.run(svc.search("CDI", top_k=3, library="main", rerank=True))
    assert out["reranked"] is False
    assert any("rerank 降级原序" in n for n in out["notes"])
    # 原序保留（向量 distance 升序）
    assert out["results"][0]["source"] == "yyc3-101-DEVICE.md"
    assert abs(out["results"][0]["score"] - 0.8) < 1e-6


def test_rerank_off_by_default(monkeypatch):
    svc = _patch_service(monkeypatch, probe_8b=True)

    out = asyncio.run(svc.search("CDI", top_k=2, library="main"))
    assert out["reranked"] is False
    assert out["notes"] == []


# ── API 层：路由契约（服务层整体桩替）───────────────────────
@pytest.mark.integration
def test_ops_route_contract(monkeypatch):
    async def fake_search(self, query, top_k, library, hybrid, rerank=False):
        return {
            "query": query,
            "library": library,
            "embedded_by": "qwen3-embedding-8b",
            "hybrid": False,
            "reranked": rerank,
            "notes": [],
            "results": [],
        }

    monkeypatch.setattr(OpsRAGService, "search", fake_search)
    r = client.post("/v1/rag/ops", json={"query": "测试", "top_k": 3}, headers=_HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"] == "测试"
    assert "embedded_by" in body and "notes" in body and "results" in body


@pytest.mark.integration
def test_ops_route_rejects_empty_query():
    r = client.post("/v1/rag/ops", json={"query": ""}, headers=_HEADERS)
    assert r.status_code == 422, "空查询应在模型验证层拦截（min_length=1）"


@pytest.mark.integration
def test_ops_route_rerank_param_passthrough(monkeypatch):
    seen = {}

    async def fake_search(self, query, top_k, library, hybrid, rerank=False):
        seen["rerank"] = rerank
        return {
            "query": query,
            "library": library,
            "embedded_by": "qwen3-embedding-8b",
            "hybrid": False,
            "reranked": rerank,
            "notes": [],
            "results": [],
        }

    monkeypatch.setattr(OpsRAGService, "search", fake_search)
    r = client.post(
        "/v1/rag/ops",
        json={"query": "精排测试", "rerank": True},
        headers=_HEADERS,
    )
    assert r.status_code == 200, r.text
    assert seen["rerank"] is True
    assert r.json()["reranked"] is True
