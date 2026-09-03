# file: proxy.py
# description: 能力代理端点 - embeddings/rerank/asr/ocr，复用上游池 capability 路由
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-09-03
# status: active
# tags: [api],[proxy],[embeddings],[rerank],[asr],[ocr]

"""
@file: app/api/proxy.py
@description: 非 chat 能力的统一代理端点。上游池按 capability（embedding/rerank/asr/ocr）
             分层选择 + 熔断降级，与 chat 共用 OPENAI_COMPATIBLE_UPSTREAMS 配置与
             X-YYC3-Upstream / X-YYC3-Degraded 响应头契约。

             路径约定（上游为 vLLM/vLLM-兼容服务）：
             - embedding → {base}/v1/embeddings（OpenAI 格式透传）
             - reranker  → {base}/v1/score（vLLM --task score，Jina 格式；
                           本端点对外暴露 Cohere 风格 /v1/rerank 并做双向转换）
             - asr       → {base}/v1/audio/transcriptions（multipart 透传）
             - ocr       → {base}/v1/ocr（multipart 透传）
@author: YanYuCloudCube Team <admin@0379.email>
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from app.errors.handler import error_handler
from app.services.upstream_registry import Upstream, registry
from app.utils import metrics_manager
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_TIMEOUT = httpx.Timeout(120.0, connect=10.0, read=120.0)

# capability → 上游请求路径
# rerank 走生成式打分（Qwen3-Reranker 官方用法）：指令模板 + completions logprobs 取 yes 概率
_CAP_PATH = {
    "embedding": "/v1/embeddings",
    "rerank": "/v1/completions",
    "asr": "/v1/audio/transcriptions",
    "ocr": "/v1/ocr",
}

# Qwen3-Reranker 官方 judge 三段式模板（生成式打分：取 yes token 概率）
_RERANK_PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements based on "
    'the Query and the Instruct provided. Note that the answer can only be "yes" or "no".'
    "<|im_end|>\n<|im_start|>user\n"
)
_RERANK_INSTRUCT = "Given a web search query, retrieve relevant passages that answer the query"
_RERANK_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


def _rerank_prompt(query: str, doc: str) -> str:
    middle = (
        f"<Instruct>{_RERANK_INSTRUCT}</Instruct>"
        f"\n<Query>{query}</Query>\n<Document>{doc}</Document>"
    )
    return _RERANK_PREFIX + middle + _RERANK_SUFFIX


class EmbeddingRequest(BaseModel):
    """OpenAI 兼容 embeddings 请求"""

    model: str
    input: Any  # str | List[str] | List[int tokens]
    dimensions: Optional[int] = None
    user: Optional[str] = None


class RerankRequest(BaseModel):
    """Cohere/Jina 风格 rerank 请求（对外契约）"""

    model: str
    query: str
    documents: List[str]
    top_n: Optional[int] = None
    user: Optional[str] = None


# ── 通用转发（降级链 + 熔断上报 + X 头） ────────────────────


def _chain(capability: str) -> List[Upstream]:
    """同 capability 上游按优先级排序（作为降级链）"""
    return sorted(
        [u for u in registry.upstreams.values() if u.capability == capability],
        key=lambda u: (u.priority, -u.weight),
    )


def _addresses(u: Upstream) -> List[str]:
    return [u.base_url] + ([u.fallback_url] if u.fallback_url else [])


async def _forward(
    capability: str,
    *,
    json_body: Optional[Dict] = None,
    data: Optional[Dict] = None,
    files: Optional[Dict] = None,
    headers_extra: Optional[Dict] = None,
):
    """
    按 capability 降级链转发；返回 (response_dict, served_upstream, degraded_from)。
    所有上游失败时抛 RuntimeError（由调用方转 502）。
    """
    errors: list = []
    degraded_from: list = []
    for u in _chain(capability):
        if not registry.available(u):
            continue
        registry.acquire(u)
        started = time.time()
        for addr in _addresses(u):
            url = f"{addr}{_CAP_PATH[capability]}"
            headers = {}
            if u.api_key():
                headers["Authorization"] = f"Bearer {u.api_key()}"
            if headers_extra:
                headers.update(headers_extra)
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.post(
                        url, json=json_body, data=data, files=files, headers=headers
                    )
                resp.raise_for_status()
                registry.release(u, (time.time() - started) * 1000, True)
                return resp.json(), u, degraded_from
            except Exception as e:
                errors.append(f"{u.name}@{addr}: {e}")
                logger.warning(f"[{capability}] 上游失败 {u.name}@{addr}: {e}")
        degraded_from.append(u.name)
        registry.release(u, (time.time() - started) * 1000, False, errors[-1] if errors else "")
    raise RuntimeError(f"[{capability}] 上游降级链全部失败: {'; '.join(errors)}")


def _json_or_502(payload: Dict, upstream: Upstream, degraded: List[str], status_hint: int = 200):
    headers = {"X-YYC3-Upstream": upstream.name}
    if degraded:
        headers["X-YYC3-Degraded"] = ",".join(degraded)
    return JSONResponse(content=payload, status_code=status_hint, headers=headers)


def _yes_probability(choice: Dict) -> float:
    """从 completions choice 的 top_logprobs 里提取 yes 概率（Qwen3-Reranker 语义）"""
    import math

    top = (choice.get("logprobs") or {}).get("top_logprobs") or []
    if not top:
        return 0.0
    for tok, lp in (top[0] or {}).items():
        if tok.strip().lower() == "yes":
            return math.exp(lp)
    return 0.0


# ── 1) POST /v1/embeddings ─────────────────────────────────


@router.post("/v1/embeddings")
async def embeddings(req: EmbeddingRequest):
    """向量嵌入（OpenAI 兼容；上游池 capability=embedding）"""
    try:
        body = {"model": req.model, "input": req.input}
        if req.dimensions:
            body["dimensions"] = req.dimensions
        result, u, degraded = await _forward("embedding", json_body=body)
        metrics_manager.record_model_usage(req.model, f"embedding:{u.name}")
        return _json_or_502(result, u, degraded)
    except Exception as e:
        error_response = await error_handler.handle(
            e, context={"model": req.model, "capability": "embedding", "operation": "proxy"}
        )
        raise HTTPException(status_code=error_response["status_code"], detail=error_response)


# ── 2) POST /v1/rerank ─────────────────────────────────────


@router.post("/v1/rerank")
async def rerank(req: RerankRequest):
    """重排序（Cohere 风格对外；上游 Qwen3-Reranker 生成式打分）"""
    try:
        # Qwen3-Reranker 生成式打分：批量 prompt → completions(max_tokens=1, logprobs)
        prompts = [_rerank_prompt(req.query, doc) for doc in req.documents]
        score_body = {
            "model": req.model,
            "prompt": prompts,
            "max_tokens": 1,
            "temperature": 0,
            "logprobs": 20,
        }
        result, u, degraded = await _forward("rerank", json_body=score_body)
        choices = result.get("choices", [])
        items = []
        for i, ch in enumerate(choices):
            score = _yes_probability(ch)
            items.append({"index": i, "relevance_score": score})
        items.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_n = req.top_n or len(items)
        payload = {
            "model": req.model,
            "results": items[:top_n],
            "usage": result.get("usage", {}),
        }
        metrics_manager.record_model_usage(req.model, f"rerank:{u.name}")
        return _json_or_502(payload, u, degraded)
    except Exception as e:
        error_response = await error_handler.handle(
            e, context={"model": req.model, "capability": "rerank", "operation": "proxy"}
        )
        raise HTTPException(status_code=error_response["status_code"], detail=error_response)


# ── 3) POST /v1/audio/transcriptions ───────────────────────


@router.post("/v1/audio/transcriptions")
async def transcriptions(file: UploadFile = File(...), model: str = Form(...)):
    """语音转写（Whisper 风格 multipart；上游池 capability=asr）"""
    try:
        content = await file.read()
        files = {"file": (file.filename, content, file.content_type or "application/octet-stream")}
        data = {"model": model}
        result, u, degraded = await _forward("asr", data=data, files=files)
        metrics_manager.record_model_usage(model, f"asr:{u.name}")
        return _json_or_502(result, u, degraded)
    except Exception as e:
        error_response = await error_handler.handle(
            e, context={"model": model, "capability": "asr", "operation": "proxy"}
        )
        raise HTTPException(status_code=error_response["status_code"], detail=error_response)


# ── 4) POST /v1/ocr ────────────────────────────────────────


@router.post("/v1/ocr")
async def ocr(file: UploadFile = File(...), model: Optional[str] = Form(None)):
    """图文识别（multipart；上游池 capability=ocr）"""
    try:
        content = await file.read()
        files = {"file": (file.filename, content, file.content_type or "application/octet-stream")}
        data = {}
        if model:
            data["model"] = model
        result, u, degraded = await _forward("ocr", data=data, files=files)
        metrics_manager.record_model_usage(model or "ocr", f"ocr:{u.name}")
        return _json_or_502(result, u, degraded)
    except Exception as e:
        error_response = await error_handler.handle(
            e, context={"model": model or "ocr", "capability": "ocr", "operation": "proxy"}
        )
        raise HTTPException(status_code=error_response["status_code"], detail=error_response)
