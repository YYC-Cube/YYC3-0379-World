#!/usr/bin/env python3
"""
@file test_registry_merge_consumer.py
@description Phase B 增量合并测试——事件驱动 merge/定点摘除/健壮性（免重启入池语义）
@author: YanYuCloudCube Team <admin@0379.email>
@tags [test,registry,phase-b,merge,integration]
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.services import model_registry_svc as svc  # noqa: E402
from app.services import upstream_registry  # noqa: E402

pytestmark = pytest.mark.integration

_PAYLOAD = {
    "model_id": "phaseb-probe",
    "display_name": "Phase B 探针",
    "backend": "vllm",
    "capabilities": ["chat"],
    "base_url": "http://10.0.0.77:9000/v1",
    "model_type": "chat",
}


class _NoopRedis:
    async def publish(self, *a, **k):
        return 0


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pb.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    import app.db as app_db

    monkeypatch.setattr(app_db, "async_session", session_factory)
    monkeypatch.setattr(app_db, "engine", engine)
    monkeypatch.setattr(app_db, "DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'pb.db'}")
    monkeypatch.setattr(svc, "redis_client", _NoopRedis())
    asyncio.run(svc.ensure_tables())
    # 池隔离快照（用例内合并的 registry-* 条目用后还原）
    snapshot = dict(upstream_registry.registry.upstreams)
    yield session_factory
    upstream_registry.registry.upstreams.clear()
    upstream_registry.registry.upstreams.update(snapshot)


def _pool_names():
    return sorted(n for n in upstream_registry.registry.upstreams if n.startswith("registry-"))


class TestHandleEvent:
    def test_registered_event_merges_into_pool(self, sqlite_db):
        asyncio.run(svc.register_model(dict(_PAYLOAD)))
        asyncio.run(svc.update_model("phaseb-probe", {"state": "ready"}))
        asyncio.run(
            svc._handle_registry_event({"event_type": "registered", "model_id": "phaseb-probe"})
        )
        assert "registry-phaseb-probe" in _pool_names()

    def test_deregistered_event_removes_from_pool(self, sqlite_db):
        asyncio.run(svc.register_model(dict(_PAYLOAD)))
        asyncio.run(svc.update_model("phaseb-probe", {"state": "ready"}))
        asyncio.run(
            svc._handle_registry_event({"event_type": "registered", "model_id": "phaseb-probe"})
        )
        assert "registry-phaseb-probe" in _pool_names()
        asyncio.run(
            svc._handle_registry_event({"event_type": "deregistered", "model_id": "phaseb-probe"})
        )
        assert "registry-phaseb-probe" not in _pool_names()

    def test_updated_event_remerges_state_change(self, sqlite_db):
        """updated 事件全量重合并：ready→offline 后条目应消失（merge 不再产出）。"""
        asyncio.run(svc.register_model(dict(_PAYLOAD)))
        asyncio.run(svc.update_model("phaseb-probe", {"state": "ready"}))
        asyncio.run(
            svc._handle_registry_event({"event_type": "updated", "model_id": "phaseb-probe"})
        )
        assert "registry-phaseb-probe" in _pool_names()
        asyncio.run(svc.update_model("phaseb-probe", {"state": "offline"}))
        asyncio.run(
            svc._handle_registry_event({"event_type": "updated", "model_id": "phaseb-probe"})
        )
        assert "registry-phaseb-probe" not in _pool_names()

    def test_malformed_event_no_raise(self, sqlite_db):
        asyncio.run(svc._handle_registry_event({"event_type": ""}))  # 空 type：静默忽略
        asyncio.run(svc._handle_registry_event({"event_type": "deregistered"}))  # 无 model_id

    def test_unknown_model_deregister_is_noop(self, sqlite_db):
        asyncio.run(
            svc._handle_registry_event({"event_type": "deregistered", "model_id": "never-existed"})
        )
        assert "registry-never-existed" not in _pool_names()


class TestConsumerLifecycle:
    def test_start_stop_idempotent(self, sqlite_db, monkeypatch):
        """start 幂等（同 loop 内二次 start 不新建任务）；stop 后任务归 None。"""

        class _PubSub:
            async def subscribe(self, *a):
                return None

            async def get_message(self, **k):
                await asyncio.sleep(0.01)
                return None

            async def unsubscribe(self, *a):
                return None

            async def close(self):
                return None

        class _Redis:
            def pubsub(self):
                return _PubSub()

        monkeypatch.setattr(svc, "redis_client", _Redis())

        async def _scenario():
            await svc.start_merge_consumer()
            task1 = svc._merge_task
            await svc.start_merge_consumer()
            assert svc._merge_task is task1  # 幂等
            await svc.stop_merge_consumer()
            assert svc._merge_task is None

        asyncio.run(_scenario())


class TestHeartbeatWatch:
    """TOP3b：断流翻转告警语义（stale↔healthy 各告警一次，不重复刷屏）。"""

    @staticmethod
    def _model(mid, age_seconds):
        import datetime

        return {
            "id": mid,
            "node_id": "yyc3-101",
            "state": "ready",
            "last_heartbeat_at": (
                datetime.datetime.utcnow() - datetime.timedelta(seconds=age_seconds)
                if age_seconds is not None
                else None
            ),
        }

    def test_stale_flip_warns_once_and_recovers(self, caplog):
        import logging

        svc._stale_state.clear()
        with caplog.at_level(logging.INFO, logger="app.services.model_registry_svc"):
            asyncio.run(svc._watch_once([self._model("m1", 10)]))  # healthy 初判（无告警）
            asyncio.run(svc._watch_once([self._model("m1", 10)]))  # 持续 healthy（无告警）
            asyncio.run(svc._watch_once([self._model("m1", 200)]))  # → stale：warning ×1
            asyncio.run(svc._watch_once([self._model("m1", 300)]))  # 持续 stale（不重复）
            asyncio.run(svc._watch_once([self._model("m1", 10)]))  # → 恢复：info ×1
        warns = [r for r in caplog.records if "心跳断流告警" in r.message]
        recovers = [r for r in caplog.records if "心跳恢复" in r.message]
        assert len(warns) == 1 and "m1" in warns[0].message
        assert len(recovers) == 1

    def test_manual_mode_no_stale(self, caplog):
        """无心跳（手动模式）age=-1：不参与断流判定。"""
        import logging

        svc._stale_state.clear()
        with caplog.at_level(logging.INFO, logger="app.services.model_registry_svc"):
            asyncio.run(svc._watch_once([self._model("m2", None)]))
            asyncio.run(svc._watch_once([self._model("m2", None)]))
        assert not [r for r in caplog.records if "断流" in r.message]
        assert svc._stale_state["m2"] is False
