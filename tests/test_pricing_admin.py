#!/usr/bin/env python3
"""
@file test_pricing_admin.py
@description 协同事务价格表管理端点测试——列表/upsert/RBAC/运行时覆盖生效
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-26
@tags [test,pricing,admin,vk,integration]

TASK_TYPE_PRICES 为模块级内存态：fixture 备份/恢复防跨用例污染；
admin 端点 RBAC（ADMIN_API_KEYS）与 422 校验面一并覆盖。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))
# 密钥读 conftest 统一注入值（收集顺序加固）
_TEST_API_KEY = os.environ["API_KEYS"]
_TEST_ADMIN_KEY = os.environ["ADMIN_API_KEYS"]

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import pricing  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture()
def pricing_table_clean():
    """TASK_TYPE_PRICES 快照恢复（运行时 upsert 会改模块级内存态）。"""
    snapshot = dict(pricing.TASK_TYPE_PRICES)
    yield
    pricing.TASK_TYPE_PRICES.clear()
    pricing.TASK_TYPE_PRICES.update(snapshot)


@pytest.fixture()
def client():
    return TestClient(app)


def _admin():
    return {"X-API-Key": _TEST_ADMIN_KEY}


def _normal():
    return {"X-API-Key": _TEST_API_KEY}


class TestTaskTypePricingAdmin:
    def test_list_contains_builtin_types(self, client, pricing_table_clean):
        """GET 列表：含内置 8 任务类型价目。"""
        resp = client.get("/v1/admin/pricing/task-types", headers=_admin())
        assert resp.status_code == 200
        types = resp.json()["task_types"]
        assert types["data_analysis"] == 0.002
        assert types["code_review"] == 0.002
        assert len(types) >= 8

    def test_upsert_updates_cost_immediately(self, client, pricing_table_clean):
        """PUT 更新单价 → 内存即时生效（task_cost 与 X-A2A-Cost 取值源）。"""
        resp = client.put(
            "/v1/admin/pricing/task-types/data_analysis",
            json={"price_usd": 0.005},
            headers=_admin(),
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] is True
        assert isinstance(resp.json()["persisted"], bool)  # PG 双写结果（测试环境允许 False）
        assert pricing.task_cost("data_analysis") == 0.005
        listed = client.get("/v1/admin/pricing/task-types", headers=_admin()).json()
        assert listed["task_types"]["data_analysis"] == 0.005

    def test_upsert_new_task_type_preset(self, client, pricing_table_clean):
        """PUT 未知类型：可预置（新 task_type 上线即计价，无需发版）。"""
        resp = client.put(
            "/v1/admin/pricing/task-types/future_skill",
            json={"price_usd": 0.01},
            headers=_admin(),
        )
        assert resp.status_code == 200
        assert pricing.task_cost("future_skill") == 0.01

    def test_upsert_negative_price_422(self, client, pricing_table_clean):
        """负单价 → 422（Field ge=0 拦截）。"""
        resp = client.put(
            "/v1/admin/pricing/task-types/data_analysis",
            json={"price_usd": -0.1},
            headers=_admin(),
        )
        assert resp.status_code == 422

    def test_normal_key_forbidden_403(self, client, pricing_table_clean):
        """推理面密钥访问管理端点 → 403 admin privileges required。"""
        resp = client.get("/v1/admin/pricing/task-types", headers=_normal())
        assert resp.status_code == 403


class _BrokenEngine:
    """begin() 即抛（模拟 DB 不可达/表未迁移）。"""

    def begin(self):
        raise RuntimeError("db unavailable")


class TestTaskPricePersistence:
    def test_upsert_persisted_db_unavailable_memory_still_applies(self, monkeypatch, pricing_table_clean):
        """PG 不可达：双写降级——内存生效 + 返回 False（提示补迁移）。"""
        import app.db as db_mod

        monkeypatch.setattr(db_mod, "engine", _BrokenEngine())
        import asyncio

        ok = asyncio.run(pricing.upsert_task_price_persisted("gray_type", 0.007))
        assert ok is False
        assert pricing.task_cost("gray_type") == 0.007  # 内存已生效

    def test_load_from_db_failure_returns_zero(self, monkeypatch, pricing_table_clean):
        """启动加载 DB 不可达 → 返回 0 且不抛（内置表兜底，不阻断启动）。"""
        import app.db as db_mod

        monkeypatch.setattr(db_mod, "engine", _BrokenEngine())
        import asyncio

        assert asyncio.run(pricing.load_task_prices_from_db()) == 0
        assert pricing.task_cost("data_analysis") == 0.002  # 内置默认未被破坏

    def test_load_from_db_overrides_memory(self, monkeypatch, pricing_table_clean):
        """启动加载成功 → 表值覆盖内存默认（多实例价格一致性来源）。"""
        import asyncio

        import app.db as db_mod

        class _StubRows:
            def fetchall(self):
                return [("data_analysis", 0.009), ("new_skill", 0.02)]

        class _StubConn:
            async def execute(self, _sql):
                return _StubRows()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

        class _StubEngine:
            def begin(self):
                ctx = _StubConn()
                # engine.begin() 返回异步上下文管理器
                return ctx

        monkeypatch.setattr(db_mod, "engine", _StubEngine())
        assert asyncio.run(pricing.load_task_prices_from_db()) == 2
        assert pricing.task_cost("data_analysis") == 0.009
        assert pricing.task_cost("new_skill") == 0.02
