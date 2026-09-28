#!/usr/bin/env python3
"""
@file test_rerank_svc.py
@description 重排服务测试——生成式打分/降级链/模型改写/数量对齐（零网络 respx）
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-28
@tags [test,rerank,qwen3-reranker,upstream-chain]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

os.environ.setdefault("API_KEYS", "test-key-1")

import asyncio  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402

from app.services.rerank_svc import (_rerank_prompt,  # noqa: E402
                                     _yes_probability, rerank_scores)
from app.services.upstream_registry import registry  # noqa: E402

# rerank 池：一主一备（降级链验证用）
_POOL = json.dumps(
    [
        {
            "name": "rerank-main",
            "base_url": "http://rerank-main.test:8101",
            "models": ["qwen3-reranker-0.6b"],
            "capability": "rerank",
            "priority": 1,
        },
        {
            "name": "rerank-backup",
            "base_url": "http://rerank-backup.test:8101",
            "models": ["qwen3-reranker-0.6b"],
            "capability": "rerank",
            "priority": 5,
        },
    ]
)


@pytest.fixture(autouse=True)
def _pool_context(monkeypatch):
    """本文件专用池（含备份链）；用例后还原 settings 属性"""
    from app.config import settings as _settings

    monkeypatch.setattr(_settings, "openai_compatible_upstreams", _POOL)
    registry.load_from_env()
    yield
    registry.load_from_env()  # 还原为其余环境池（防跨文件污染）


def _choice(yes_lp: float = -0.1, no_lp: float = -3.0) -> dict:
    """构造 Qwen3-Reranker 语义的 completions choice（top_logprobs 含 yes/no）"""
    return {
        "logprobs": {
            "top_logprobs": [
                {"yes": yes_lp, "no": no_lp, " Yes": yes_lp + 0.01},
            ]
        }
    }


def _resp(choices) -> dict:
    return {"choices": choices, "usage": {"total_tokens": 1}}


# ── 纯函数：模板与概率提取 ──────────────────────────────────
def test_prompt_template_three_part():
    p = _rerank_prompt("查什么", "文档内容")
    assert p.startswith("<|im_start|>system")
    assert "<Instruct>" in p and "<Query>查什么</Query>" in p
    assert "<Document>文档内容</Document>" in p
    assert p.endswith("<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")


@respx.mock
def test_long_doc_truncated_in_scores_call():
    """超长文档在 rerank_scores 调用侧截断为 _DOC_MAX_CHARS（防超长 prompt）"""
    from app.services.rerank_svc import _DOC_MAX_CHARS

    route = respx.post("http://rerank-main.test:8101/v1/completions").mock(
        return_value=httpx.Response(200, json=_resp([_choice()]))
    )
    asyncio.run(rerank_scores("q", ["字" * 3000]))
    body = json.loads(route.calls.last.request.content)
    prompt = body["prompt"][0]
    doc_part = prompt.split("<Document>")[1].split("</Document>")[0]
    assert len(doc_part) == _DOC_MAX_CHARS


def test_yes_probability_extraction():
    assert abs(_yes_probability(_choice(yes_lp=0.0)) - 1.0) < 1e-9
    assert abs(_yes_probability(_choice(yes_lp=math.log(0.4))) - 0.4) < 1e-6


def test_yes_probability_miss_returns_zero():
    assert _yes_probability({"logprobs": {"top_logprobs": [{"no": -0.2}]}}) == 0.0
    assert _yes_probability({}) == 0.0
    assert _yes_probability({"logprobs": {}}) == 0.0


# ── rerank_scores：打分与契约（respx 桩上游）────────────────
@respx.mock
def test_scores_aligned_with_documents():
    route = respx.post("http://rerank-main.test:8101/v1/completions").mock(
        return_value=httpx.Response(200, json=_resp([_choice(-0.1), _choice(-2.0)]))
    )
    scores, upstream = asyncio.run(
        rerank_scores("查询", ["文档一", "文档二", "文档三"])  # 上游只回 2 → 补 0
    )
    assert upstream == "rerank-main"
    assert len(scores) == 3
    assert scores[2] == 0.0, "上游截断时缺项补 0"
    assert scores[0] > scores[1] > scores[2]
    body = json.loads(route.calls.last.request.content)
    assert body["max_tokens"] == 1 and body["temperature"] == 0
    assert body["logprobs"] == 20
    assert len(body["prompt"]) == 3
    assert body["model"] == "qwen3-reranker-0.6b", "未指定 model 时用上游首个注册模型"


@respx.mock
def test_model_rewrite_for_unregistered_model():
    route = respx.post("http://rerank-main.test:8101/v1/completions").mock(
        return_value=httpx.Response(200, json=_resp([_choice()]))
    )
    asyncio.run(rerank_scores("q", ["d"], model="custom-reranker-x"))
    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "qwen3-reranker-0.6b", "未注册 model 应改写为上游注册模型"


@respx.mock
def test_failover_to_backup_upstream():
    respx.post("http://rerank-main.test:8101/v1/completions").mock(
        return_value=httpx.Response(500, text="boom")
    )
    respx.post("http://rerank-backup.test:8101/v1/completions").mock(
        return_value=httpx.Response(200, json=_resp([_choice()]))
    )
    scores, upstream = asyncio.run(rerank_scores("q", ["d"]))
    assert upstream == "rerank-backup", "主上游 500 应降级到备份"
    assert scores == [pytest.approx(math.exp(-0.1))]


@respx.mock
def test_all_upstreams_failed_raises():
    respx.post("http://rerank-main.test:8101/v1/completions").mock(
        return_value=httpx.Response(500)
    )
    respx.post("http://rerank-backup.test:8101/v1/completions").mock(
        return_value=httpx.Response(500)
    )
    with pytest.raises(RuntimeError, match="降级链全部失败"):
        asyncio.run(rerank_scores("q", ["d"]))


def test_empty_documents_short_circuit():
    scores, upstream = asyncio.run(rerank_scores("q", []))
    assert scores == [] and upstream == ""


def test_empty_pool_raises():
    registry.upstreams.clear()  # 池清空（fixture 结束会重载还原）
    with pytest.raises(RuntimeError, match="上游池为空"):
        asyncio.run(rerank_scores("q", ["d"]))
