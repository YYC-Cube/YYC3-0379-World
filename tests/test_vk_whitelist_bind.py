# file: test_vk_whitelist_bind.py
# description: vk model_whitelist 跨方言绑定回归锚（生产 vk_create DataError 修复 2026-09-27）
# author: YanYuCloudCube Team <admin@0379.email>
# created: 2026-09-27
# status: active
# tags: [test],[vk],[regression]

"""
@file: test_vk_whitelist_bind.py
@description: virtual_keys.model_whitelist 列为 PG TEXT[]——写入必须直绑 list
  （JSON 串 → asyncpg DataError，生产 vk 创建链曾因此全阻）：
  ① PG 方言：vk_create / vk_update_fields 绑定 list
  ② sqlite 兜底（本地 e2e TEXT 列）：绑定 JSON 串
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from app.services import virtual_key_manager as vkm  # noqa: E402

_captured: list = []


class _Dialect:
    name = "postgresql"


class _Bind:
    dialect = _Dialect()


class _Result:
    rowcount = 1

    def scalar(self, stmt=None, params=None):
        return "vk-hash-1"


class _Session:
    bind = _Bind()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt, params=None):
        if params and "wl" in params:
            _captured.append(params["wl"])
        return _Result()

    async def commit(self):
        return None


@pytest.fixture(autouse=True)
def _stubs(monkeypatch):
    from app import db as app_db

    async def _fake_set(*a, **k):
        return True

    async def _fake_delete(*a, **k):
        return True

    monkeypatch.setattr(app_db, "async_session", lambda: _Session())
    monkeypatch.setattr(vkm.redis_client, "set", _fake_set)
    monkeypatch.setattr(vkm.redis_client, "delete", _fake_delete)
    _captured.clear()


def test_vk_create_binds_list_on_pg(monkeypatch):
    """① PG 方言：默认白名单绑 []（list），非 JSON 串"""
    rec = asyncio.run(vkm.vk_create(name="t", metadata=None))
    assert rec["key"].startswith("vk-")
    assert _captured and isinstance(_captured[0], list) and _captured[0] == []


def test_vk_update_binds_list_on_pg(monkeypatch):
    """① PG 方言：白名单更新绑 list"""
    changed = asyncio.run(vkm.vk_update_fields("id-1", model_whitelist=["m1", "m2"]))
    assert changed is True
    assert _captured and _captured[0] == ["m1", "m2"]


def test_vk_create_binds_json_str_on_sqlite(monkeypatch):
    """② sqlite 兜底：TEXT 列绑 JSON 串（读取侧 json.loads 兼容）"""
    from app import db as app_db

    class _SqliteDialect:
        name = "sqlite"

    class _SqliteBind:
        dialect = _SqliteDialect()

    class _SqliteSession(_Session):
        bind = _SqliteBind()

    monkeypatch.setattr(app_db, "async_session", lambda: _SqliteSession())
    asyncio.run(vkm.vk_create(name="t", model_whitelist=["m1"]))
    assert _captured and isinstance(_captured[0], str)
    assert json.loads(_captured[0]) == ["m1"]


def test_flush_batch_updates_vk_spent_usd(monkeypatch):
    """③ 记账落库必须增量 UPDATE virtual_keys.spent_usd（否则重启后预算闸门从 PG 读旧值）"""
    from app import db as app_db

    stmts: list = []

    class _CapSession(_Session):
        async def execute(self, stmt, params=None):
            stmts.append((str(stmt), params))
            return _Result()

    monkeypatch.setattr(app_db, "async_session", lambda: _CapSession())
    asyncio.run(
        vkm.vk_manager._flush_batch(
            [{"key_id": "kid-1", "cost_usd": 0.002, "model": "a2a", "capability": "agent"}]
        )
    )
    updates = [s for s, _ in stmts if "UPDATE virtual_keys" in s and "spent_usd" in s]
    assert updates, "flush 必须含 spent_usd 增量 UPDATE"
    upd_params = next(p for s, p in stmts if "UPDATE virtual_keys" in s)
    assert upd_params == {"cost": 0.002, "kid": "kid-1"}
