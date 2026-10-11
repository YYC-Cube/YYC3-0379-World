# file: test_redis_probe_unit.py
# description: probe_redis 单元测试 - yyc3_redis_up 指标维护（RedisDown 告警数据源）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-10-11
# tags: [test],[unit],[redis],[metrics],[chaos-drill]

"""Redis 连通性探针的指标语义测试。

配套 2026-10-11 故障演练制度化（scripts/chaos-redis.sh）：
probe_redis 是 RedisDown 告警（yyc3_redis_up == 0 for 1m）的唯一数据生产者，
必须保证：探测成功 → gauge=1；探测失败 → gauge=0；异常不外泄。
conftest._hermetic_redis 已以 fakeredis 替换 app.cache.redis_client 绑定。
异步执行沿用本仓库口径：sync 测试函数内 asyncio.run（pytest-asyncio strict 免标记）。
"""

import asyncio

import pytest

import app.cache as cache_module
from app.cache import probe_redis
from app.utils.metrics import metrics_manager

pytestmark = pytest.mark.unit


def _gauge() -> float:
    """读 yyc3_redis_up 当前值（无 label 的裸 Gauge）"""
    return metrics_manager.redis_up._value.get()


class TestProbeRedis:
    def test_healthy_sets_gauge_to_1(self):
        """fakeredis 可达：返回 True 且 gauge 落 1"""
        assert asyncio.run(probe_redis()) is True
        assert _gauge() == 1

    def test_unreachable_sets_gauge_to_0(self, monkeypatch):
        """Redis 宕机（ping 抛连接异常）：返回 False 且 gauge 落 0，异常不外泄"""

        async def _boom():
            raise ConnectionError("Connection refused")

        monkeypatch.setattr(cache_module.redis_client, "ping", _boom)
        assert asyncio.run(probe_redis()) is False
        assert _gauge() == 0

    def test_recovers_after_transient_failure(self, monkeypatch):
        """瞬断恢复语义：失败置 0 后，ping 恢复则 gauge 回 1（与限流 10s 回切同口径）

        注意：不可用 monkeypatch.undo()——conftest 的 fakeredis 绑定与本测试共用同一
        monkeypatch 实例（pytest 函数级注入），undo 会把 hermetic 绑定一并回滚。"""
        original_ping = cache_module.redis_client.ping

        async def _boom():
            raise ConnectionError("Connection refused")

        monkeypatch.setattr(cache_module.redis_client, "ping", _boom)
        assert asyncio.run(probe_redis()) is False
        assert _gauge() == 0

        # 恢复：显式写回原 bound method（留在同一 undo 栈，fixture 收尾统一清理）
        monkeypatch.setattr(cache_module.redis_client, "ping", original_ping)
        assert asyncio.run(probe_redis()) is True
        assert _gauge() == 1
