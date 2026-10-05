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

import asyncio
import ipaddress
import json
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings


def _normalize_host(host: str) -> str:
    """兼容 OLLAMA_HOST 两种格式：纯 host（127.0.0.1）或完整 URL（http://127.0.0.1:11434，
    Ollama 官方 CLI 即后者）——统一剥 scheme/端口只留纯 host，端口恒由 ollama_port 决定"""
    h = host.strip()
    for p in ("http://", "https://"):
        if h.startswith(p):
            h = h[len(p) :]
    if ":" in h:
        h = h.split(":", 1)[0]
    return h


def _endpoints() -> list:
    """Ollama 地址列表：主地址必选；OLLAMA_BACKUP_HOST 配置时追加备机"""
    eps = [f"http://{_normalize_host(settings.ollama_host)}:{settings.ollama_port}"]
    if settings.ollama_backup_host:
        eps.append(f"http://{_normalize_host(settings.ollama_backup_host)}:{settings.ollama_port}")
    return eps


# ── 本地 Ollama 集群智能识别（2026-10-05：CIDR 网段自动扫描，替代静态设备表）──
# 设计：无需既定设备清单——对 OLLAMA_DISCOVER_CIDR（如 192.168.3.0/24）并发探
# :port/api/tags，在线 Ollama 自动入表；结果 TTL 缓存 + 过期后台刷新（/health 高频
# 探活不重复扫网）。静态表 OLLAMA_LOCAL_HOSTS 保留为补充通道（CIDR 外的设备）。
_DISC_TTL = 300.0  # 发现缓存有效期（秒）
_DISC_CONNECT = 0.8  # 连接超时：在线主机毫秒级返回，离线快速跳过
_DISC_CONCURRENCY = 96  # 扫描并发：/24≈254 目标约 2-3s 完成
_DISC_MAX_NET = 1024  # 网段地址数上限（防误配大网段拖垮 /health）

_disc_cache: Dict[str, Any] = {"ts": 0.0, "found": []}


async def _disc_probe(ip: str, port: int, sem: asyncio.Semaphore) -> Optional[str]:
    """单目标探测：可达返回 base_url，否则 None（供 gather 并发调用）"""
    base = f"http://{ip}:{port}"
    async with sem:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(2.0, connect=_DISC_CONNECT)
            ) as client:
                resp = await client.get(f"{base}/api/tags")
                return base if resp.status_code == 200 else None
        except Exception:
            return None


async def discover_local_ollamas(cidr: str, port: int = 11434) -> List[str]:
    """扫描 CIDR 网段自动识别在线 Ollama（返回 base_url 列表，按 IP 序）。

    - /24 ≈254 目标 × 并发 96 × 0.8s 连接超时 → 全程约 2-3s
    - 网段非法或地址数 > _DISC_MAX_NET（/22 以上）直接返回空（防误配）
    """
    try:
        net = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return []
    if net.num_addresses > _DISC_MAX_NET:
        return []
    sem = asyncio.Semaphore(_DISC_CONCURRENCY)
    results = await asyncio.gather(*[_disc_probe(str(ip), port, sem) for ip in net.hosts()])
    return sorted(base for base in results if base)


async def _disc_refresh(cidr: str) -> None:
    """后台刷新发现结果（失败静默保留旧值，下轮再试）"""
    try:
        _disc_cache["found"] = await discover_local_ollamas(cidr)
        _disc_cache["ts"] = time.monotonic()
    except Exception:
        pass


async def local_cluster_targets(static_hosts: str, cidr: str, port: int) -> List[str]:
    """本地集群探测目标 = 静态表 ∪ 自动发现（去重）。

    缓存策略：进程首次调用内联首扫（≈2s，仅一次）；此后命中缓存，过期由后台任务
    刷新（/health 即时返回旧值，不阻塞）。cidr 为空时仅静态表。
    """
    targets: List[str] = []
    for item in static_hosts.split(","):
        item = item.strip()
        if item:
            host, _, p = item.partition(":")
            targets.append(f"http://{host}:{p or port}")
    if cidr.strip():
        if _disc_cache["ts"] == 0.0:
            _disc_cache["found"] = await discover_local_ollamas(cidr)
            _disc_cache["ts"] = time.monotonic()
        elif time.monotonic() - _disc_cache["ts"] > _DISC_TTL:
            asyncio.create_task(_disc_refresh(cidr))
        targets += [b for b in _disc_cache["found"] if b not in targets]
    return targets


_TIMEOUT = httpx.Timeout(120.0, read=120.0)


async def _call_one(endpoint: str, payload: Dict) -> Dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{endpoint}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()


async def chat_completion(
    model: str,
    messages: List[Dict],
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    top_p: Optional[float] = None,
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
    for ep in _endpoints():
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
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    top_p: Optional[float] = None,
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
    for ep in _endpoints():
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                async with client.stream("POST", f"{ep}/api/chat", json=payload) as response:
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
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "role": message.get("role"),
                                                "content": message.get("content", ""),
                                            },
                                            "finish_reason": (
                                                chunk.get("done_reason")
                                                if chunk.get("done")
                                                else None
                                            ),
                                        }
                                    ],
                                }
                            except json.JSONDecodeError:
                                continue

            # 成功完成，退出循环
            return

        except Exception as exc:
            last_err = exc
            continue

    raise RuntimeError(f"All Ollama endpoints failed for streaming: {last_err}")
