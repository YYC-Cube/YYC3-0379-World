#!/usr/bin/env python3
"""
@file test_rate_limit_failback.py
@description 限流器 Redis 故障降级/自动回切状态机回归（P1-3，2026-10-11 深度审计）
@author: YanYuCloudCube Team
@tags [test,rate-limit,resilience,unit]

审计证据：_redis_available 一旦 False 即进程级永久闩锁，Redis 恢复后限流
滞留内存模式（docs/0379-world-执行记录/21-深度审核与实况测试报告.md §三 P1-3）。
本文件锁定修复后状态机：失败冷却 10s 不重复探测 → 到期自动重探测 → 恢复回切。
纯单元（桩替 redis_client.ping + 受控时钟），快速层运行。
"""

import asyncio
import importlib
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

# 注意：app.middleware 包级导出存在同名装饰器函数 rate_limit，会遮蔽子模块属性，
# 必须经 importlib 取模块对象本体（from app.middleware import rate_limit 拿到的是函数）
rl = importlib.import_module("app.middleware.rate_limit")

pytestmark = pytest.mark.unit


class _PingStub:
    """可控 ping 桩：按脚本序列返回/抛异常，并计数"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    async def ping(self):
        self.calls += 1
        item = self.script[min(self.calls - 1, len(self.script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture()
def limiter(monkeypatch):
    fake_now = [1000.0]
    real_time = rl.time
    monkeypatch.setattr(
        rl,
        "time",
        types.SimpleNamespace(
            time=lambda: fake_now[0],
            gmtime=real_time.gmtime,
            strftime=real_time.strftime,
        ),
    )
    lim = rl.RateLimiter(max_requests=100, time_window=60, burst=10)
    return lim, fake_now


def test_fail_degrades_and_caches_cooldown(limiter, monkeypatch):
    """Redis 失败 → 降级内存模式；冷却期内不重复探测（ping 只打一次）"""
    lim, _ = limiter
    stub = _PingStub([ConnectionError("down")])
    monkeypatch.setattr(rl, "redis_client", stub)

    assert asyncio.run(lim._check_redis()) is False
    assert lim._redis_available is False
    for _ in range(5):  # 冷却期内连续查询：不得重复 ping
        assert asyncio.run(lim._check_redis()) is False
    assert stub.calls == 1


def test_recovers_after_cooldown_and_fails_back(limiter, monkeypatch):
    """冷却到期自动重探测；Redis 恢复 → 回切分布式模式（_redis_available=True）"""
    lim, fake_now = limiter
    stub = _PingStub([ConnectionError("down"), True])
    monkeypatch.setattr(rl, "redis_client", stub)

    assert asyncio.run(lim._check_redis()) is False
    assert asyncio.run(lim._check_redis()) is False  # 冷却内短路
    assert stub.calls == 1

    fake_now[0] += 11  # 越过 10s 冷却
    assert asyncio.run(lim._check_redis()) is True
    assert lim._redis_available is True
    assert stub.calls == 2  # 到期后确实重探测


def test_flap_repeat_cycles(limiter, monkeypatch):
    """抖动场景：故障→恢复→再故障→再恢复，状态机全程正确"""
    lim, fake_now = limiter
    stub = _PingStub([ConnectionError("a"), True, ConnectionError("b"), True])
    monkeypatch.setattr(rl, "redis_client", stub)

    assert asyncio.run(lim._check_redis()) is False  # 故障
    fake_now[0] += 11
    assert asyncio.run(lim._check_redis()) is True  # 恢复
    fake_now[0] += 1  # 成功态无冷却，立即探测
    assert asyncio.run(lim._check_redis()) is False  # 再故障
    fake_now[0] += 11
    assert asyncio.run(lim._check_redis()) is True  # 再恢复
    assert lim._redis_available is True
