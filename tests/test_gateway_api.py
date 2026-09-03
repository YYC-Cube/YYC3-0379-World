#!/usr/bin/env python3
"""
@file test_gateway_api.py
@description 网关标准 pytest——TestClient + respx 全 mock，零网络依赖
@author: YanYuCloudCube Team <admin@0379.email>
@version: 2.0.0
@date: 2026-09-03
@tags [test,gateway,api,router,breaker]

覆盖：健康检查、认证、三段式路由（云前缀/上游池/Ollama 兜底）、
上游降级链、备用地址切换、熔断摘除、响应头契约、观测端点。
"""

import json
import os
import sys

# ── 环境必须在 import app 之前就位 ──────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))
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
os.environ.update(
    {
        "API_KEYS": "test-key-1",
        "JWT_SECRET_KEY": "pytest-only-secret",
        "POSTGRES_PASSWORD": "pytest-only-pg",
        "REDIS_PASSWORD": "pytest-only-redis",
        "AUTH_ENABLED": "true",
        "OPENAI_COMPATIBLE_UPSTREAMS": _POOL,
    }
)

import time  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from app.main import app  # noqa: E402
from app.services.upstream_registry import registry  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _pool_context():
    """每个测试函数前：本文件的池写入 settings 并重载 registry（跨文件互不污染）"""
    from app.config import settings as _settings

    _settings.openai_compatible_upstreams = _POOL
    registry.load_from_env()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _auth():
    return {"X-API-Key": "test-key-1"}


def _chat_body(model="deepseek-v4-flash"):
    return {
        "model": model,
        "messages": [{"role": "user", "content": "用一句话介绍你自己"}],
        "stream": False,
        "max_tokens": 32,
        "user_id": "pytest",
    }


def _upstream_ok(content="你好，旗舰在线", model="deepseek-v4-flash"):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
    }


# ── 基础：健康与认证 ────────────────────────────────────────


def test_health_no_auth(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_chat_requires_auth(client):
    r = client.post("/v1/chat/completions", json=_chat_body())
    assert r.status_code in (401, 403)


def test_chat_bad_key(client):
    r = client.post("/v1/chat/completions", json=_chat_body(), headers={"X-API-Key": "wrong"})
    assert r.status_code in (401, 403)


# ── 路由：上游池 ────────────────────────────────────────────


@respx.mock
def test_chat_upstream_pool_route(client):
    """旗舰模型 → 上游池 flagship，响应头披露服务者"""
    route = respx.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_upstream_ok())
    )
    r = client.post("/v1/chat/completions", json=_chat_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert route.called
    body = r.json()
    assert body["choices"][0]["message"]["content"] == "你好，旗舰在线"
    assert r.headers.get("x-yyc3-upstream") == "flagship"
    assert "x-yyc3-degraded" not in r.headers


@respx.mock
def test_chat_unknown_model_falls_to_ollama(client):
    """未匹配上游池的模型 → Ollama 兜底（mock Ollama 地址）"""
    from app.config import settings

    ollama_url = f"http://{settings.ollama_host}:{settings.ollama_port}/api/chat"
    respx.post(ollama_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "local"},
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            },
        )
    )
    r = client.post(
        "/v1/chat/completions",
        json=_chat_body(model="some-unknown-model"),
        headers=_auth(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["choices"][0]["message"]["content"] == "local"


# ── 降级链与备用地址 ────────────────────────────────────────


@respx.mock
def test_degraded_chain_and_header(client):
    """旗舰 500 → 降级到 backup，X-YYC3-Degraded 披露失败链"""
    registry.load_from_env()  # 确保池为 _POOL
    respx.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="boom")
    )
    ok = respx.post("http://backup.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_upstream_ok(content="backup served"))
    )
    r = client.post("/v1/chat/completions", json=_chat_body(), headers=_auth())
    assert r.status_code == 200, r.text
    assert ok.called
    assert r.headers.get("x-yyc3-degraded") == "flagship"


@respx.mock
def test_fallback_url_address_switch(client):
    """base_url 失败 → 同一上游 fallback_url 接管（QSFP 主 / Tailscale 备语义）"""
    try:
        from app.config import settings as _settings

        _settings.openai_compatible_upstreams = json.dumps(
            [
                {
                    "name": "solo",
                    "base_url": "http://primary.test:8001",
                    "fallback_url": "http://secondary.test:8001",
                    "models": ["deepseek-v4-flash"],
                    "priority": 1,
                }
            ]
        )
        registry.load_from_env()
        respx.post("http://primary.test:8001/v1/chat/completions").mock(
            return_value=httpx.Response(502, text="primary down")
        )
        ok = respx.post("http://secondary.test:8001/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=_upstream_ok(content="via secondary"))
        )
        r = client.post("/v1/chat/completions", json=_chat_body(), headers=_auth())
        assert r.status_code == 200, r.text
        assert ok.called
    finally:
        from app.config import settings as _settings

        _settings.openai_compatible_upstreams = _POOL
        registry.load_from_env()


# ── 熔断器 ──────────────────────────────────────────────────


@respx.mock
def test_circuit_breaker_opens_and_falls_back():
    """旗舰连续失败 3 次 → 熔断 OPEN → select 直选 backup，旗舰不再被打"""
    registry.load_from_env()
    flag = registry.upstreams["flagship"]
    flag.breaker_state = "closed"
    flag.consecutive_failures = 0

    fail = respx.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="breaker test")
    )
    respx.post("http://backup.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_upstream_ok())
    )

    # 三次请求：每次旗舰 500 被记录，backup 兜底成功且带降级头
    with TestClient(app) as c:
        for i in range(3):
            body = _chat_body()
            body["messages"][0]["content"] = f"breaker probe {i}"
            r = c.post("/v1/chat/completions", json=body, headers={"X-API-Key": "test-key-1"})
            assert r.status_code == 200, r.text
            assert r.headers.get("x-yyc3-degraded") == "flagship"
    assert flag.consecutive_failures == 3
    assert flag.breaker_state == "open"

    # 熔断摘除后：select 直接落到 backup 层，旗舰零请求、无降级头
    fail.calls.clear()
    with TestClient(app) as c:
        body = _chat_body()
        body["messages"][0]["content"] = "post-breaker probe"
        r = c.post("/v1/chat/completions", json=body, headers={"X-API-Key": "test-key-1"})
        assert r.status_code == 200, r.text
    assert not fail.called, "熔断摘除后不应再请求旗舰"
    assert r.headers.get("x-yyc3-degraded") is None
    assert r.headers.get("x-yyc3-upstream") == "backup"

    # 半开探测：时间窗过后 available 放行
    import app.services.upstream_registry as ur

    flag.breaker_opened_at -= ur.BREAKER_OPEN_SECONDS + 1
    assert registry.available(flag) is True
    # 还原
    flag.breaker_state = "closed"
    flag.consecutive_failures = 0


# ── 观测端点 ────────────────────────────────────────────────


def test_router_stats_has_pool(client):
    r = client.get("/v1/router/stats", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert "upstream_pool" in data
    names = {u["name"] for u in data["upstream_pool"]}
    assert {"flagship", "backup"} <= names


def test_models_list_includes_upstream(client):
    r = client.get("/v1/models", headers=_auth())
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert "deepseek-v4-flash" in ids


def test_models_stats_real_ewma(client):
    r = client.get("/v1/models/stats", headers=_auth())
    assert r.status_code == 200
    by_id = {m["model_id"]: m for m in r.json()}
    assert "flagship" in by_id  # 上游池真实数据（DB 不可达也不影响）


# ── 补强：流式 / 参数透传 / 熔断恢复 / 灰度开关 ─────────────


@pytest.mark.asyncio
async def test_stream_sse_and_upstream_disclosure(client, monkeypatch):
    """流式：SSE 格式正确、首 chunk 披露 _yyc3_upstream、以 [DONE] 收尾"""
    from app.api import chat as chat_mod

    async def _fake_stream(base_url, model, messages, api_key="", **kw):
        yield {
            "id": "chatcmpl-s",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "你好"},
                    "finish_reason": None,
                }
            ],
        }
        yield {
            "id": "chatcmpl-s",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }

    monkeypatch.setattr(chat_mod.openai_compatible, "chat_completion_stream", _fake_stream)

    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers=_auth(),
        json={**_chat_body(), "stream": True},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers.get("x-yyc3-upstream") == "flagship"
        body = "".join(resp.iter_text())

    lines = [ln for ln in body.split("\n\n") if ln.strip()]
    assert lines[-1] == "data: [DONE]"
    import json as _json

    first = _json.loads(lines[0][6:])
    assert first["choices"][0]["delta"]["content"] == "你好"
    assert first["_yyc3_upstream"] == "flagship"


@respx.mock
def test_params_passthrough_to_upstream(client):
    """上游收到的请求体：model/messages/max_tokens/temperature 原样透传"""
    route = respx.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_upstream_ok())
    )
    body = _chat_body()
    body["max_tokens"] = 77
    body["temperature"] = 0.2
    r = client.post("/v1/chat/completions", json=body, headers=_auth())
    assert r.status_code == 200
    sent = _json_loads(route.calls.last.request.content)
    assert sent["model"] == "deepseek-v4-flash"
    assert sent["messages"][0]["content"].startswith("用一句话")
    assert sent["max_tokens"] == 77
    assert sent["temperature"] == 0.2


def test_router_disabled_falls_to_ollama():
    """ROUTER_ENABLED=false 灰度回退：上游池被绕过，旗舰模型名也走 Ollama"""
    from app.api.chat import _select_backend
    from app.config import settings as _settings
    from app.services import ollama as _ollama

    old = _settings.router_enabled
    try:
        _settings.router_enabled = False
        backend, _, btype = _select_backend("deepseek-v4-flash")
        assert backend is _ollama and btype == "ollama"
    finally:
        _settings.router_enabled = old


def test_breaker_success_closes():
    """熔断 OPEN 后时间窗过 → 半开放行 → 一次成功 → 恢复 CLOSED"""
    import app.services.upstream_registry as ur

    registry.load_from_env()
    flag = registry.upstreams["flagship"]
    try:
        flag.breaker_state = "open"
        flag.breaker_opened_at = time.time() - (ur.BREAKER_OPEN_SECONDS + 1)
        assert registry.available(flag) is True  # half_open 探测放行
        registry.release(flag, 120.0, True)
        assert flag.breaker_state == "closed"
        assert flag.consecutive_failures == 0
    finally:
        flag.breaker_state = "closed"
        flag.consecutive_failures = 0


def _json_loads(raw):
    import json as _json

    return _json.loads(raw)
