# file: test_cloud_adapters_fullpath.py
# description: 三云适配器（zhipu/deepseek/openai）+ ollama 主链路覆盖补齐（P1-3，快速层纯 mock）
# author: YanYuCloudCube Team <admin@0379.email>
# created: 2026-09-23
# status: active
# tags: [test],[adapters],[coverage]

"""
@file: test_cloud_adapters_fullpath.py
@description: 覆盖 v8 审计识别的主链路缺口（三云适配器 24%/27%/53%）：
  ① 同步入口正常链路（headers 组装 / payload 透传 / 响应规范化）
  ② 流式入口正常链路（SSE 行解析 / [DONE] 终止 / chunk 规范化 / 坏行容错）
  ③ zhipu reasoning_content 折叠（同步响应侧）
  ④ HTTPStatusError / 网络异常分支
  ⑤ ollama 主备切换（主挂→备起）与全塔断路（RuntimeError）
  ⑥ ollama _normalize_host 两种 OLLAMA_HOST 格式归一
全部 respx mock，毫秒级，属快速回归层（不带 integration 标记）。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import httpx  # noqa: E402
import respx  # noqa: E402
from httpx import Response  # noqa: E402

# ── 公共夹具：三云 Key 注入 + base_url 指向 mock 域 ──────────────


@pytest.fixture(autouse=True)
def _cloud_env(monkeypatch):
    """三云 Key/base 指向可控 mock 域（每用例还原，防跨文件污染）"""
    from app.config import settings

    monkeypatch.setattr(settings, "zhipu_base_url", "https://zhipu-mock.test/v4")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://deepseek-mock.test/v1")
    monkeypatch.setattr(settings, "openai_base_url", "https://openai-mock.test/v1")
    monkeypatch.setenv("ZHIPU_API_KEY", "zk-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "ok-test")
    monkeypatch.setattr(settings, "zhipu_api_key", "zk-test")
    monkeypatch.setattr(settings, "deepseek_api_key", "dk-test")
    monkeypatch.setattr(settings, "openai_api_key", "ok-test")
    yield


def _ok_body(content="你好", reasoning=""):
    """云上游 OpenAI 兼容响应体"""
    msg = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    return {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 1700000000,
        "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
    }


_SSE_LINES = [
    'data: {"id":"c1","created":1,"choices":[{"index":0,"delta":{"role":"assistant","content":"你"},"finish_reason":null}]}',
    "data: not-a-json",  # 坏行 → 容错 continue
    'data: {"id":"c1","created":1,"choices":[{"index":0,"delta":{"content":"好"},"finish_reason":null}]}',
    "data: [DONE]",
    'data: {"id":"c1","created":1,"choices":[{"index":0,"delta":{"content":"DONE后应被忽略"},"finish_reason":null}]}',
]


def _sse_stream():
    return httpx.Response(
        200,
        text="\n".join(_SSE_LINES) + "\n",
        headers={"content-type": "text/event-stream"},
    )


# ── ① 同步入口正常链路 ────────────────────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize(
    "module_name,base_url,model",
    [
        ("zhipu", "https://zhipu-mock.test/v4", "glm-4"),
        ("deepseek", "https://deepseek-mock.test/v1", "deepseek-chat"),
        ("openai", "https://openai-mock.test/v1", "gpt-4"),
    ],
    ids=["zhipu", "deepseek", "openai"],
)
async def test_sync_ok_and_auth_header(module_name, base_url, model):
    """同步链路 200：Authorization 携带 Bearer Key、payload 模型透传、响应含 usage"""
    import importlib

    adapter = importlib.import_module(f"app.services.{module_name}")

    with respx.mock(base_url=base_url, assert_all_mocked=False) as m:
        route = m.post(f"{base_url}/chat/completions").mock(
            return_value=Response(200, json=_ok_body())
        )
        result = await adapter.chat_completion(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=64,
            top_p=0.9,
        )
        assert route.called
        sent = route.calls.last.request
        key_prefix = {"zhipu": "zk", "deepseek": "dk", "openai": "ok"}[module_name]
        assert sent.headers["authorization"] == f"Bearer {key_prefix}-test"
        import json as _json

        body = _json.loads(sent.content)
        assert body["model"] == model
        assert body["messages"][0]["content"] == "hi"
    assert result["choices"][0]["message"]["content"] == "你好"
    assert result["usage"]["total_tokens"] == 7


# ── ② 流式入口正常链路 ────────────────────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize(
    "module_name,base_url,model",
    [
        ("zhipu", "https://zhipu-mock.test/v4", "glm-4"),
        ("deepseek", "https://deepseek-mock.test/v1", "deepseek-chat"),
        ("openai", "https://openai-mock.test/v1", "gpt-4"),
    ],
    ids=["zhipu", "deepseek", "openai"],
)
async def test_stream_parses_sse_stops_at_done(module_name, base_url, model):
    """流式链路：SSE 解析为统一 chunk、坏行容错、[DONE] 终止（后续行不产出）"""
    import importlib

    adapter = importlib.import_module(f"app.services.{module_name}")

    with respx.mock(base_url=base_url, assert_all_mocked=False) as m:
        m.post(f"{base_url}/chat/completions").mock(return_value=_sse_stream())
        chunks = [
            c
            async for c in adapter.chat_completion_stream(
                model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=32
            )
        ]
    contents = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
    assert contents == "你好", "坏行应跳过、DONE 后不产出"
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)


# ── ③ zhipu reasoning 折叠（同步响应侧）─────────────────────


@pytest.mark.anyio
async def test_zhipu_reasoning_folded_into_content():
    """GLM reasoning_content 折叠：仅 reasoning → 上提为 content；两者并存 → 拼接"""
    from app.services import zhipu

    with respx.mock(base_url="https://zhipu-mock.test/v4", assert_all_mocked=False) as m:
        m.post("https://zhipu-mock.test/v4/chat/completions").mock(
            return_value=Response(200, json=_ok_body(content="", reasoning="思考中"))
        )
        r1 = await zhipu.chat_completion(
            model="glm-4", messages=[{"role": "user", "content": "hi"}]
        )
        assert r1["choices"][0]["message"]["content"] == "思考中"

        m2 = m.post("https://zhipu-mock.test/v4/chat/completions").mock(
            return_value=Response(200, json=_ok_body(content="答案", reasoning="推演"))
        )
        # respx 同 path 后注册优先：直接断言第二次
        r2 = await zhipu.chat_completion(
            model="glm-4", messages=[{"role": "user", "content": "hi"}]
        )
        msg = r2["choices"][0]["message"]["content"]
        assert "推演" in msg and "答案" in msg
    _ = m2


# ── ④ 错误分支 ────────────────────────────────────────────────


@pytest.mark.anyio
async def test_deepseek_4xx_raises_apierror_with_status():
    """deepseek HTTPStatusError → APIError（details 携带上游 status）"""
    from app.errors import APIError
    from app.services import deepseek

    with respx.mock(base_url="https://deepseek-mock.test/v1", assert_all_mocked=False) as m:
        m.post("https://deepseek-mock.test/v1/chat/completions").mock(
            return_value=Response(402, text='{"error":"quota"}')
        )
        with pytest.raises(APIError) as ei:
            await deepseek.chat_completion(
                model="deepseek-chat", messages=[{"role": "user", "content": "hi"}]
            )
    assert "DeepSeek" in ei.value.message
    assert ei.value.details["status_code"] == 402


@pytest.mark.anyio
async def test_deepseek_network_error_raises_apierror():
    """deepseek 网络层异常 → APIError（服务异常语义）"""
    from app.errors import APIError
    from app.services import deepseek

    with respx.mock(base_url="https://deepseek-mock.test/v1", assert_all_mocked=False) as m:
        m.post("https://deepseek-mock.test/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("boom")
        )
        with pytest.raises(APIError):
            await deepseek.chat_completion(
                model="deepseek-chat", messages=[{"role": "user", "content": "hi"}]
            )


@pytest.mark.anyio
async def test_zhipu_5xx_reraises_httpx_and_unknown_wraps_apierror():
    """zhipu：HTTPStatusError 原样上抛（上层 handler 统一分诊）；未知异常包 APIError"""
    from app.errors import APIError
    from app.services import zhipu

    with respx.mock(base_url="https://zhipu-mock.test/v4", assert_all_mocked=False) as m:
        m.post("https://zhipu-mock.test/v4/chat/completions").mock(
            return_value=Response(503, text="up")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await zhipu.chat_completion(model="glm-4", messages=[{"role": "user", "content": "hi"}])

        m.post("https://zhipu-mock.test/v4/chat/completions").mock(side_effect=ValueError("boom"))
        with pytest.raises(APIError):
            await zhipu.chat_completion(model="glm-4", messages=[{"role": "user", "content": "hi"}])


@pytest.mark.anyio
async def test_openai_sync_5xx_reraises():
    """openai 同步入口 raise_for_status 直抛（无 try 包裹，上层 handler 分诊）"""
    from app.services import openai as oa

    with respx.mock(base_url="https://openai-mock.test/v1", assert_all_mocked=False) as m:
        m.post("https://openai-mock.test/v1/chat/completions").mock(
            return_value=Response(500, text="err")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await oa.chat_completion(model="gpt-4", messages=[{"role": "user", "content": "hi"}])


# ── ⑤ ollama 主备切换与全塔断路 ──────────────────────────────


@pytest.fixture()
def _ollama_two_hosts(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ollama_host", "192.168.9.9")
    monkeypatch.setattr(settings, "ollama_backup_host", "192.168.9.10")
    monkeypatch.setattr(settings, "ollama_port", 11434)


@pytest.mark.anyio
async def test_ollama_fallback_to_backup(_ollama_two_hosts):
    """主 Ollama 挂 → 自动切备机，响应规范化为 OpenAI 兼容"""
    from app.services import ollama

    ollama_raw = {
        "created_at": "2026-09-23T00:00:00Z",
        "message": {"role": "assistant", "content": "本地在线"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 5,
        "eval_count": 6,
    }
    with respx.mock(assert_all_mocked=False) as m:
        m.post("http://192.168.9.9:11434/api/chat").mock(
            side_effect=httpx.ConnectError("primary down")
        )
        m.post("http://192.168.9.10:11434/api/chat").mock(
            return_value=Response(200, json=ollama_raw)
        )
        r = await ollama.chat_completion(
            model="qwen3:8b", messages=[{"role": "user", "content": "hi"}]
        )
    assert r["object"] == "chat.completion"
    assert r["choices"][0]["message"]["content"] == "本地在线"
    assert r["usage"]["total_tokens"] == 11


@pytest.mark.anyio
async def test_ollama_all_endpoints_failed(_ollama_two_hosts):
    """主备全挂 → RuntimeError（All Ollama endpoints failed）"""
    from app.services import ollama

    with respx.mock(assert_all_mocked=False) as m:
        m.post("http://192.168.9.9:11434/api/chat").mock(side_effect=httpx.ConnectError("a"))
        m.post("http://192.168.9.10:11434/api/chat").mock(side_effect=httpx.ConnectError("b"))
        with pytest.raises(RuntimeError, match="All Ollama endpoints failed"):
            await ollama.chat_completion(
                model="qwen3:8b", messages=[{"role": "user", "content": "hi"}]
            )


@pytest.mark.anyio
async def test_ollama_stream_chunks(_ollama_two_hosts, monkeypatch):
    """ollama 流式：NDJSON 行解析、done 标志 → finish_reason、成功即 return 不碰备机"""
    from app.config import settings
    from app.services import ollama

    monkeypatch.setattr(settings, "ollama_backup_host", "")  # 单主机
    ndjson = (
        '{"created_at":"t1","message":{"role":"assistant","content":"你"},"done":false}\n'
        '{"created_at":"t2","message":{"content":"好"},"done":true,"done_reason":"stop"}\n'
    )
    with respx.mock(assert_all_mocked=False) as m:
        m.post("http://192.168.9.9:11434/api/chat").mock(
            return_value=httpx.Response(
                200, text=ndjson, headers={"content-type": "application/x-ndjson"}
            )
        )
        chunks = [
            c
            async for c in ollama.chat_completion_stream(
                model="qwen3:8b", messages=[{"role": "user", "content": "hi"}]
            )
        ]
    assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == "你好"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


# ── ⑥ _normalize_host 归一 ───────────────────────────────────


def test_ollama_normalize_host_variants():
    """OLLAMA_HOST 官方完整 URL 与纯 host 两种格式归一为纯 host"""
    from app.services.ollama import _normalize_host

    assert _normalize_host("http://127.0.0.1:11434") == "127.0.0.1"
    assert _normalize_host("https://dgx-101:11434") == "dgx-101"
    assert _normalize_host("  100.65.64.49 ") == "100.65.64.49"
    assert _normalize_host("plainhost") == "plainhost"
