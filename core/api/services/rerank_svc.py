# file: rerank_svc.py
# description: 重排服务——Qwen3-Reranker 生成式打分，复用上游池 capability 路由 + 降级链 + 熔断
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-09-28
# status: active
# tags: [service],[rerank],[qwen3-reranker],[hybrid-search]
#
# 设计要点（P1 RAG 混合检索深化）：
# 1. 与 api/proxy.py 的 /v1/rerank 端点解耦：对外 API（Cohere 风格 + vk 记账）走 proxy；
#    内部检索重排（ops_rag RRF 后精排）走本服务——同进程直调，零 HTTP 自调、免 vk。
# 2. 打分语义与 proxy 同源：Qwen3-Reranker 官方 judge 三段式模板 + completions
#    logprobs 取 yes 概率（max_tokens=1, temperature=0, logprobs=20）。
# 3. 降级链 + 熔断 + 模型改写复用 upstream_registry 既有机制（与 proxy._forward 同语义）。

import logging
import math
import time
from typing import List, Optional, Tuple

import httpx

from app.services.upstream_registry import Upstream, registry

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=5.0, read=30.0)

# Qwen3-Reranker 官方 judge 三段式模板（与 api/proxy.py 保持同源，勿单独改动任一份）
_RERANK_PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements based on "
    'the Query and the Instruct provided. Note that the answer can only be "yes" or "no".'
    "<|im_end|>\n<|im_start|>user\n"
)
_RERANK_INSTRUCT = "Given a web search query, retrieve relevant passages that answer the query"
_RERANK_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

_DOC_MAX_CHARS = 1500  # 重排输入截断（防超长 prompt；检索文本 400 chunk 上游已限）


def _rerank_prompt(query: str, doc: str) -> str:
    middle = (
        f"<Instruct>{_RERANK_INSTRUCT}</Instruct>"
        f"\n<Query>{query}</Query>\n<Document>{doc}</Document>"
    )
    return _RERANK_PREFIX + middle + _RERANK_SUFFIX


def _yes_probability(choice: dict) -> float:
    """从 completions choice 的 top_logprobs 里提取 yes 概率（Qwen3-Reranker 语义）"""
    top = (choice.get("logprobs") or {}).get("top_logprobs") or []
    if not top:
        return 0.0
    for tok, lp in (top[0] or {}).items():
        if tok.strip().lower() == "yes":
            return math.exp(lp)
    return 0.0


def _chain() -> List[Upstream]:
    """capability=rerank 上游按优先级排序（降级链；registry+env 双通道合并池）"""
    return sorted(
        [u for u in registry.upstreams.values() if u.capability == "rerank"],
        key=lambda u: (u.priority, -u.weight),
    )


async def rerank_scores(
    query: str,
    documents: List[str],
    model: Optional[str] = None,
) -> Tuple[List[float], str]:
    """query 对 documents 逐条打分，返回 (scores, upstream_name)。

    - scores 与 documents 等长等序（上游截断/缺项补 0.0）；
    - 全链失败抛 RuntimeError——调用方（ops_rag）捕获后降级原序，检索不因重排失败而失败；
    - model 不指定时用上游首个注册模型（模型改写防 404）。
    """
    if not documents:
        return [], ""
    chain = _chain()
    if not chain:
        raise RuntimeError("rerank 上游池为空（capability=rerank 无注册条目）")

    prompts = [_rerank_prompt(query, d[:_DOC_MAX_CHARS]) for d in documents]
    errors: list = []
    for u in chain:
        if not registry.available(u):
            continue
        registry.acquire(u)
        started = time.time()
        # 模型改写（与 proxy._forward 同语义）：显式 model 被上游服务则保留，
        # 否则改写为该上游首个注册模型（防 404 model-not-found）
        if model and u.models and u.serves(model):
            payload_model = model
        else:
            payload_model = u.models[0] if u.models else "qwen3-reranker-0.6b"
        body = {
            "model": payload_model,
            "prompt": prompts,
            "max_tokens": 1,
            "temperature": 0,
            "logprobs": 20,
        }
        for addr in [u.base_url] + ([u.fallback_url] if u.fallback_url else []):
            url = f"{addr}/v1/completions"
            headers = {}
            if u.api_key():
                headers["Authorization"] = f"Bearer {u.api_key()}"
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                registry.release(u, (time.time() - started) * 1000, True)
                choices = resp.json().get("choices", [])
                scores = [_yes_probability(ch) for ch in choices]
                scores += [0.0] * (len(documents) - len(scores))
                return scores[: len(documents)], u.name
            except Exception as e:
                errors.append(f"{u.name}@{addr}: {e}")
                logger.warning(f"[rerank] 上游失败 {u.name}@{addr}: {e}")
        registry.release(u, (time.time() - started) * 1000, False, errors[-1] if errors else "")
    raise RuntimeError(f"[rerank] 上游降级链全部失败: {'; '.join(errors)}")
