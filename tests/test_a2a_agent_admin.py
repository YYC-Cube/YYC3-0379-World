#!/usr/bin/env python3
"""
@file test_a2a_agent_admin.py
@description A2A Agent 注册演进层测试——全量列表/PATCH扩展元数据/注销/审计/404
@author: YanYuCloudCube Team <admin@0379.email>
@tags [test,a2a,admin,evolution,integration]

规范 docs/模型接入与注册/04-Agent注册规范.md §4——现有 A2A 契约上的扩展端点。
Redis 以内存桩替（范式同 test_a2a_protocol）。
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

_TEST_ADMIN_KEY = os.environ["ADMIN_API_KEYS"]

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import a2a_protocol as proto  # noqa: E402

pytestmark = pytest.mark.integration

_CARD = {
    "agent_id": "web-search-agent",
    "agent_name": "Web Search Agent",
    "role": "外置搜索",
    "capabilities": ["tool_use", "search"],
    "endpoint": "stream:agent:task:web-search",
    "layer": "business",
}


class _FakeAsyncRedis:
    """异步 Redis 内存桩（Hash 面 + xadd 审计面 + hdel）。"""

    def __init__(self):
        self.hash: dict = {}
        self.audit: list = []

    async def hget(self, key, field):
        return self.hash.get(field)

    async def hset(self, key, field, value):
        self.hash[field] = value

    async def hgetall(self, key):
        return dict(self.hash)

    async def hdel(self, key, field):
        return 1 if self.hash.pop(field, None) is not None else 0

    async def xadd(self, stream, fields):
        self.audit.append(fields)
        return f"{len(self.audit)}-1"


@pytest.fixture()
def fake_redis(monkeypatch):
    stub = _FakeAsyncRedis()
    monkeypatch.setattr(proto, "redis_client", stub)
    return stub


@pytest.fixture()
def client(fake_redis):
    return TestClient(app)


def _admin():
    return {"X-API-Key": _TEST_ADMIN_KEY}


def _register(client, card=None):
    resp = client.post("/v1/admin/a2a/agents/register", json=card or _CARD, headers=_admin())
    assert resp.status_code == 200
    return resp.json()


class TestAdminListAgents:
    def test_list_includes_offline_with_counts(self, client, fake_redis):
        _register(client)
        # 伪造过期心跳 → 离线
        card = json.loads(fake_redis.hash["web-search-agent"])
        card["last_heartbeat"] = 0
        fake_redis.hash["web-search-agent"] = json.dumps(card)
        resp = client.get("/v1/admin/a2a/agents", headers=_admin())
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1 and body["offline"] == 1 and body["online"] == 0
        assert body["agents"][0]["status"] == "offline"

    def test_list_filter_by_capability(self, client):
        _register(client)
        assert (
            client.get("/v1/admin/a2a/agents?capability=search", headers=_admin()).json()["count"]
            == 1
        )
        assert (
            client.get("/v1/admin/a2a/agents?capability=nope", headers=_admin()).json()["count"]
            == 0
        )


class TestPatchAgent:
    def test_patch_evolution_fields(self, client):
        _register(client)
        resp = client.patch(
            "/v1/admin/a2a/agents/web-search-agent",
            json={
                "tools": [{"name": "web_search", "timeout_seconds": 30}],
                "timeout_seconds": 60,
                "rate_limit_per_minute": 120,
            },
            headers=_admin(),
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["tools"][0]["name"] == "web_search"
        assert updated["timeout_seconds"] == 60

    def test_patch_preserves_register_time(self, client, fake_redis):
        _register(client)
        before = json.loads(fake_redis.hash["web-search-agent"])["register_time"]
        client.patch(
            "/v1/admin/a2a/agents/web-search-agent", json={"role": "搜索增强"}, headers=_admin()
        )
        after = json.loads(fake_redis.hash["web-search-agent"])
        assert after["register_time"] == before
        assert after["role"] == "搜索增强"

    def test_patch_unknown_404(self, client):
        assert (
            client.patch(
                "/v1/admin/a2a/agents/nope", json={"role": "x"}, headers=_admin()
            ).status_code
            == 404
        )

    def test_patch_writes_audit(self, client, fake_redis):
        _register(client)
        client.patch("/v1/admin/a2a/agents/web-search-agent", json={"role": "y"}, headers=_admin())
        # 桩审计条目经 _stringify：action 为标量保留 str，detail 为 JSON 串
        actions = [a.get("action") for a in fake_redis.audit]
        assert "agent.updated" in actions


class TestUnregisterAgent:
    def test_unregister_removes_card(self, client, fake_redis):
        _register(client)
        resp = client.delete("/v1/admin/a2a/agents/web-search-agent", headers=_admin())
        assert resp.status_code == 200
        assert resp.json()["status"] == "deregistered"
        assert "web-search-agent" not in fake_redis.hash

    def test_unregister_unknown_404(self, client):
        assert client.delete("/v1/admin/a2a/agents/nope", headers=_admin()).status_code == 404

    def test_unregister_writes_audit(self, client, fake_redis):
        _register(client)
        client.delete("/v1/admin/a2a/agents/web-search-agent", headers=_admin())
        assert any("agent.deregistered" in str(a) for a in fake_redis.audit)


class TestServiceLayerEvolution:
    def test_update_card_ignores_non_whitelist_fields(self, fake_redis):
        asyncio.run(proto._registry_register(dict(_CARD)))
        updated = asyncio.run(
            proto._registry_update_card("web-search-agent", {"role": "ok", "hacker_field": "x"})
        )
        assert updated["role"] == "ok"
        assert "hacker_field" not in updated

    def test_unregister_builtin_note(self, fake_redis):
        """注销语义：HDEL 生效（内置编队自愈回归由 _registry_loop 承担，文档已注明）。"""
        asyncio.run(proto._registry_register(dict(_CARD)))
        assert asyncio.run(proto._registry_unregister("web-search-agent")) is True
        assert asyncio.run(proto._registry_unregister("web-search-agent")) is False
