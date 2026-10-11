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


# ── fakeredis 全量密闭化（P2-1 闭环，2026-10-11 深度审计）────────────────
# 历史：集成层依赖 CI 的 docker Redis（主机名 redis 可解析），本机/外部贡献者
# 12 个用例必挂且每个 Redis 触点白白消耗 30-60s 连接重试（全量 28 分钟）。
# 现以 fakeredis（进程内内存实现）统一替换各模块绑定的 redis_client 引用，
# 集成层在任何环境可跑且语义与 CI 真 Redis 对齐（CI 绿 = 本机绿）。
# 注意：各模块经 `from app.cache import redis_client` 持有独立引用，必须逐一补丁。
import importlib  # noqa: E402

_REDIS_BOUND_MODULES = (
    "app.cache",  # 源头：get_redis() / get_cached 系列
    "app.middleware.rate_limit",
    "app.api.video_tasks",
    "app.api.agent",
    "app.api.model_registry",
    "app.services.a2a_protocol",
    "app.services.virtual_key_manager",
    "app.services.model_registry_svc",
)


@pytest.fixture(autouse=True)
def _hermetic_redis(monkeypatch):
    """每个测试注入独立 FakeRedis 实例，替换所有已绑定的 redis_client 引用。

    CI 例外：GitHub Actions 的 CI=true 环境保留真 Redis 服务（docker compose），
    维持「对真实 Redis 集成验证」的覆盖面；本机/外部贡献者无 Redis 时走 fakeredis，
    语义对齐（已用命令集验证：string/zset/set/hash/pipeline/incr/lpush/pubsub）。
    测试若需自定义 Redis 行为（故障桩/NoopRedis），在测试内二次
    monkeypatch 本夹具注入的实例即可（后写覆盖先生，与既有范式兼容）。"""
    if os.environ.get("CI") == "true":
        yield None  # CI：真 Redis，不替换
        return

    from fakeredis.aioredis import FakeRedis

    fake = FakeRedis(decode_responses=True)
    for name in _REDIS_BOUND_MODULES:
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        if hasattr(mod, "redis_client"):
            monkeypatch.setattr(mod, "redis_client", fake)
    yield fake
