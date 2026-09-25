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

# ── 关键配置统一注入（收集顺序加固，2026-09-26）──────────────────────
# 历史：各 integration 测试文件头部各自注入随机密钥，收集顺序决定 settings 初值，
# 合跑时后续文件自身密钥错配 → 401/403（对照证据见 docs/0379-world-yyc3-expert-20260925/02）。
# 现约定：pytest 专用静态值在此唯一注入（先于任何 app.config 导入），各测试文件只读不写。
# （值为 pytest 专用占位，非真实凭据；与 test_gateway_api/test_proxy_api 既有静态值一致）
os.environ.update(
    {
        "API_KEYS": "test-key-1",
        "ADMIN_API_KEYS": "runner-test-key-1",
        "JWT_SECRET_KEY": "pytest-only-secret",
        "POSTGRES_PASSWORD": "pytest-only-pg",
        "REDIS_PASSWORD": "pytest-only-redis",
        "AGENT_WORKER_ENABLED": "false",  # 内置 Worker 关闭：integration 经 admin 端点驱动
        "A2A_ENABLED": "false",  # A2A 注册/心跳循环关闭：避免测试进程真实 Redis 连接重试
        "A2A_RESULT_CONSUMER_ENABLED": "false",  # 结果消费泵关闭：测试直驱 run_once/reclaim
    }
)

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

# 供 app 层（如 app/api/agent.py）import core.agents（仓库根布局，容器内由 PYTHONPATH=/app 承担）
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


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
