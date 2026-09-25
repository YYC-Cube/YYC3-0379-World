#!/usr/bin/env python3
"""
@file test_a2a_protocol.py
@description A2A 协议测试——消息信封/Agent Card 注册中心（心跳/能力发现）/审计流/端点
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-26
@tags [test,a2a,registry,audit,integration]

Redis 以内存桩替（monkeypatch a2a_protocol.redis_client 为异步内存桩 / _sync_client 为
同步内存桩），零外部依赖；异步路径经 asyncio.run 桥接（项目无 pytest-asyncio，范式同
test_agent_api）；测试密钥值运行时随机生成（凭据零硬编码）。
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

# 密钥读 conftest 统一注入值（收集顺序加固：测试文件只读不写，详见 tests/conftest.py）
_TEST_API_KEY = os.environ["API_KEYS"]
_TEST_RUNNER_KEY = os.environ["ADMIN_API_KEYS"]

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import a2a_protocol as proto  # noqa: E402

pytestmark = pytest.mark.integration

_CARD_YUSHU = {
    "agent_id": "yushu-wanwu-002",
    "agent_name": "语枢·万物",
    "role": "思考者",
    "capabilities": ["data_analysis"],
    "endpoint": "stream:agent:request:yushu",
    "layer": "business",
}
_CARD_YUJIAN = {
    "agent_id": "yujian-xianzhi-002",
    "agent_name": "预见·先知",
    "role": "预言家",
    "capabilities": ["trend_forecast"],
    "endpoint": "stream:agent:request:yujian",
    "layer": "business",
}


def _auth():
    return {"X-API-Key": _TEST_API_KEY}


def _runner_auth():
    return {"X-API-Key": _TEST_RUNNER_KEY}


class _FakeAsyncRedis:
    """异步 Redis 内存桩（仅 A2A 注册中心 Hash 与审计流 XADD 所需面）。"""

    def __init__(self):
        self.hash: dict = {}
        self.streams: dict = {}

    async def hget(self, key, field):
        return self.hash.get(field)

    async def hset(self, key, field, value):
        self.hash[field] = value

    async def hgetall(self, key):
        return dict(self.hash)

    async def xadd(self, stream, fields):
        msg_id = f"{len(self.streams) + 1}-1"
        self.streams.setdefault(stream, []).append(fields)
        return msg_id


class _FakeSyncRedis:
    """同步 Redis 内存桩（审计 sink 线程安全路径）。"""

    def __init__(self):
        self.streams: dict = {}

    def xadd(self, stream, fields):
        self.streams.setdefault(stream, []).append(fields)
        return "1-1"


@pytest.fixture()
def fake_redis(monkeypatch):
    """内存桩替换 a2a_protocol 的异步 Redis 客户端（注册中心 + 审计流）。"""
    fake = _FakeAsyncRedis()
    monkeypatch.setattr(proto, "redis_client", fake)
    return fake


@pytest.fixture()
def client():
    return TestClient(app)


# ════════════════════ 消息信封 ════════════════════


class TestMessageEnvelope:
    def test_build_and_parse_roundtrip(self):
        msg = proto.build_message(
            trace_id="trace-1",
            msg_type="task_request",
            sender="yuanqi-tianshu-001",
            receiver="yushu-wanwu-001",
            task_type="data_analysis",
            payload={"query": "分析Q2营收", "knowledge": ["同比增长32%"]},
            priority=7,
            ttl=120,
        )
        parsed = proto.parse_message(msg)
        assert parsed["msg_id"] == msg["msg_id"]
        assert parsed["trace_id"] == "trace-1"
        assert parsed["msg_type"] == "task_request"
        assert parsed["sender"] == "yuanqi-tianshu-001"
        assert parsed["receiver"] == "yushu-wanwu-001"
        assert parsed["task_type"] == "data_analysis"
        assert parsed["payload"] == {
            "query": "分析Q2营收",
            "knowledge": ["同比增长32%"],
        }
        assert parsed["priority"] == 7
        assert parsed["ttl"] == 120

    def test_msg_id_format(self):
        prefix, ms, rand = proto.generate_msg_id().split("-")
        assert prefix == "msg"
        assert len(ms) == 13 and ms.isdigit()
        assert len(rand) == 8

    def test_parse_message_non_str_payload_passthrough(self):
        raw = {"payload": {"already": "parsed"}}
        assert proto.parse_message(raw)["payload"] == {"already": "parsed"}

    def test_parse_message_invalid_payload_kept_raw(self):
        raw = {"payload": "{not-json"}
        assert proto.parse_message(raw)["payload"] == "{not-json"


# ════════════════════ Agent Card 注册中心 ════════════════════


class TestAgentRegistry:
    def test_register_and_online(self, fake_redis):
        full = asyncio.run(proto._registry_register(dict(_CARD_YUSHU)))
        assert full["status"] == "online"
        assert full["register_time"]
        online = asyncio.run(proto._registry_online_cards())
        assert [c["agent_id"] for c in online] == ["yushu-wanwu-002"]

    def test_register_preserves_first_register_time(self, fake_redis):
        first = asyncio.run(proto._registry_register(dict(_CARD_YUSHU)))
        again = asyncio.run(proto._registry_register(dict(_CARD_YUSHU)))
        assert again["register_time"] == first["register_time"]

    def test_heartbeat_timeout_marks_offline(self, fake_redis):
        await_register = proto._registry_register(dict(_CARD_YUSHU))
        asyncio.run(await_register)
        # 手写过期心跳时间戳（90s 超时判定）
        raw = json.loads(fake_redis.hash[_CARD_YUSHU["agent_id"]])
        raw["last_heartbeat"] = time.time() - proto.HEARTBEAT_TIMEOUT - 10
        fake_redis.hash[_CARD_YUSHU["agent_id"]] = json.dumps(raw)
        assert asyncio.run(proto._registry_online_cards()) == []
        all_cards = asyncio.run(proto._registry_all_cards())
        assert all_cards[0]["status"] == "offline"

    def test_heartbeat_unregistered_returns_false(self, fake_redis):
        assert asyncio.run(proto._registry_heartbeat("unknown-001")) is False

    def test_heartbeat_refreshes(self, fake_redis):
        card = asyncio.run(proto._registry_register(dict(_CARD_YUSHU)))
        assert asyncio.run(proto._registry_heartbeat(_CARD_YUSHU["agent_id"])) is True
        refreshed = json.loads(fake_redis.hash[_CARD_YUSHU["agent_id"]])
        assert refreshed["last_heartbeat"] >= card["last_heartbeat"]

    def test_capability_filter(self, fake_redis):
        asyncio.run(proto._registry_register(dict(_CARD_YUSHU)))
        asyncio.run(proto._registry_register(dict(_CARD_YUJIAN)))
        online = asyncio.run(proto._registry_online_cards(capability="data_analysis"))
        assert [c["agent_id"] for c in online] == ["yushu-wanwu-002"]
        online = asyncio.run(proto._registry_online_cards(capability="trend_forecast"))
        assert [c["agent_id"] for c in online] == ["yujian-xianzhi-002"]

    def test_builtin_agents_manifest_contract(self):
        """内置编队清单契约：8 张卡、id 唯一、capabilities 非空、元数据齐全。"""
        ids = [c["agent_id"] for c in proto.BUILTIN_AGENTS]
        assert len(proto.BUILTIN_AGENTS) == 8
        assert len(set(ids)) == 8
        for card in proto.BUILTIN_AGENTS:
            assert card["agent_name"] and card["role"] and card["layer"]
            assert card["capabilities"], card["agent_id"]


# ════════════════════ 审计流 ════════════════════


class TestAuditStream:
    def test_publish_audit_xadd_stringify(self, fake_redis):
        asyncio.run(
            proto.publish_audit(
                {
                    "trace_id": "t-1",
                    "auditor": "agent-gateway",
                    "action": "submit",
                    "detail": {"queue_position": 0},
                    "timestamp": 1_726_000_000_000,
                }
            )
        )
        entries = fake_redis.streams["stream:audit:log"]
        assert len(entries) == 1
        assert entries[0]["trace_id"] == "t-1"
        assert json.loads(entries[0]["detail"]) == {"queue_position": 0}

    def test_publish_audit_failure_tolerated(self, monkeypatch):
        class _Boom:
            async def xadd(self, stream, fields):
                raise RuntimeError("redis down")

        monkeypatch.setattr(proto, "redis_client", _Boom())
        asyncio.run(proto.publish_audit({"trace_id": "t-2", "action": "x"}))  # 不应抛出

    def test_threadsafe_sink_writes_sync_stream(self, monkeypatch):
        fake = _FakeSyncRedis()
        monkeypatch.setattr(proto, "_sync_client", lambda: fake)
        sink = proto.make_threadsafe_audit_sink()
        sink({"trace_id": "t-3", "action": "test", "detail": {"k": "v"}})
        entry = fake.streams["stream:audit:log"][0]
        assert entry["trace_id"] == "t-3"
        assert json.loads(entry["detail"]) == {"k": "v"}


# ════════════════════ 生命周期开关 ════════════════════


class TestRegistryLifecycle:
    def test_start_registry_disabled_no_task(self, monkeypatch):
        monkeypatch.setattr(proto, "_a2a_enabled", lambda: False)
        monkeypatch.setattr(proto, "_registry_task", None)
        proto.start_registry()
        assert proto._registry_task is None

    def test_stop_registry_without_task_noop(self):
        asyncio.run(proto.stop_registry())  # _registry_task 为 None 时不抛


# ════════════════════ A2A 端点 ════════════════════


class TestA2AAPI:
    def test_list_agents_empty(self, client, fake_redis):
        r = client.get("/v1/a2a/agents", headers=_auth())
        assert r.status_code == 200
        assert r.json() == {"agents": [], "count": 0}

    def test_register_requires_admin_key(self, client, fake_redis):
        r = client.post("/v1/admin/a2a/agents/register", json=_CARD_YUSHU, headers=_auth())
        assert r.status_code in (401, 403)

    def test_register_and_discover(self, client, fake_redis):
        r = client.post("/v1/admin/a2a/agents/register", json=_CARD_YUSHU, headers=_runner_auth())
        assert r.status_code == 200
        assert r.json() == {"agent_id": "yushu-wanwu-002", "status": "online"}

        r = client.get("/v1/a2a/agents", headers=_auth())
        assert r.json()["count"] == 1
        r = client.get("/v1/a2a/agents?capability=data_analysis", headers=_auth())
        assert r.json()["count"] == 1
        r = client.get("/v1/a2a/agents?capability=not_exist", headers=_auth())
        assert r.json() == {"agents": [], "count": 0}

    def test_heartbeat_unknown_agent_404(self, client, fake_redis):
        r = client.post("/v1/admin/a2a/agents/unknown-001/heartbeat", headers=_runner_auth())
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "agent_not_registered"

    def test_heartbeat_registered_agent(self, client, fake_redis):
        client.post("/v1/admin/a2a/agents/register", json=_CARD_YUJIAN, headers=_runner_auth())
        r = client.post("/v1/admin/a2a/agents/yujian-xianzhi-002/heartbeat", headers=_runner_auth())
        assert r.status_code == 200
        assert r.json() == {"agent_id": "yujian-xianzhi-002", "status": "online"}


# 编排任务审计埋点联动用例见 tests/test_agent_api.py::test_submit_and_claim_audited
# （复用其 autouse 存储层桩替与 audited 记录器，避免本文件重复桩替）
