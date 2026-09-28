#!/usr/bin/env python3
"""
@file test_registry_api.py
@description 模型注册中心 API 测试——12端点/管理面RBAC/灰度开关503/幂等注册
@author: YanYuCloudCube Team <admin@0379.email>
@tags [test,registry,api,integration]

sqlite 文件库 + TestClient；REGISTRY_ENABLED 灰度开关用例覆盖 Phase A 语义。
认证分层：/registry/v1/** 全程普通认证；写操作端点内校验 admin。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

_TEST_API_KEY = os.environ["API_KEYS"]
_TEST_ADMIN_KEY = os.environ["ADMIN_API_KEYS"]

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.main import app  # noqa: E402
from app.services import model_registry_svc as svc  # noqa: E402

pytestmark = pytest.mark.integration

_BODY = {
    "model_id": "glm-5.3-flash",
    "display_name": "GLM 5.3 Flash",
    "backend": "vllm",
    "version": "v5.3.0",
    "capabilities": ["chat"],
    "base_url": "http://yyc3-102.local:8002/v1",
    "node_id": "yyc3-102",
    "model_type": "chat",
}


class _NoopRedis:
    async def publish(self, *a, **k):
        return 0


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    import app.db as app_db

    monkeypatch.setattr(app_db, "async_session", session_factory)
    monkeypatch.setattr(app_db, "engine", engine)  # ensure_tables 建表走 engine
    monkeypatch.setattr(app_db, "DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'registry.db'}")
    monkeypatch.setattr(svc, "redis_client", _NoopRedis())
    monkeypatch.setenv("REGISTRY_ENABLED", "true")
    asyncio.run(svc.ensure_tables())
    return TestClient(app)


def _admin():
    return {"X-API-Key": _TEST_ADMIN_KEY}


def _normal():
    return {"X-API-Key": _TEST_API_KEY}


class TestReadEndpoints:
    def test_list_and_get_roundtrip(self, sqlite_db):
        assert (
            sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin()).status_code == 201
        )
        listed = sqlite_db.get("/registry/v1/models", headers=_normal()).json()
        assert listed["count"] == 1
        detail = sqlite_db.get("/registry/v1/models/glm-5.3-flash", headers=_normal())
        assert detail.status_code == 200
        assert detail.json()["base_url"] == "http://yyc3-102.local:8002/v1"

    def test_unauthenticated_401(self, sqlite_db):
        assert sqlite_db.get("/registry/v1/models").status_code == 401

    def test_get_unknown_404(self, sqlite_db):
        assert sqlite_db.get("/registry/v1/models/nope", headers=_normal()).status_code == 404

    def test_versions_endpoint(self, sqlite_db):
        sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin())
        resp = sqlite_db.get("/registry/v1/models/glm-5.3-flash/versions", headers=_normal())
        assert resp.status_code == 200
        assert resp.json()["versions"][0]["version"] == "v5.3.0"

    def test_health_endpoint(self, sqlite_db):
        sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin())
        resp = sqlite_db.get("/registry/v1/models/glm-5.3-flash/health", headers=_normal())
        assert resp.status_code == 200
        assert "health_status" in resp.json()


class TestWriteGuardrails:
    def test_register_requires_admin(self, sqlite_db):
        resp = sqlite_db.post("/registry/v1/models", json=_BODY, headers=_normal())
        assert resp.status_code == 403

    def test_write_disabled_when_registry_off(self, sqlite_db, monkeypatch):
        monkeypatch.setenv("REGISTRY_ENABLED", "false")
        resp = sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin())
        assert resp.status_code == 503
        body = resp.json()
        assert body["detail"]["error"] == "registry_disabled"

    def test_register_idempotent(self, sqlite_db):
        sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin())
        resp = sqlite_db.post(
            "/registry/v1/models", json=dict(_BODY, version="v5.3.1"), headers=_admin()
        )
        assert resp.status_code == 201
        assert sqlite_db.get("/registry/v1/models", headers=_normal()).json()["count"] == 1

    def test_patch_and_delete(self, sqlite_db):
        sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin())
        patched = sqlite_db.patch(
            "/registry/v1/models/glm-5.3-flash", json={"state": "ready"}, headers=_admin()
        )
        assert patched.status_code == 200
        assert patched.json()["state"] == "ready"
        deleted = sqlite_db.delete("/registry/v1/models/glm-5.3-flash", headers=_admin())
        assert deleted.status_code == 200
        assert (
            sqlite_db.get("/registry/v1/models/glm-5.3-flash", headers=_normal()).status_code == 404
        )

    def test_rollback_flow(self, sqlite_db):
        sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin())
        sqlite_db.post("/registry/v1/models", json=dict(_BODY, version="v5.3.1"), headers=_admin())
        resp = sqlite_db.post(
            "/registry/v1/models/glm-5.3-flash/rollback",
            json={"target_version": "v5.3.0", "reason": "t"},
            headers=_admin(),
        )
        assert resp.status_code == 200
        assert resp.json()["target_version"] == "v5.3.0"

    def test_heartbeat_and_audit(self, sqlite_db):
        sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin())
        hb = sqlite_db.post(
            "/registry/v1/models/glm-5.3-flash/heartbeat",
            json={"status": "healthy", "gpu_utilization": 0.5},
            headers=_normal(),
        )
        assert hb.status_code == 200
        audit = sqlite_db.get("/registry/v1/audit", headers=_admin())
        assert audit.status_code == 200
        assert audit.json()["count"] >= 1  # register 已入审计

    def test_manifest_by_hash(self, sqlite_db):
        created = sqlite_db.post("/registry/v1/models", json=_BODY, headers=_admin()).json()
        m_hash = created["manifest_hash"]
        resp = sqlite_db.get(f"/registry/v1/manifests/{m_hash}", headers=_normal())
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "glm-5.3-flash"
