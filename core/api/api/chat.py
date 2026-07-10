# file: chat.py
# description: 聊天 API 路由模块 - 支持同步和SSE流式响应
# author: YanYuCloudCube Team
# version: v2.0.0
# created: 2026-03-21
# updated: 2026-07-10
# status: active
# tags: [api],[chat],[route],[streaming],[sse]

"""
@file: app/api/chat.py
@description: Chat Completions API 路由，提供 OpenAI 兼容的统一接口（含SSE流式）
@author: YanYuCloudCube Team <admin@0379.email>
@version: v2.0.0
@created: 2026-03-13
@updated: 2026-07-10
@status: stable
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
@tags: api,python,chat,critical,public
"""

import hashlib
import json
import logging
import time
from typing import AsyncGenerator

from app.api.schemas import CompletionRequest
from app.db import log_usage
from app.errors.handler import error_handler, with_retry
from app.services import deepseek, ollama, zhipu
from app.services import openai as openai_service
from app.utils import (
    cache_manager,
    concurrency_limiter,
    content_filter,
    metrics_manager,
)
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _cache_key(req: CompletionRequest) -> str:
    payload = json.dumps(req.dict(), sort_keys=True).encode()
    return "llm_cache:" + hashlib.sha256(payload).hexdigest()


def _select_backend(model_name: str):
    """选择模型后端，返回 (backend_module, backend_name, backend_type)"""
    if model_name.startswith("zhipu:") or model_name in [
        "glm-4-flash",
        "glm-4-plus",
        "glm-4",
    ]:
        backend = zhipu
        backend_name = model_name.split(":", 1)[1] if ":" in model_name else model_name
        backend_type = "zhipu"
    elif model_name.startswith("deepseek:") or model_name in [
        "deepseek-chat",
        "deepseek-coder",
    ]:
        backend = deepseek
        backend_name = model_name.split(":", 1)[1] if ":" in model_name else model_name
        backend_type = "deepseek"
    elif model_name.startswith("openai:") or model_name in [
        "gpt-4",
        "gpt-4o",
        "gpt-3.5-turbo",
    ]:
        backend = openai_service
        backend_name = model_name.split(":", 1)[1] if ":" in model_name else model_name
        backend_type = "openai"
    elif model_name.startswith("ollama:") or model_name.startswith("local:"):
        backend = ollama
        backend_type = "ollama"
        backend_name = model_name.split(":", 1)[1] if ":" in model_name else model_name
    else:
        # 默认尝试Ollama本地模型
        backend = ollama
        backend_type = "ollama"
        backend_name = model_name
    return backend, backend_name, backend_type


def _has_stream_method(backend) -> bool:
    """检查后端是否支持流式输出"""
    return hasattr(backend, "chat_completion_stream")


@router.post("/chat/completions")
async def chat_completion(req: CompletionRequest, request: Request):
    """
    聊天完成接口

    - stream=false: 返回完整JSON响应
    - stream=true: 返回SSE流式响应（data: {...}\\n\\n 格式）
    """
    start_time = time.time()
    metrics_manager.increment_active_requests()

    # ── 选择后端 ──────────────────────────────────────────
    try:
        backend, backend_name, backend_type = _select_backend(req.model)
    except Exception as e:
        error_response = await error_handler.handle(
            e, context={"model": req.model, "operation": "backend_selection"}
        )
        metrics_manager.decrement_active_requests()
        raise HTTPException(
            status_code=error_response["status_code"], detail=error_response
        )

    # ── 流式分支 ──────────────────────────────────────────
    if req.stream:
        return await _handle_stream(
            req, backend, backend_name, backend_type, start_time
        )

    # ── 同步分支（带缓存） ────────────────────────────────
    return await _handle_sync(req, backend, backend_name, backend_type, start_time)


async def _handle_sync(req, backend, backend_name, backend_type, start_time):
    """处理同步请求（带缓存）"""
    try:
        cache_key = _cache_key(req)
        cached = await cache_manager.get(cache_key)
        if cached:
            metrics_manager.record_cache_hit(req.model)
            metrics_manager.record_request("POST", "/chat/completions", 200, "cache")
            metrics_manager.record_response_time(
                "POST", "/chat/completions", time.time() - start_time, "cache"
            )
            metrics_manager.decrement_active_requests()
            return cached

        metrics_manager.record_cache_miss(req.model)
    except Exception as e:
        error_response = await error_handler.handle(
            e, context={"operation": "cache_check"}
        )
        metrics_manager.decrement_active_requests()
        raise HTTPException(
            status_code=error_response["status_code"], detail=error_response
        )

    async with concurrency_limiter.limit():
        backend_start_time = time.time()
        try:
            response = await with_retry(max_retries=2, delay=1.0)(
                backend.chat_completion
            )(
                model=backend_name,
                messages=[m.dict() for m in req.messages],
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                top_p=req.top_p,
                stream=False,
            )
            metrics_manager.record_backend_latency(
                backend_type, req.model, time.time() - backend_start_time
            )
        except Exception as e:
            # Ollama失败时回退到智谱
            if backend is ollama:
                try:
                    response = await with_retry(max_retries=2, delay=1.0)(
                        zhipu.chat_completion
                    )(
                        model="glm-4-flash",
                        messages=[m.dict() for m in req.messages],
                        max_tokens=req.max_tokens,
                        temperature=req.temperature,
                        top_p=req.top_p,
                        stream=False,
                    )
                    backend_type = "zhipu"
                except Exception as ee:
                    error_response = await error_handler.handle(
                        ee,
                        context={
                            "model": req.model,
                            "backend": backend_type,
                            "fallback": "zhipu",
                            "operation": "fallback_request",
                        },
                    )
                    raise HTTPException(
                        status_code=error_response["status_code"], detail=error_response
                    )
            else:
                error_response = await error_handler.handle(
                    e,
                    context={
                        "model": req.model,
                        "backend": backend_type,
                        "operation": "backend_request",
                    },
                )
                raise HTTPException(
                    status_code=error_response["status_code"], detail=error_response
                )

        # 缓存 + 用量记录
        await cache_manager.set(
            cache_key,
            response,
            ttl=300,
            tags=[f"model:{req.model}"],
        )

        usage = response.get("usage", {})
        await log_usage(
            model=req.model,
            backend_type=backend_type,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            user_id=req.user_id,
        )

        metrics_manager.record_model_usage(req.model, backend_type)
        metrics_manager.record_token_usage(
            req.model, backend_type, "prompt", usage.get("prompt_tokens", 0)
        )
        metrics_manager.record_token_usage(
            req.model, backend_type, "completion", usage.get("completion_tokens", 0)
        )

        filtered_response, is_blocked = content_filter.filter_response(response)
        if is_blocked:
            logger.warning(
                f"Response blocked for model: {req.model}, user: {req.user_id}"
            )

        metrics_manager.record_request("POST", "/chat/completions", 200, backend_type)
        metrics_manager.record_response_time(
            "POST", "/chat/completions", time.time() - start_time, backend_type
        )
        metrics_manager.decrement_active_requests()

        return filtered_response


async def _handle_stream(req, backend, backend_name, backend_type, start_time):
    """
    处理流式请求，返回SSE StreamingResponse

    所有Provider的 chat_completion_stream() 都产出统一的chunk格式，
    这里统一包装为 SSE "data: {json}\\n\\n" 格式。
    """
    # 流式请求不查缓存
    metrics_manager.record_cache_miss(req.model)

    if not _has_stream_method(backend):
        # 后端不支持流式，降级为同步后包装
        logger.warning(
            f"Backend {backend_type} has no stream method, falling back to sync"
        )

        async def _fallback_stream():
            response = await backend.chat_completion(
                model=backend_name,
                messages=[m.dict() for m in req.messages],
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                top_p=req.top_p,
                stream=False,
            )
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            yield {
                "id": response.get("id", ""),
                "object": "chat.completion.chunk",
                "created": response.get("created", int(time.time())),
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": content},
                        "finish_reason": None,
                    }
                ],
            }
            yield {
                "id": response.get("id", ""),
                "object": "chat.completion.chunk",
                "created": response.get("created", int(time.time())),
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }

        stream_gen = _fallback_stream()
    else:
        stream_gen = backend.chat_completion_stream(
            model=backend_name,
            messages=[m.dict() for m in req.messages],
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
        )

    async def sse_wrapper(gen) -> AsyncGenerator[str, None]:
        """将统一的chunk dict包装为SSE格式"""
        total_tokens = 0
        try:
            async for chunk in gen:
                # 估算token（粗略：按字符数/4）
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    total_tokens += len(delta["content"]) // 4

                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "stream_error",
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"
        finally:
            # 发送结束标记
            yield "data: [DONE]\n\n"

            # 记录用量
            try:
                await log_usage(
                    model=req.model,
                    backend_type=backend_type,
                    prompt_tokens=0,
                    completion_tokens=total_tokens,
                    total_tokens=total_tokens,
                    user_id=req.user_id,
                )
                metrics_manager.record_model_usage(req.model, backend_type)
                metrics_manager.record_token_usage(
                    req.model, backend_type, "completion", total_tokens
                )
            except Exception:
                pass

            metrics_manager.record_request(
                "POST", "/chat/completions", 200, backend_type
            )
            metrics_manager.record_response_time(
                "POST", "/chat/completions", time.time() - start_time, backend_type
            )
            metrics_manager.decrement_active_requests()

    return StreamingResponse(
        sse_wrapper(stream_gen),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
