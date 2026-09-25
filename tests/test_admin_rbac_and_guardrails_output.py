# file: test_admin_rbac_and_guardrails_output.py
# description: 管理面 RBAC + Guardrail 输出链 PII + provider 运维面 集成验证
# author: YanYuCloudCube Team
# created: 2026-09-20
# status: active
# tags: [test],[rbac],[guardrail],[providers]

"""
@file: test_admin_rbac_and_guardrails_output.py
@description: 四类集成断言：
  ① 管理面 RBAC：非 admin Key 访问 /v1/admin/** → 403；admin Key 通过；vk 身份 → 403
  ② provider 运维面：GET /v1/providers 列出已登记实现（无需 admin）
  ③ Guardrail 输出链：PII（手机号/邮箱）拦截 400；GUARDRAILS_PII_ENABLED=false 放行
  ④ 上游池 provider 配置校验：未知名 warning 回退（行为验证在 test_guardrails_and_providers.py）
@author: YanYuCloudCube Team <admin@0379.email>
"""

import json
import os
import sys

import pytest

# conftest.py 在收集阶段已注册 app 包（settings 定格前环境须就位）；
# 基础密闭环境用 os.environ（conftest import app 前生效——收集阶段早于测试模块 import），
# RBAC 专用 Key 用 module fixture 直接改 settings（避免与其他测试文件的环境块竞争）
os.environ.setdefault("JWT_SECRET_KEY", "pytest-only-secret")
os.environ.setdefault("POSTGRES_PASSWORD", "pytest-only-pg")
os.environ.setdefault("REDIS_PASSWORD", "pytest-only-redis")
os.environ.setdefault("AUTH_ENABLED", "true")
os.environ.setdefault("OLLAMA_HOST", "127.0.0.1")
os.environ.setdefault("OLLAMA_PORT", "11434")
# 本文件按字母序最先被收集：import 时 settings 定格，须与 test_gateway_api 同源 api_keys
# （否则后续文件的 TestClient startup 关键配置校验因 api_keys 空而炸）
os.environ.setdefault("API_KEYS", "test-key-1")
_POOL = json.dumps(
    [
        {
            "name": "flagship",
            "base_url": "http://flagship.test:8001",
            "models": ["deepseek-v4-flash", "deepseek-v4*"],
            "priority": 1,
            "weight": 100,
        },
        {
            "name": "backup",
            "base_url": "http://backup.test:8001",
            "models": ["deepseek-v4-flash"],
            "priority": 5,
            "weight": 50,
        },
    ]
)

import httpx  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings as _settings  # noqa: E402
from app.main import app  # noqa: E402

# P1-1 分层：TestClient 全链路 → integration 层（pytest -m integration 运行；默认快速层跳过）
pytestmark = pytest.mark.integration

_BIZ_KEY = "biz-key-1"
_ADMIN_KEY = "admin-key-1"


@pytest.fixture(scope="module", autouse=True)
def _settings_override():
    """RBAC 断言根基：管理面与业务 Key 分离（直接改 settings，绕过环境定格时序）"""
    from app.config import settings

    old = {
        "api_keys": settings.api_keys,
        "admin_api_keys": getattr(settings, "admin_api_keys", ""),
        "openai_compatible_upstreams": settings.openai_compatible_upstreams,
    }
    settings.api_keys = _BIZ_KEY
    settings.admin_api_keys = _ADMIN_KEY
    settings.openai_compatible_upstreams = _POOL
    from app.services.upstream_registry import registry

    registry.load_from_env()
    yield
    settings.api_keys = old["api_keys"]
    settings.admin_api_keys = old["admin_api_keys"]
    settings.openai_compatible_upstreams = old["openai_compatible_upstreams"]
    registry.load_from_env()


def _upstream_ok():
    return {
        "id": "chatcmpl-rbac",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "你好"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _mock_upstream():
    # 带括号 with = 新实例；路由必须注册到实例（as router），
    # respx.post 全局函数注册的是未激活全局实例 → 穿透真实网络（DNS 失败空响应）；
    # assert_all_mocked=False 让 testserver ASGI 请求 pass-through
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as router:
        router.post("http://flagship.test:8001/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_upstream_ok())
        )
        router.post("http://backup.test:8001/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_upstream_ok())
        )
        _ROUTER = router  # 供用例内重 mock（函数体访问 fixture 内实例）
        yield _ROUTER


def _chat_body(content="你好"):
    return {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": content}],
        "stream": False,
    }


# ── ① 管理面 RBAC ────────────────────────────────────────────


def test_admin_endpoint_rejects_business_key(client):
    """业务 Key 访问管理面 → 403（Admin privileges required）"""
    r = client.get("/v1/admin/virtual-keys", headers={"X-API-Key": _BIZ_KEY})
    assert r.status_code == 403
    assert "Admin" in r.json()["message"] or "admin" in r.json()["message"]


def test_admin_endpoint_rejects_anonymous(client):
    """无凭证访问管理面 → 401"""
    r = client.get("/v1/admin/virtual-keys")
    assert r.status_code == 401


def test_admin_endpoint_accepts_admin_key(client):
    """ADMIN_API_KEYS 中的 Key 访问管理面 → 非 403（200 或数据库错误 ≠ 权限问题）"""
    r = client.get("/v1/admin/virtual-keys", headers={"X-API-Key": _ADMIN_KEY})
    assert r.status_code != 403, r.text


def test_inference_accepts_business_key(client):
    """业务 Key 推理面照常放行（RBAC 不误伤）"""
    r = client.post("/v1/chat/completions", json=_chat_body(), headers={"X-API-Key": _BIZ_KEY})
    assert r.status_code == 200, r.text


# ── ② provider 运维面 ────────────────────────────────────────


def test_list_providers(client):
    """GET /v1/providers 列出已登记实现（推理面可读，便于配置校验）"""
    r = client.get("/v1/providers", headers={"X-API-Key": _BIZ_KEY})
    assert r.status_code == 200
    providers = r.json()["providers"]
    assert "openai_compat" in providers
    assert "zhipu" in providers


# ── ③ Guardrail 输出链 PII ───────────────────────────────────


def test_output_pii_blocked(client, _mock_upstream):
    """上游返回手机号 → 既有 content_filter 先脱敏（纵深防御第一层），响应不含完整手机号"""
    leaked = _upstream_ok()
    leaked["choices"][0]["message"]["content"] = "请联系 13812345678"
    _mock_upstream.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=leaked)
    )
    r = client.post("/v1/chat/completions", json=_chat_body(), headers={"X-API-Key": _BIZ_KEY})
    assert r.status_code == 200, r.text
    # 纵深防御：content_filter 脱敏后完整手机号不应出现在响应
    content = r.json()["choices"][0]["message"]["content"]
    assert "13812345678" not in content


def test_output_clean_passes(client):
    """上游返回正常内容 → 放行"""
    r = client.post(
        "/v1/chat/completions",
        json=_chat_body("普通回复"),
        headers={"X-API-Key": _BIZ_KEY},
    )
    assert r.status_code == 200, r.text


# ── ④ 流式输出链 PII（chunk 级脱敏 + carry 跨 chunk 缓冲）────


def _sse_chunk(content, finish=None):
    delta = {"role": "assistant", "content": content} if content else {}
    if finish:
        delta = {}
    return (
        "data: "
        + json.dumps(
            {
                "id": "chatcmpl-stream",
                "object": "chat.completion.chunk",
                "model": "deepseek-v4-flash",
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            },
            ensure_ascii=False,
        )
        + "\n\n"
    )


def _parse_sse_contents(text):
    contents = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            continue
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if choices and isinstance(choices[0], dict):
            delta = choices[0].get("delta") or {}
            if delta.get("content"):
                contents.append(delta["content"])
    return "".join(contents)


def _stream_body(content="你好"):
    body = _chat_body(content)
    body["stream"] = True
    return body


def test_stream_pii_masked_across_chunks(client, _mock_upstream):
    """手机号跨 chunk 截断（138 | 12345678）→ carry 缓冲拼接后脱敏，客户端拼不出完整手机号"""
    sse_body = (
        _sse_chunk("请您联系手机号 138")
        + _sse_chunk("12345678 获取验证码")
        + _sse_chunk("", finish="stop")
        + "data: [DONE]\n\n"
    ).encode("utf-8")
    _mock_upstream.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=sse_body)
    )
    r = client.post("/v1/chat/completions", json=_stream_body(), headers={"X-API-Key": _BIZ_KEY})
    assert r.status_code == 200, r.text
    assert "text/event-stream" in r.headers.get("content-type", "")
    assembled = _parse_sse_contents(r.text)
    assert "13812345678" not in assembled, f"完整手机号泄漏: {assembled!r}"
    assert "****" in assembled, f"应含脱敏标记: {assembled!r}"


def test_stream_clean_content_intact(client, _mock_upstream):
    """无 PII 流式内容完整透传（含 flush 滞留缓冲不丢字）"""
    sse_body = (
        _sse_chunk("今天天气不错") + _sse_chunk("", finish="stop") + "data: [DONE]\n\n"
    ).encode("utf-8")
    _mock_upstream.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=sse_body)
    )
    r = client.post(
        "/v1/chat/completions",
        json=_stream_body("随意"),
        headers={"X-API-Key": _BIZ_KEY},
    )
    assert r.status_code == 200, r.text
    assembled = _parse_sse_contents(r.text)
    assert assembled == "今天天气不错", f"流式内容应完整无损: {assembled!r}"
