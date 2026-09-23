# file: test_guardrails_and_providers.py
# description: Guardrail 云审核 + provider 配置化行为验证（respx mock 外部服务）
# author: YanYuCloudCube Team
# created: 2026-09-20
# status: active
# tags: [test],[guardrail],[providers]

"""
@file: test_guardrails_and_providers.py
@description: 三类行为验证：
  ① guardrails 云审核检查器（flagged 拦截 / 未命中放行 / 服务不可达放行 / 未配置自跳过）
  ② providers registry（zhipu reasoning_content 折叠 / 未知名回退）
  ③ upstream provider 配置化（Upstream.provider 字段解析 + 客户端 endpoint 委托）
@author: YanYuCloudCube Team <admin@0379.email>
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import respx  # noqa: E402
from httpx import Response  # noqa: E402

# ── Guardrail 云审核 ──────────────────────────────────────────


def _reload_guardrails(cloud_url: str = "", cloud_key: str = ""):
    """按环境变量重载 guardrails 模块（模块级常量在 import 时定格）"""
    import importlib
    import os

    if cloud_url:
        os.environ["GUARDRAILS_CLOUD_URL"] = cloud_url
        os.environ["GUARDRAILS_CLOUD_KEY"] = cloud_key
    else:
        os.environ.pop("GUARDRAILS_CLOUD_URL", None)
        os.environ.pop("GUARDRAILS_CLOUD_KEY", None)
    import app.services.guardrails as g

    importlib.reload(g)
    return g


@pytest.mark.anyio
async def test_cloud_moderation_not_configured_passes():
    """未配置云审核（缺省）→ 检查器直接放行，零网络调用"""
    g = _reload_guardrails()
    assert await g._check_cloud_moderation("任何内容") is None


@pytest.mark.anyio
async def test_cloud_moderation_flagged_blocks():
    """云审核返回 flagged=true → 拦截并携带 reason"""
    g = _reload_guardrails("http://moderation.test/v1/check", "sk-test")
    with respx.mock:
        respx.post("http://moderation.test/v1/check").mock(
            return_value=Response(200, json={"flagged": True, "reason": "violence"})
        )
        verdict = await g._check_cloud_moderation("bad text")
    assert verdict is not None and "violence" in verdict


@pytest.mark.anyio
async def test_cloud_moderation_clean_passes():
    """云审核返回 flagged=false → 放行"""
    g = _reload_guardrails("http://moderation.test/v1/check", "sk-test")
    with respx.mock:
        respx.post("http://moderation.test/v1/check").mock(
            return_value=Response(200, json={"flagged": False})
        )
        assert await g._check_cloud_moderation("good text") is None


@pytest.mark.anyio
async def test_cloud_moderation_unreachable_passes():
    """审核服务不可达 → 按放行（可用性优先，不阻塞推理）"""
    g = _reload_guardrails("http://unreachable.test:1/v1/check", "sk-test")
    assert await g._check_cloud_moderation("hello") is None


# ── providers registry ────────────────────────────────────────


def test_zhipu_provider_folds_reasoning():
    """zhipu transform_response：R+C → 拼接；R only → content=R"""
    from app.services.providers.registry import get_provider

    p = get_provider("zhipu")
    raw = {
        "choices": [
            {"message": {"reasoning_content": "思考", "content": "答案"}},
            {"message": {"reasoning_content": "仅思考"}},
        ]
    }
    out = p.transform_response(raw)
    assert out["choices"][0]["message"]["content"] == "思考\n\n答案"
    assert out["choices"][1]["message"]["content"] == "仅思考"


def test_unknown_provider_falls_back():
    """未知名 → 回退 openai_compat（绝不抛异常阻断推理）"""
    from app.services.providers.base import OpenAICompatProvider
    from app.services.providers.registry import get_provider

    p = get_provider("no-such-provider")
    assert isinstance(p, OpenAICompatProvider)


def test_endpoint_matches_client_path():
    """provider endpoint 与 openai_compatible 客户端既有路径一致（/v1/chat/completions）"""
    from app.services.providers.registry import get_provider

    assert (
        get_provider("openai_compat").endpoint("http://u:8001", "m", False)
        == "http://u:8001/v1/chat/completions"
    )


# ── upstream provider 配置化 ──────────────────────────────────


def test_upstream_provider_field_parsed():
    """OPENAI_COMPATIBLE_UPSTREAMS 的 provider 字段解析进 Upstream"""
    import json

    from app.config import settings
    from app.services.upstream_registry import UpstreamRegistry

    raw = json.dumps(
        [
            {"name": "zgw", "base_url": "http://zgw.test:8000", "models": ["glm-*"], "provider": "zhipu"},
            {"name": "plain", "base_url": "http://plain.test:8000", "models": ["m1"]},
        ]
    )
    r = UpstreamRegistry()
    old = settings.openai_compatible_upstreams
    try:
        settings.openai_compatible_upstreams = raw
        r.load_from_env()
    finally:
        settings.openai_compatible_upstreams = old
    assert r.upstreams["zgw"].provider == "zhipu"
    assert r.upstreams["plain"].provider == "openai_compat"  # 缺省回退
