# file: zhipu.py
# description: 智谱 AI 服务模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [service],[zhipu],[ai]

"""
@file: app/services/zhipu.py
@description: 智谱 AI API 服务模块，提供智谱 AI 模型调用接口
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-13
@updated: 2026-03-13
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: services,python,zhipu,api,public
"""

import httpx
import json
from typing import List, Dict, Any
from app.config import settings
from app.utils import http_client

_ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
_ZHIPU_KEY = settings.zhipu_api_key


async def chat_completion(
    model: str,
    messages: List[Dict],
    max_tokens: int | None = None,
    temperature: float = 0.7,
    top_p: float | None = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    调用智谱 AI API 并返回 OpenAI 兼容的 JSON 格式
    """
    headers = {
        "Authorization": f"Bearer {_ZHIPU_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if temperature:
        payload["temperature"] = temperature
    if top_p:
        payload["top_p"] = top_p
    
    try:
        response = await http_client.post(
            f"{_ZHIPU_BASE}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        raw = response.json()
        choices = raw.get("choices", [])
        
        for choice in choices:
            message = choice.get("message", {})
            reasoning_content = message.get("reasoning_content", "")
            content = message.get("content", "")
            
            if reasoning_content and not content:
                message["content"] = reasoning_content
            elif reasoning_content and content:
                message["content"] = f"{reasoning_content}\n\n{content}"
        
        return {
            "id": raw.get("id", ""),
            "object": "chat.completion",
            "created": raw.get("created", 0),
            "model": model,
            "choices": choices,
            "usage": raw.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })
        }
    except httpx.HTTPStatusError as e:
        from app.utils.logger import logger
        logger.error(f"智谱 AI API 错误: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        from app.utils.logger import logger
        logger.error(f"智谱 AI 未知错误: {str(e)}")
        from app.errors import APIError
        raise APIError(message="智谱 AI 服务异常", details={"error": str(e)})


async def chat_completion_stream(
    model: str,
    messages: List[Dict],
    max_tokens: int | None = None,
    temperature: float = 0.7,
    top_p: float | None = None,
):
    """
    智谱GLM流式输出 - 用于WebSocket
    
    Yields:
        dict: 流式响应块
    """
    headers = {
        "Authorization": f"Bearer {_ZHIPU_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if temperature:
        payload["temperature"] = temperature
    if top_p:
        payload["top_p"] = top_p
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{_ZHIPU_BASE}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line and line.startswith("data: "):
                        data_str = line[6:]  # 移除 "data: " 前缀
                        
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            
                            for choice in choices:
                                delta = choice.get("delta", {})
                                
                                # 处理reasoning_content
                                reasoning = delta.get("reasoning_content", "")
                                content = delta.get("content", "")
                                
                                if reasoning and not content:
                                    delta["content"] = reasoning
                                elif reasoning and content:
                                    delta["content"] = f"{reasoning}\n\n{content}"
                                
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
        logger.error(f"智谱 AI 流式API错误: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        from app.utils.logger import logger
        logger.error(f"智谱 AI 流式输出错误: {str(e)}")
        from app.errors import APIError
        raise APIError(message="智谱 AI 流式服务异常", details={"error": str(e)})
