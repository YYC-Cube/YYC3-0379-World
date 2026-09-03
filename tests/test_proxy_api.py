#!/usr/bin/env python3
"""
@file test_proxy_api.py
@description 能力代理端点测试——embeddings/rerank/asr/ocr 路由、转换、降级、认证
@author: YanYuCloudCube Team <admin@0379.email>
@version: 1.0.0
@date: 2026-09-03
@tags [test,proxy,embeddings,rerank,asr,ocr]

全部上游经 respx mock，零网络。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

# 能力池：embedding/rerank 各一主一备 + chat（用于隔离断言）
_POOL = json.dumps(
    [
        {
            "name": "flagship",
            "base_url": "http://flagship.test:8001",
            "models": ["deepseek-v4-flash"],
            "priority": 1,
        },
        {
            "name": "embed-main",
            "base_url": "http://embed-main.test:8100",
            "models": ["qwen3-embedding-0.6b"],
            "capability": "embedding",
            "priority": 1,
        },
        {
            "name": "embed-backup",
            "base_url": "http://embed-backup.test:8100",
            "models": ["*"],
            "capability": "embedding",
            "priority": 5,
        },
        {
            "name": "rerank-main",
            "base_url": "http://rerank.test:8101",
            "models": ["qwen3-reranker-0.6b"],
            "capability": "rerank",
            "priority": 1,
        },
        {
            "name": "asr-main",
            "base_url": "http://asr.test:8004",
            "models": ["qwen3-asr"],
            "capability": "asr",
            "priority": 1,
        },
        {
            "name": "ocr-main",
            "base_url": "http://ocr.test:8103",
            "models": ["*"],
            "capability": "ocr",
            "priority": 1,
        },
    ]
)
os.environ.update(
    {
        "API_KEYS": "test-key-1",
        "JWT_SECRET_KEY": "pytest-only-secret",
        "POSTGRES_PASSWORD": "pytest-only-pg",
        "REDIS_PASSWORD": "pytest-only-redis",
        "OPENAI_COMPATIBLE_UPSTREAMS": _POOL,
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from app.main import app  # noqa: E402
from app.services.upstream_registry import registry  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# 池上下文在下方 autouse fixture 中按测试函数切换
# （pydantic settings 不感知 os.environ 后续变化，须改属性 + 重载）


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


# ── embeddings ──────────────────────────────────────────────


@respx.mock
def test_embeddings_route_and_passthrough(client):
    """embedding 能力路由 + 请求体透传 + 响应头"""
    registry.load_from_env()
    route = respx.post("http://embed-main.test:8100/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                "model": "qwen3-embedding-0.6b",
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )
    )
    r = client.post(
        "/v1/embeddings",
        headers=_auth(),
        json={"model": "qwen3-embedding-0.6b", "input": "你好世界"},
    )
    assert r.status_code == 200, r.text
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "qwen3-embedding-0.6b"
    assert sent["input"] == "你好世界"
    assert r.headers.get("x-yyc3-upstream") == "embed-main"
    assert r.json()["data"][0]["embedding"] == [0.1, 0.2]


@respx.mock
def test_embeddings_degraded_to_backup(client):
    """主 embedding 500 → 备用接管 + X-YYC3-Degraded"""
    registry.load_from_env()
    respx.post("http://embed-main.test:8100/v1/embeddings").mock(
        return_value=httpx.Response(500, text="down")
    )
    ok = respx.post("http://embed-backup.test:8100/v1/embeddings").mock(
        return_value=httpx.Response(
            200, json={"object": "list", "data": [{"index": 0, "embedding": [0.5]}]}
        )
    )
    r = client.post("/v1/embeddings", headers=_auth(), json={"model": "any-embed", "input": "x"})
    assert r.status_code == 200
    assert ok.called
    assert r.headers.get("x-yyc3-degraded") == "embed-main"


def test_embeddings_requires_auth(client):
    r = client.post("/v1/embeddings", json={"model": "m", "input": "x"})
    assert r.status_code in (401, 403)


# ── rerank：Cohere 对外 ⇆ 生成式打分 ──────────────────────


@respx.mock
def test_rerank_translation(client):
    """对外 Cohere 风格 → 上游生成式打分(/v1/completions+logprobs)；按 yes 概率降序"""
    route = respx.post("http://rerank.test:8101/v1/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "text_completion",
                "choices": [
                    {"index": 0, "logprobs": {"top_logprobs": [{"no": -2.3, "yes": -0.1}]}},
                    {"index": 1, "logprobs": {"top_logprobs": [{"yes": -0.05, "no": -3.0}]}},
                    {"index": 2, "logprobs": {"top_logprobs": [{"no": -0.2}]}},
                ],
                "usage": {"prompt_tokens": 9, "total_tokens": 9},
            },
        )
    )
    r = client.post(
        "/v1/rerank",
        headers=_auth(),
        json={
            "model": "qwen3-reranker-0.6b",
            "query": "什么是GB10",
            "documents": ["答案A", "GB10是Grace Blackwell", "无关C"],
            "top_n": 2,
        },
    )
    assert r.status_code == 200, r.text
    sent = json.loads(route.calls.last.request.content)
    assert len(sent["prompt"]) == 3  # 每文档一条指令模板
    assert "什么是GB10" in sent["prompt"][1]
    assert "GB10是Grace Blackwell" in sent["prompt"][1]
    assert sent["prompt"][1].startswith("<|im_start|>system")  # 官方 judge 模板
    body = r.json()
    assert body["results"][0]["index"] == 1  # yes=-0.05 概率最高
    assert body["results"][0]["relevance_score"] == pytest.approx(0.951, abs=0.01)
    assert len(body["results"]) == 2  # top_n=2
    assert body["results"][1]["index"] == 0  # yes=-0.1 次之
    assert r.headers.get("x-yyc3-upstream") == "rerank-main"


# ── capability 隔离 ─────────────────────────────────────────


@respx.mock
def test_capability_isolation_chat_pool_not_used_for_embedding(client):
    """embedding 请求绝不落到 chat 上游（即使其 models 通配）"""
    registry.load_from_env()
    chat_route = respx.post("http://flagship.test:8001/v1/embeddings").mock(
        return_value=httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.9]}]})
    )
    respx.post("http://embed-main.test:8100/v1/embeddings").mock(
        return_value=httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1]}]})
    )
    r = client.post("/v1/embeddings", headers=_auth(), json={"model": "whatever", "input": "x"})
    assert r.status_code == 200
    assert not chat_route.called, "chat 上游不应收到 embedding 请求"
    assert r.headers.get("x-yyc3-upstream") == "embed-main"


def test_models_list_excludes_non_chat_capabilities(client):
    """embedding/rerank 上游的 models 不进 /v1/models（chat 专属清单）"""
    registry.load_from_env()
    r = client.get("/v1/models", headers=_auth())
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert "deepseek-v4-flash" in ids  # chat 在
    assert "qwen3-embedding-0.6b" not in ids  # embedding 不在
    assert "qwen3-reranker-0.6b" not in ids


# ── multipart：asr / ocr ────────────────────────────────────


@respx.mock
def test_asr_multipart_passthrough(client):
    registry.load_from_env()
    route = respx.post("http://asr.test:8004/v1/audio/transcriptions").mock(
        return_value=httpx.Response(200, json={"text": "你好世界"})
    )
    r = client.post(
        "/v1/audio/transcriptions",
        headers=_auth(),
        files={"file": ("t.wav", b"RIFF-fake-audio", "audio/wav")},
        data={"model": "qwen3-asr"},
    )
    assert r.status_code == 200, r.text
    assert route.called
    assert r.json()["text"] == "你好世界"
    assert r.headers.get("x-yyc3-upstream") == "asr-main"


@respx.mock
def test_ocr_multipart_passthrough(client):
    registry.load_from_env()
    route = respx.post("http://ocr.test:8103/v1/ocr").mock(
        return_value=httpx.Response(200, json={"text": "识别结果"})
    )
    r = client.post(
        "/v1/ocr",
        headers=_auth(),
        files={"file": ("img.png", b"\x89PNG-fake", "image/png")},
    )
    assert r.status_code == 200, r.text
    assert route.called
    assert r.json()["text"] == "识别结果"


@respx.mock
def test_asr_all_down_returns_5xx(client):
    """全链失败 → 502（error_handler）而非 500 裸栈"""
    registry.load_from_env()
    respx.post("http://asr.test:8004/v1/audio/transcriptions").mock(
        return_value=httpx.Response(503, text="asr down")
    )
    r = client.post(
        "/v1/audio/transcriptions",
        headers=_auth(),
        files={"file": ("t.wav", b"fake", "audio/wav")},
        data={"model": "qwen3-asr"},
    )
    assert r.status_code in (500, 502, 503)
    assert "detail" in r.json()
