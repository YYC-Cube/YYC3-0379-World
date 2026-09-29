#!/usr/bin/env python3
"""
@file test_usage_summary.py
@description 全局用量聚合测试——usage_summary 分组白名单/聚合语义 + admin 端点 RBAC/422
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-28
@tags [test,usage,summary,billing,admin]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

os.environ.setdefault("API_KEYS", "test-key-1")

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import virtual_key_manager as vkm  # noqa: E402

client = TestClient(app)

_HEADERS = {"X-API-Key": os.environ.get("API_KEYS", "test-key-1")}
# conftest 注入 ADMIN_API_KEYS=runner-test-key-1（/v1/admin/** 闸门）
_ADMIN_HEADERS = {"X-API-Key": os.environ.get("ADMIN_API_KEYS", "runner-test-key-1")}

# 看板回放数据：两组（model 分组视角），含 NULL cost 行（容错路径）
_ROWS = [
    {
        "grp": "deepseek-v4-flash",
        "calls": 10,
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "cost_usd": 0.25,
        "avg_latency_ms": 800.4,
    },
    {
        "grp": "content_validation",
        "calls": 4,
        "prompt_tokens": 200,
        "completion_tokens": 80,
        "cost_usd": 0.016,
        "avg_latency_ms": 1200.0,
    },
    {
        "grp": "qwen3-reranker-8b",
        "calls": 1,
        "prompt_tokens": 50,
        "completion_tokens": 0,
        "cost_usd": None,
        "avg_latency_ms": None,
    },
]


class _FakeResult:
    captured_sql: str = ""
    captured_params: dict = {}

    def mappings(self):
        return _ROWS


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, sql, params=None):
        _FakeResult.captured_sql = str(sql)
        _FakeResult.captured_params = dict(params or {})
        return _FakeResult()


@pytest.fixture()
def _stub_session(monkeypatch):
    import app.db as db_mod

    monkeypatch.setattr(db_mod, "async_session", lambda: _FakeSession())


# ── svc 层（快层，桩替 DB）──────────────────────────────────
def test_usage_summary_groups_and_totals(_stub_session):
    out = asyncio.run(vkm.usage_summary(days=7, group_by="model"))
    assert out["group_by"] == "model"
    assert out["total_calls"] == 15
    assert abs(out["total_cost_usd"] - 0.266) < 1e-9
    assert out["groups"][0]["grp"] == "deepseek-v4-flash"  # cost 降序
    null_row = out["groups"][2]
    assert (
        null_row["cost_usd"] == 0.0 and null_row["avg_latency_ms"] == 0.0
    ), "NULL 容错归零"


def test_usage_summary_group_whitelist(_stub_session):
    with pytest.raises(ValueError, match="invalid group_by"):
        asyncio.run(vkm.usage_summary(group_by="cost_usd; DROP TABLE"))
    # 白名单列生效（key → key_id 列）
    asyncio.run(vkm.usage_summary(group_by="key"))
    assert (
        "key_id" in _FakeResult.captured_sql
        and "GROUP BY key_id" in _FakeResult.captured_sql
    )


def test_usage_summary_key_filter_in_where(_stub_session):
    asyncio.run(vkm.usage_summary(group_by="model", key_id="vk-123"))
    assert "key_id = :kid" in _FakeResult.captured_sql
    assert _FakeResult.captured_params.get("kid") == "vk-123"


# ── API 层（integration：TestClient 全链路）─────────────────
@pytest.mark.integration
def test_usage_summary_route_admin_ok(_stub_session):
    r = client.get(
        "/v1/admin/usage/summary?days=7&group_by=capability", headers=_ADMIN_HEADERS
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["group_by"] == "capability" and "groups" in body and "total_cost_usd" in body


@pytest.mark.integration
def test_usage_summary_route_rejects_plain_key(_stub_session):
    """普通 API Key 不得过 /v1/admin/** RBAC 闸门"""
    r = client.get("/v1/admin/usage/summary", headers=_HEADERS)
    assert r.status_code == 403


@pytest.mark.integration
def test_usage_summary_route_invalid_group_422(_stub_session):
    r = client.get("/v1/admin/usage/summary?group_by=nope", headers=_ADMIN_HEADERS)
    assert r.status_code == 422
