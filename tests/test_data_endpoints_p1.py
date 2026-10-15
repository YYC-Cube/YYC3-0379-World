#!/usr/bin/env python3
"""
@file test_data_endpoints_p1.py
@description 双端联通 P1 数据端点测试——BL-A1 /v1/logs · BL-A2 /v1/usage/timeline ·
             BL-A3 summary cost 真实化 · BL-A4 /v1/admin/alerts（sqlite 实库 + RBAC）
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-10-15
@tags [test,duallink,p1,logs,timeline,alerts,summary]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

os.environ.setdefault("API_KEYS", "test-key-1")

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

_HEADERS = {"X-API-Key": os.environ.get("API_KEYS", "test-key-1")}
_ADMIN_HEADERS = {"X-API-Key": os.environ.get("ADMIN_API_KEYS", "runner-test-key-1")}

client = TestClient(app)


@pytest.fixture()
def seeded_logs(tmp_path, monkeypatch):
    """sqlite 隔离库（对齐 test_registry_api 范式）: monkeypatch app_db 会话/引擎 →
    ensure_tables 自建（含 007 新列）→ 经生产写入器 _flush_batch 插桩 3 行"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.db as app_db
    from app.services.virtual_key_manager import vk_manager

    db_file = tmp_path / "p1.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(app_db, "async_session", session_factory)
    monkeypatch.setattr(app_db, "engine", engine)
    monkeypatch.setattr(app_db, "DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    # /v1/models/summary 使用 main 模块级 async_session 绑定 — 一并切到 sqlite 工厂
    import app.main as app_main

    monkeypatch.setattr(app_main, "async_session", session_factory)

    from app.db import UsageLog

    async def _create_usage_log():
        async with engine.begin() as conn:
            await conn.run_sync(UsageLog.__table__.create, checkfirst=True)

    asyncio.run(_create_usage_log())  # ORM 单表（/v1/models/summary 的 UsageLog 查询）
    asyncio.run(vk_manager.ensure_tables())
    asyncio.run(
        vk_manager._flush_batch(
            [
                {
                    "key_id": None, "model": "glm-4-flash", "upstream": "zhipu",
                    "capability": "chat", "prompt_tokens": 1000, "completion_tokens": 500,
                    "cost_usd": 0.25, "latency_ms": 800, "status": "ok",
                },
                {
                    "key_id": None, "model": "glm-4-flash", "upstream": "zhipu",
                    "capability": "chat", "prompt_tokens": 200, "completion_tokens": 80,
                    "cost_usd": 0.05, "latency_ms": 400, "status": "ok",
                },
                {
                    "key_id": None, "model": "deepseek-v4", "upstream": "deepseek",
                    "capability": "chat", "prompt_tokens": 300, "completion_tokens": 100,
                    "cost_usd": 0.1, "latency_ms": 1200, "status": "error",
                    "request_id": "chatcmpl-trace-001",
                },
            ]
        )
    )
    yield TestClient(app)


# ── BL-A1: /v1/logs ────────────────────────────────────────────────


def test_logs_query_basic(seeded_logs):
    res = seeded_logs.get("/v1/logs?minutes=60", headers=_ADMIN_HEADERS)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["total"] == 3
    assert body["limit"] == 100
    # 倒序 + 可观测性列 + tokens 派生
    first = body["logs"][0]
    assert first["model"] == "deepseek-v4"
    assert first["status"] == "error"
    assert first["tokens"] == 400


def test_logs_query_filters(seeded_logs):
    res = seeded_logs.get(
        "/v1/logs?minutes=60&model=glm-4-flash&status=ok", headers=_ADMIN_HEADERS
    )
    body = res.json()
    assert body["total"] == 2
    assert all(row["model"] == "glm-4-flash" and row["status"] == "ok" for row in body["logs"])

    res_err = seeded_logs.get("/v1/logs?minutes=60&status=error", headers=_ADMIN_HEADERS)
    assert res_err.json()["total"] == 1


def test_logs_query_pagination(seeded_logs):
    res = seeded_logs.get("/v1/logs?minutes=60&limit=2&offset=2", headers=_ADMIN_HEADERS)
    body = res.json()
    assert len(body["logs"]) == 1
    assert body["offset"] == 2


def test_logs_query_by_request_id(seeded_logs):
    """R7 链路跳转数据面: request_id 精确过滤（/audit 追踪按钮消费）"""
    res = client.get("/v1/logs?minutes=60&request_id=chatcmpl-trace-001", headers=_ADMIN_HEADERS)
    body = res.json()
    assert body["total"] == 1
    assert body["logs"][0]["model"] == "deepseek-v4"
    res_none = client.get("/v1/logs?minutes=60&request_id=chatcmpl-none", headers=_ADMIN_HEADERS)
    assert res_none.json()["total"] == 0


# ── BL-A2: /v1/usage/timeline ──────────────────────────────────────


def test_usage_timeline_buckets(seeded_logs):
    res = seeded_logs.get(
        "/v1/usage/timeline?minutes=60&step_minutes=30&group_by=model",
        headers=_ADMIN_HEADERS,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["group_by"] == "model"
    assert set(body["series"].keys()) == {"glm-4-flash", "deepseek-v4"}
    glm = body["series"]["glm-4-flash"]
    assert sum(p["calls"] for p in glm) == 2
    assert sum(p["tokens"] for p in glm) == 1780
    # 总计与分桶一致
    assert body["totals"]["calls"] == 3
    assert body["totals"]["tokens"] == 2180
    assert round(body["totals"]["cost_usd"], 2) == 0.4


def test_usage_timeline_total_group(seeded_logs):
    res = seeded_logs.get(
        "/v1/usage/timeline?minutes=60&step_minutes=60&group_by=total",
        headers=_ADMIN_HEADERS,
    )
    body = res.json()
    assert list(body["series"].keys()) == ["total"]
    assert sum(p["calls"] for p in body["series"]["total"]) == 3


def test_usage_timeline_invalid_group():
    res = client.get("/v1/usage/timeline?group_by=hacker", headers=_ADMIN_HEADERS)
    assert res.status_code == 422


# ── BL-A3: /v1/models/summary cost 真实化 ──────────────────────────


def test_models_summary_cost_real(seeded_logs):
    res = seeded_logs.get("/v1/models/summary", headers=_ADMIN_HEADERS)
    assert res.status_code == 200
    body = res.json()
    assert round(body["cost_usd"], 2) == 0.4  # 0.25 + 0.05 + 0.10（替换原硬编码 0.0）


# ── BL-A4: /v1/admin/alerts ────────────────────────────────────────


def test_admin_alerts_shape():
    res = client.get("/v1/admin/alerts", headers=_ADMIN_HEADERS)
    assert res.status_code == 200
    body = res.json()
    assert "alerts" in body and "total" in body
    for a in body["alerts"]:
        assert a["source"] in ("upstream", "registry")
        assert a["level"] in ("critical", "warning", "info")
        assert a["title"]


def test_admin_alerts_level_filter():
    res = client.get("/v1/admin/alerts?level=critical", headers=_ADMIN_HEADERS)
    body = res.json()
    assert all(a["level"] == "critical" for a in body["alerts"])


def test_admin_alerts_requires_admin():
    # 非 admin key（普通 API key）→ /v1/admin/** 闸门 403
    res = client.get("/v1/admin/alerts", headers=_HEADERS)
    assert res.status_code == 403
