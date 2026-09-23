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


# ── 云适配器空 Key 前置校验（OBS-2/OBS-3：三适配器双入口参数化矩阵）──

from app.errors.exceptions import APIError  # noqa: E402

_CLOUD_ADAPTERS = [
    pytest.param("zhipu", "ZHIPU_API_KEY", "zhipu_api_key", "glm-4", id="zhipu"),
    pytest.param("deepseek", "DEEPSEEK_API_KEY", "deepseek_api_key", "deepseek-chat", id="deepseek"),
    pytest.param("openai", "OPENAI_API_KEY", "openai_api_key", "gpt-4", id="openai"),
]


@pytest.mark.anyio
@pytest.mark.parametrize("module_name,env_name,setting_field,model", _CLOUD_ADAPTERS)
async def test_cloud_adapter_empty_key_raises_401(
    monkeypatch, module_name, env_name, setting_field, model
):
    """三云适配器同构契约：空 Key 双入口均抛 APIError(401)，消息含 env 名（断言面=声明面）

    deepseek 原为 502 + 模块级快照；openai 原无任何校验（空 Key 直拼非法头）。
    """
    import importlib

    adapter = importlib.import_module(f"app.services.{module_name}")

    monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setattr(adapter.settings, setting_field, "")

    # 同步入口
    with pytest.raises(APIError) as ei:
        await adapter.chat_completion(model=model, messages=[{"role": "user", "content": "hi"}])
    assert ei.value.status_code == 401, f"{module_name} 同步入口应为 401（原 deepseek 502/openai 无校验）"
    assert env_name in ei.value.message, "错误消息须含 env 变量名（可自愈排障契约）"

    # 流式入口（async 生成器首次迭代时触发校验）
    with pytest.raises(APIError) as ei2:
        async for _ in adapter.chat_completion_stream(
            model=model, messages=[{"role": "user", "content": "hi"}]
        ):
            pass
    assert ei2.value.status_code == 401


@pytest.mark.anyio
async def test_cloud_adapter_key_runtime_reload(monkeypatch):
    """OBS-2 附带修复验证：Key 延迟读取（原模块级快照 import 时定格，运行时设 env 不生效）"""
    from app.services import deepseek

    monkeypatch.setattr(deepseek.settings, "deepseek_api_key", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-runtime-loaded")
    assert deepseek._get_deepseek_key() == "sk-runtime-loaded"


def test_zhipu_empty_key_raises_401():
    """ZHIPU_API_KEY 空时双入口抛 401 明确错误（原 'Bearer ' 非法头 → 模糊 502）

    OBS-3 后保留为薄兼容壳：矩阵用例 test_cloud_adapter_empty_key_raises_401[zhipu]
    已完整覆盖（双入口 + env 名断言），此名保留以维持 v5 测试报告的历史引用。
    """
    from app.services import zhipu

    assert callable(zhipu._ensure_key)  # 契约锚点：入口存在（行为断言见矩阵用例）
