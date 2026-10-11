#!/usr/bin/env python3
"""
@file test_canary_resilience.py
@description Canary/Shadow 路由 Redis 故障容错回归（P0-1 闭环，2026-10-11 深度审计）
@author: YanYuCloudCube Team
@tags [test,canary,resilience,unit]

审计证据：Redis 不可达时 canary_get 裸调 hgetall → 聊天主路径全量 500
（docs/0379-world-执行记录/21-深度审核与实况测试报告.md §三 P0-1）。
本文件锁定修复后行为：Redis 故障=语义无灰度（直连 baseline）、负缓存防重试风暴、
失败信号/采样任务绝不抛异常。纯单元（桩替 redis_client），快速层运行。
"""

import asyncio
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

from app.services import model_registry_svc as svc  # noqa: E402

pytestmark = pytest.mark.unit


class _RedisDown:
    """hgetall/incr/expire 全部抛 ConnectionError 的故障桩（实例级计数）"""

    def __init__(self):
        self.calls = 0

    async def hgetall(self, *a, **k):
        self.calls += 1
        raise ConnectionError("Error 8 connecting to redis:6379")

    async def incr(self, *a, **k):
        raise ConnectionError("Error 8 connecting to redis:6379")

    async def expire(self, *a, **k):
        raise ConnectionError("Error 8 connecting to redis:6379")


class _RedisHash:
    """按预置哈希返回的桩（正路径）"""

    def __init__(self, data):
        self.data = data
        self.calls = 0

    async def hgetall(self, *a, **k):
        self.calls += 1
        return dict(self.data)


@pytest.fixture()
def clean_canary_cache():
    svc._canary_cache.clear()
    yield
    svc._canary_cache.clear()


def _run(coro):
    return asyncio.run(coro)


def test_canary_get_redis_down_returns_none(clean_canary_cache, monkeypatch):
    """P0-1 核心回归：Redis 宕机 → canary_get 返回 None（无灰度），绝不抛异常"""
    monkeypatch.setattr(svc, "redis_client", _RedisDown())
    assert _run(svc.canary_get("deepseek-v4-flash")) is None


def test_canary_route_redis_down_falls_to_baseline(clean_canary_cache, monkeypatch):
    """网关决策层：Redis 宕机 → canary_route 返回 None → chat 直连 req.model"""
    monkeypatch.setattr(svc, "redis_client", _RedisDown())
    assert _run(svc.canary_route("deepseek-v4-flash")) is None


def test_canary_get_negative_cache_avoids_retry_storm(clean_canary_cache, monkeypatch):
    """负缓存：故障期内重复查询只打一次 Redis（防每请求重试拖垮 P99）"""
    down = _RedisDown()
    monkeypatch.setattr(svc, "redis_client", down)
    _run(svc.canary_get("m"))
    _run(svc.canary_get("m"))
    _run(svc.canary_get("m"))
    assert down.calls == 1
    # 负缓存回填验证：缓存条目存在且值为 None
    assert svc._canary_cache["m"][0] is None


def test_canary_get_recovers_after_fail_ttl(clean_canary_cache, monkeypatch):
    """负缓存 5s 到期后自动重探测，Redis 恢复即恢复灰度路由"""
    fake_now = [1000.0]
    real_time = svc.time
    monkeypatch.setattr(
        svc,
        "time",
        types.SimpleNamespace(
            time=lambda: fake_now[0],
            gmtime=real_time.gmtime,
            strftime=real_time.strftime,
        ),
    )
    down = _RedisDown()
    monkeypatch.setattr(svc, "redis_client", down)
    assert _run(svc.canary_get("m")) is None
    assert down.calls == 1

    # 越过 5s 负缓存 TTL
    fake_now[0] += svc._CANARY_FAIL_TTL + 0.1
    up = _RedisHash({"baseline": "m", "canary": "m-v2", "weight": "100"})
    monkeypatch.setattr(svc, "redis_client", up)
    data = _run(svc.canary_get("m"))
    assert data is not None and data["canary"] == "m-v2"
    assert down.calls == 1  # 恢复前没有多余重试


def test_canary_positive_path_unchanged(clean_canary_cache, monkeypatch):
    """正路径回归：有灰度配置 → 按权重决策，且 10s 正缓存生效"""
    fake_now = [2000.0]
    real_time = svc.time
    monkeypatch.setattr(
        svc,
        "time",
        types.SimpleNamespace(
            time=lambda: fake_now[0],
            gmtime=real_time.gmtime,
            strftime=real_time.strftime,
        ),
    )
    up = _RedisHash({"baseline": "m", "canary": "m-v2", "weight": "100"})
    monkeypatch.setattr(svc, "redis_client", up)
    route = _run(svc.canary_route("m"))
    assert route is not None
    assert route["pick"] == "m-v2" and route["is_canary"] is True
    # 正缓存：TTL 内第二次查询不打 Redis
    _run(svc.canary_get("m"))
    assert up.calls == 1


def test_canary_report_failure_never_raises(clean_canary_cache, monkeypatch):
    """失败信号路径：Redis 宕机时仅记日志，绝不向 chat 异常处理器抛二次异常"""
    monkeypatch.setattr(svc, "redis_client", _RedisDown())
    _run(svc.canary_report_failure("m"))  # 不抛即通过


def test_shadow_fire_select_failure_swallowed(clean_canary_cache, monkeypatch):
    """采样任务：上游选择阶段异常不得逃逸为 unhandled task exception"""
    from app.services.upstream_registry import registry

    def _boom(model):
        raise RuntimeError("registry broken")

    monkeypatch.setattr(registry, "select", _boom)
    _run(svc.shadow_fire("m-v2", {"messages": [], "max_tokens": 32}))


def test_shadow_fire_happy_path_sends_request(clean_canary_cache, monkeypatch):
    """shadow 采样历史 bug 修复回归：配置命中后真实发出采样请求并记指标"""
    from app.services.upstream_registry import registry

    calls = {}

    class _U:
        base_url = "http://shadow.test:8001"
        api_key = None

    def _fake_select(model, capability="chat"):
        calls["model"] = model
        return _U()

    monkeypatch.setattr(registry, "select", _fake_select)

    import httpx

    req_log = []

    class _Resp:
        status_code = 200

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            req_log.append(url)
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    _run(svc.shadow_fire("m-v2", {"messages": [], "max_tokens": 32}))
    assert calls.get("model") == "m-v2"
    assert req_log == ["http://shadow.test:8001/v1/chat/completions"]
