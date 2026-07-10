# file: ollama.py
# description: Ollama 模型服务模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [service],[ollama],[ai]

"""
@file: app/services/ollama.py
@description: Ollama 本地模型服务模块，提供本地模型推理接口
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-13
@updated: 2026-03-13
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: services,python,ollama,local,critical,public
"""

import os
import json
import httpx
import time
from typing import List, Dict, Any
from app.config import settings

_OLLAMA_ENDPOINTS = [
    "http://ollama:11434",
    f"http://{settings.ollama_host}:{settings.ollama_port}",
    "http://10.200.0.3:11434",
]

_TIMEOUT = httpx.Timeout(120.0, read=120.0)


async def _call_one(endpoint: str, payload: Dict) -> Dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{endpoint}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


async def chat_completion(
    model: str,
    messages: List[Dict],
    max_tokens: int | None = None,
    temperature: float = 0.7,
    top_p: float | None = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    调用本地 Ollama（可自动切换主/备）并返回 OpenAI‑compatible JSON
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": temperature,
        },
    }
    
    if max_tokens:
        payload["options"]["num_ctx"] = max_tokens
    if top_p:
        payload["options"]["top_p"] = top_p

    last_err = None
    for ep in _OLLAMA_ENDPOINTS:
        try:
            raw = await _call_one(ep, payload)
            return {
                "id": raw.get("created_at", ""),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": raw["message"],
                        "finish_reason": raw.get("done_reason", "stop"),
                    }
                ],
                "usage": {
                    "prompt_tokens": raw.get("prompt_eval_count", 0),
                    "completion_tokens": raw.get("eval_count", 0),
                    "total_tokens": raw.get("prompt_eval_count", 0) + raw.get("eval_count", 0),
                },
            }
        except Exception as exc:
            last_err = exc
            continue

    raise RuntimeError(f"All Ollama endpoints failed: {last_err}")


async def chat_completion_stream(
    model: str,
    messages: List[Dict],
    max_tokens: int | None = None,
    temperature: float = 0.7,
    top_p: float | None = None,
):
    """
    Ollama流式输出 - 用于WebSocket
    
    Yields:
        dict: 流式响应块
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
        },
    }
    
    if max_tokens:
        payload["options"]["num_ctx"] = max_tokens
    if top_p:
        payload["options"]["top_p"] = top_p
    
    last_err = None
    for ep in _OLLAMA_ENDPOINTS:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{ep}/api/chat",
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                message = chunk.get("message", {})
                                
                                yield {
                                    "id": chunk.get("created_at", ""),
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "role": message.get("role"),
                                            "content": message.get("content", "")
                                        },
                                        "finish_reason": chunk.get("done_reason") if chunk.get("done") else None
                                    }]
                                }
                            except json.JSONDecodeError:
                                continue
            
            # 成功完成，退出循环
            return
            
        except Exception as exc:
            last_err = exc
            continue
    
    raise RuntimeError(f"All Ollama endpoints failed for streaming: {last_err}")
