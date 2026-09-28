#!/usr/bin/env python3
"""
@file test_model_registry_svc.py
@description 模型注册中心服务层测试——CRUD幂等/心跳TTL三级/版本回滚/事件/双通道上游产出
@author: YanYuCloudCube Team <admin@0379.email>
@tags [test,registry,svc,integration]

sqlite 文件库（tmp_path）替换 app.db.async_session；Redis publish 桩替（防真连接超时）；
异步路径 asyncio.run 桥接（项目无 pytest-asyncio，范式同 test_vk_whitelist_bind）。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.services import model_registry_svc as svc  # noqa: E402

pytestmark = pytest.mark.integration

_PAYLOAD = {
    "model_id": "qwen3.8-27b",
    "display_name": "Qwen3.8 27B",
    "backend": "vllm",
    "version": "v1.0.0",
    "capabilities": ["chat", "tool_use"],
    "base_url": "http://yyc3-101.local:8001/v1",
    "node_id": "yyc3-101",
    "node_role": "primary",
    "model_type": "chat",
    "tags": ["旗舰"],
}


class _NoopRedis:
    async def publish(self, *a, **k):
        return 0


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    """sqlite 文件库替换 app.db.async_session/engine（svc 函数内 import，运行时取属性 → 生效）。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    import app.db as app_db

    monkeypatch.setattr(app_db, "async_session", session_factory)
    monkeypatch.setattr(app_db, "engine", engine)  # ensure_tables 建表走 engine
    monkeypatch.setattr(app_db, "DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}")
    monkeypatch.setattr(svc, "redis_client", _NoopRedis())
    asyncio.run(svc.ensure_tables())
    return session_factory


def _register(payload=None):
    return asyncio.run(svc.register_model(dict(payload or _PAYLOAD)))


class TestCrud:
    def test_register_and_get(self, sqlite_db):
        result = _register()
        assert result["id"] == "qwen3.8-27b"
        assert result["capabilities"] == ["chat", "tool_use"]
        assert result["state"] == "offline"  # 注册默认 offline，就绪后置 ready
        assert result["tags"] == ["旗舰"]

    def test_register_idempotent_overwrite(self, sqlite_db):
        _register()
        payload = dict(_PAYLOAD, display_name="Qwen3.8 27B 改", version="v1.1.0")
        result = _register(payload)
        models = asyncio.run(svc.list_models())
        assert len(models) == 1  # 幂等：覆盖不产生副本
        assert result["display_name"] == "Qwen3.8 27B 改"

    def test_register_requires_model_id(self, sqlite_db):
        with pytest.raises(ValueError):
            asyncio.run(svc.register_model({"display_name": "x"}))

    def test_update_patch_whitelist(self, sqlite_db):
        _register()
        updated = asyncio.run(svc.update_model("qwen3.8-27b", {"state": "ready", "enabled": False}))
        assert updated["state"] == "ready"
        assert updated["enabled"] in (0, False)

    def test_deregister(self, sqlite_db):
        _register()
        assert asyncio.run(svc.deregister_model("qwen3.8-27b")) is True
        assert asyncio.run(svc.get_model("qwen3.8-27b")) is None
        assert asyncio.run(svc.deregister_model("qwen3.8-27b")) is False


class TestVersionsAndRollback:
    def test_version_history_append(self, sqlite_db):
        _register()
        _register(dict(_PAYLOAD, version="v1.1.0"))
        versions = asyncio.run(svc.list_versions("qwen3.8-27b"))
        assert [v["version"] for v in versions] == ["v1.1.0", "v1.0.0"]
        assert all(v["action"] == "register" for v in versions)

    def test_rollback_to_known_version(self, sqlite_db):
        _register()
        _register(dict(_PAYLOAD, version="v1.1.0"))
        updated = asyncio.run(svc.rollback_model("qwen3.8-27b", "v1.0.0", reason="性能退化"))
        assert updated["version"] == "v1.0.0"
        actions = [v["action"] for v in asyncio.run(svc.list_versions("qwen3.8-27b"))]
        assert actions.count("rollback") == 1

    def test_rollback_unknown_version_rejected(self, sqlite_db):
        _register()
        with pytest.raises(ValueError):
            asyncio.run(svc.rollback_model("qwen3.8-27b", "v9.9.9"))


class TestHeartbeatAndTtl:
    def test_heartbeat_refreshes_health(self, sqlite_db):
        _register()
        assert asyncio.run(svc.heartbeat("qwen3.8-27b", gpu_utilization=0.7)) is True
        health = asyncio.run(svc.get_health("qwen3.8-27b"))
        assert health["runtime"]["gpu_utilization"] == 0.7
        assert health["heartbeat_age_seconds"] < 5

    def test_heartbeat_self_heals_offline_to_ready(self, sqlite_db):
        """自愈回升（09-28 pkill 竞态事故复盘）：offline + 心跳到达 → ready + 事件。"""
        _register()
        asyncio.run(svc.update_model("qwen3.8-27b", {"state": "offline"}))
        events_before = len(asyncio.run(svc.recent_events()))
        assert asyncio.run(svc.heartbeat("qwen3.8-27b")) is True
        model = asyncio.run(svc.get_model("qwen3.8-27b"))
        assert model["state"] == "ready"  # 自动回升
        assert model["last_heartbeat_at"] is not None
        events = asyncio.run(svc.recent_events())
        assert len(events) == events_before + 1
        assert events[-1]["payload"].get("self_healed") == "offline→ready by heartbeat"

    def test_heartbeat_keeps_draining_state(self, sqlite_db):
        """draining（排空运维意图）不被心跳回升。"""
        _register()
        asyncio.run(svc.update_model("qwen3.8-27b", {"state": "draining"}))
        asyncio.run(svc.heartbeat("qwen3.8-27b"))
        assert asyncio.run(svc.get_model("qwen3.8-27b"))["state"] == "draining"

    def test_heartbeat_no_event_when_already_ready(self, sqlite_db):
        """steady 态心跳不发事件（防每 30s 刷屏）。"""
        _register()
        asyncio.run(svc.update_model("qwen3.8-27b", {"state": "ready"}))
        before = len(asyncio.run(svc.recent_events()))
        asyncio.run(svc.heartbeat("qwen3.8-27b"))
        assert len(asyncio.run(svc.recent_events())) == before

    def test_heartbeat_unknown_model(self, sqlite_db):
        assert asyncio.run(svc.heartbeat("nope")) is False

    def test_ttl_degraded_ladder(self, sqlite_db):
        """TTL 三级阶梯：伪造 100s 前心跳 → degraded；200s → unreachable。"""
        from sqlalchemy import text

        _register()
        asyncio.run(svc.heartbeat("qwen3.8-27b"))
        asyncio.run(svc.update_model("qwen3.8-27b", {"state": "ready"}))
        session_factory = svc.get_model  # noqa: F841（占位说明：直接 SQL 回拨时间戳）
        import app.db as app_db

        for age, expected in ((100, "degraded"), (200, "unreachable")):

            async def _backdate():
                async with app_db.async_session() as session:
                    await session.execute(
                        text(
                            "UPDATE model_registry SET last_heartbeat_at = "
                            "datetime('now', :neg) WHERE id = :id"
                        ),
                        {"neg": f"-{age} seconds", "id": "qwen3.8-27b"},
                    )
                    await session.commit()

            asyncio.run(_backdate())
            model = asyncio.run(svc.get_model("qwen3.8-27b"))
            assert model["health_status"] == expected


class TestEventsAndUpstreams:
    def test_events_recorded(self, sqlite_db):
        _register()
        events = asyncio.run(svc.recent_events())
        assert events and events[-1]["event_type"] == "registered"
        assert events[-1]["model_id"] == "qwen3.8-27b"

    def test_registry_upstreams_only_ready(self, sqlite_db):
        """双通道产出：仅 enabled+ready+base_url 的模型产出 env 同构上游条目。"""
        _register()
        _register(dict(_PAYLOAD, model_id="offline-model", base_url="http://10.0.0.2:8000/v1"))
        asyncio.run(svc.update_model("qwen3.8-27b", {"state": "ready"}))
        entries = asyncio.run(svc.registry_upstreams())
        assert len(entries) == 1
        entry = entries[0]
        assert entry["name"] == "registry-qwen3.8-27b"
        assert entry["base_url"] == "http://yyc3-101.local:8001/v1"
        assert entry["priority"] == 5  # primary

    def test_registry_upstreams_excludes_stale_heartbeat(self, sqlite_db):
        """300s 无心跳视为已摘除（TTL_REMOVED），不产出上游。"""
        from sqlalchemy import text

        _register()
        asyncio.run(svc.update_model("qwen3.8-27b", {"state": "ready"}))
        asyncio.run(svc.heartbeat("qwen3.8-27b"))

        import app.db as app_db

        async def _backdate():
            async with app_db.async_session() as session:
                await session.execute(
                    text(
                        "UPDATE model_registry SET "
                        "last_heartbeat_at = datetime('now', '-400 seconds') WHERE id = :id"
                    ),
                    {"id": "qwen3.8-27b"},
                )
                await session.commit()

        asyncio.run(_backdate())
        assert asyncio.run(svc.registry_upstreams()) == []

    def test_registry_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("REGISTRY_ENABLED", raising=False)
        assert svc.registry_enabled() is False
        monkeypatch.setenv("REGISTRY_ENABLED", "true")
        assert svc.registry_enabled() is True
