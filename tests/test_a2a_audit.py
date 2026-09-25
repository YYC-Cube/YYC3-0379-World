#!/usr/bin/env python3
"""
@file test_a2a_audit.py
@description A2A 审计流 Loki 消费端测试——拉取推送/分组标签/ACK 语义/开关/生命周期
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-26
@tags [test,a2a,audit,loki,integration]

Redis 以内存桩替（与结果流测试同范式的消费者组语义简化模拟）；
Loki 以 duck-typed stub 客户端替（记录请求体，可注入失败）；异步路径经 asyncio.run 桥接。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))
# 密钥读 conftest 统一注入值（收集顺序加固）
_TEST_API_KEY = os.environ["API_KEYS"]

import pytest  # noqa: E402

from app.services import a2a_audit  # noqa: E402
from app.services import a2a_protocol as proto  # noqa: E402

pytestmark = pytest.mark.integration


class _FakeRedis:
    """审计 shipper 所需最小 Redis 面：stream + 消费者组（无 block 语义，立即返回）。"""

    def __init__(self):
        self.streams = {}
        self.groups = {}
        self.acked = []
        self._seq = 0

    def _state(self, stream, group):
        return self.groups.setdefault(
            (stream, group), {"last_delivered": "0", "pending": [], "acked": set()}
        )

    async def xadd(self, stream, fields, maxlen=None, approximate=None):
        self._seq += 1
        msg_id = f"{self._seq}-1"
        self.streams.setdefault(stream, []).append((msg_id, dict(fields)))
        return msg_id

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self._state(stream, group)
        return True

    async def xreadgroup(self, groupname, consumername, streams, count=None, block=None):
        stream, _from = next(iter(streams.items()))
        state = self._state(stream, groupname)
        entries = self.streams.get(stream, [])
        fresh = [
            (i, f)
            for i, f in entries
            if int(i.split("-")[0]) > int(state["last_delivered"].split("-")[0])
        ]
        batch = fresh[: count or len(fresh)]
        if batch:
            state["last_delivered"] = batch[-1][0]
            state["pending"].extend(batch)
        return [(stream, batch)] if batch else []

    async def xack(self, stream, groupname, *msg_ids):
        state = self._state(stream, groupname)
        state["acked"].update(msg_ids)
        state["pending"] = [(i, f) for i, f in state["pending"] if i not in msg_ids]
        self.acked.extend(msg_ids)
        return len(msg_ids)


class _StubLokiClient:
    """记录推送体的 stub（status_code 可注入失败）。"""

    def __init__(self, status_code=200):
        self.status_code = status_code
        self.bodies = []

    async def post(self, url, json):
        self.bodies.append((url, json))
        return self


async def _seed_audit(fake, entries):
    for entry in entries:
        await proto.publish_audit(entry)


def _entry(action, auditor, ts_ms=1700000000000):
    return {
        "trace_id": "t-1",
        "auditor": auditor,
        "action": action,
        "detail": {"k": 1},
        "timestamp": ts_ms,
    }


class TestLokiStreams:
    def test_group_by_event_agent_and_ts_ns(self):
        """entries → 按 (event, agent) 分组 label；timestamp 毫秒 → 纳秒对齐。"""
        entries = [
            ("1-1", {"action": "task_dead", "auditor": "a1", "timestamp": 1700000000000}),
            ("1-2", {"action": "task_dead", "auditor": "a1", "timestamp": None}),
            ("1-3", {"action": "orphan_result", "auditor": "gateway"}),
        ]
        streams = a2a_audit._to_loki_streams(entries)
        assert len(streams) == 2  # 两组 label
        dead = next(s for s in streams if s["stream"]["event"] == "task_dead")
        assert dead["stream"]["job"] == "a2a-audit"
        assert dead["stream"]["agent"] == "a1"
        assert len(dead["values"]) == 2
        assert dead["values"][0][0] == "1700000000000000000"  # ms→ns
        assert dead["values"][1][0].isdigit()  # None 时间戳 → now 兜底
        orphan = next(s for s in streams if s["stream"]["event"] == "orphan_result")
        assert orphan["stream"]["agent"] == "gateway"  # 缺 auditor 兜底


class TestShipOnce:
    def test_ship_and_ack(self, monkeypatch):
        """推送成功 → XACK（at-least-once 完成侧）；返回处理条数。"""
        fake = _FakeRedis()
        monkeypatch.setattr(proto, "redis_client", fake)
        asyncio.run(_seed_audit(fake, [_entry("task_dead", "a1"), _entry("task_retry", "a2")]))

        client = _StubLokiClient()
        shipped = asyncio.run(a2a_audit.ship_once(client=client))
        assert shipped == 2
        assert len(fake.acked) == 2
        assert len(client.bodies) == 1
        url, body = client.bodies[0]
        assert url.endswith("/loki/api/v1/push")
        assert {s["stream"]["event"] for s in body["streams"]} == {"task_dead", "task_retry"}

    def test_push_failure_no_ack(self, monkeypatch):
        """Loki 5xx → 抛错且不 ACK（PEL 保留，退避重试后可被 XAUTOCLAIM 回收）。"""
        fake = _FakeRedis()
        monkeypatch.setattr(proto, "redis_client", fake)
        asyncio.run(_seed_audit(fake, [_entry("task_dead", "a1")]))

        client = _StubLokiClient(status_code=500)
        with pytest.raises(RuntimeError):
            asyncio.run(a2a_audit.ship_once(client=client))
        assert fake.acked == []
        state = fake.groups[(proto.AUDIT_STREAM, a2a_audit.AUDIT_GROUP)]
        assert len(state["pending"]) == 1

    def test_empty_poll_noop(self, monkeypatch):
        """空轮询：不推送不 ACK，返回 0。"""
        fake = _FakeRedis()
        monkeypatch.setattr(proto, "redis_client", fake)
        client = _StubLokiClient()
        assert asyncio.run(a2a_audit.ship_once(client=client)) == 0
        assert client.bodies == []


class TestToggle:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("A2A_AUDIT_LOKI_ENABLED", raising=False)
        assert a2a_audit._enabled() is False

    def test_enabled_variants(self, monkeypatch):
        for variant in ("1", "true", "yes", "on"):
            monkeypatch.setenv("A2A_AUDIT_LOKI_ENABLED", variant)
            assert a2a_audit._enabled() is True


class TestLifecycle:
    def test_start_stop_within_loop(self, monkeypatch):
        """开关开 + A2A 启用：start 建 task，stop 取消收敛（幂等不重复建）。"""
        fake = _FakeRedis()
        monkeypatch.setattr(proto, "redis_client", fake)
        monkeypatch.setenv("A2A_AUDIT_LOKI_ENABLED", "true")
        monkeypatch.setenv("A2A_ENABLED", "true")

        async def drive():
            a2a_audit.start_audit_shipper()
            assert a2a_audit._task is not None
            first = a2a_audit._task
            a2a_audit.start_audit_shipper()  # 幂等：不重复建
            assert a2a_audit._task is first
            await a2a_audit.stop_audit_shipper()
            assert a2a_audit._task is None

        asyncio.run(drive())
