#!/usr/bin/env python3
"""
@file conftest.py
@description pytest 共享夹具——把 core/api 注册为 "app" 包（对齐容器内 core/api→/app/app 映射）
@author: YanYuCloudCube Team <admin@0379.email>
@version: 1.0.0
@date: 2026-09-03
@tags [test,conftest]
"""

import importlib.util
import os
import sys

_API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "core", "api"))

if "app" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "app",
        os.path.join(_API_DIR, "__init__.py"),
        submodule_search_locations=[_API_DIR],
    )
    _pkg = importlib.util.module_from_spec(_spec)
    sys.modules["app"] = _pkg
    _spec.loader.exec_module(_pkg)

# 供测试文件直接 import app.* 时同源
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)


# ── 测试密闭性：缓存旁路（CI 有真 Redis，命中缓存会让请求绕过后端破坏断言）──
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_cache(monkeypatch):
    from app.utils import cache_manager

    async def _no_get(key):
        return None

    async def _no_set(key, value, ttl=None, tags=None):
        return None

    monkeypatch.setattr(cache_manager, "get", _no_get)
    monkeypatch.setattr(cache_manager, "set", _no_set)
