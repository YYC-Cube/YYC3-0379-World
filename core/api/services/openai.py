# file: openai.py
# description: OpenAI API 服务模块 - 支持同步和流式响应
# author: YanYuCloudCube Team
# version: v2.0.0
# created: 2026-03-21
# updated: 2026-07-10
# status: active
# tags: [service],[openai],[ai],[streaming]

"""
@file: app/services/openai.py
@description: OpenAI API 服务模块，提供同步和流式调用接口
@author: YanYuCloudCube Team <admin@0379.email>
@version: v2.0.0
@created: 2026-03-13
@updated: 2026-07-10
@status: stable
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
@tags: services,python,openai,api,public
"""

import httpx
import json
import time
from typing import List, Dict, Any, AsyncGenerator
from app.config import settings
from app.utils import http_client

_OPENAI_BASE = "https://api.openai.com/v1"
_OPENAI_KEY = settings.openai_api_key


async def chat_completion(
    model: str,
    messages: List[Dict],
    max_tokens: int | None = None,
    temperature: float = 0.7,
    top_p: float | None = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    调用 OpenAI API 并返回 OpenAI 兼容的 JSON 格式

    注意：stream参数仅为接口兼容，流式请求请使用 chat_completion_stream()
    """
    headers = {
        "Authorization": f"Bearer {_OPENAI_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,  # 同步接口始终使用非流式
    }

    if max_tokens:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p:
        payload["top_p"] = top_p

    response = await http_client.post(
        f"{_OPENAI_BASE}/chat/completions",
        headers=headers,
        json=payload
    )
    response.raise_for_status()
    return response.json()


async def chat_completion_stream(
    model: str,
    messages: List[Dict],
    max_tokens: int | None = None,
    temperature: float = 0.7,
    top_p: float | None = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    OpenAI流式输出 - 统一SSE格式

    Yields:
        dict: 统一格式的流式响应块 (chat.completion.chunk)
    """
    headers = {
        "Authorization": f"Bearer {_OPENAI_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    if max_tokens:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p:
        payload["top_p"] = top_p

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{_OPENAI_BASE}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line and line.startswith("data: "):
                        data_str = line[6:]

                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])

                            for choice in choices:
                                delta = choice.get("delta", {})

                                yield {
                                    "id": chunk.get("id", ""),
                                    "object": "chat.completion.chunk",
                                    "created": chunk.get("created", 0),
                                    "model": model,
                                    "choices": [{
                                        "index": choice.get("index", 0),
                                        "delta": delta,
                                        "finish_reason": choice.get("finish_reason")
                                    }]
                                }
                        except json.JSONDecodeError:
                            continue

    except httpx.HTTPStatusError as e:
        from app.utils.logger import logger
        logger.error(f"OpenAI流式API错误: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        from app.utils.logger import logger
        logger.error(f"OpenAI流式输出错误: {str(e)}")
        from app.errors import APIError
        raise APIError(message="OpenAI流式服务异常", details={"error": str(e)})
