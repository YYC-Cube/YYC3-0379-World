# file: test_vision_and_models_listing.py
# description: 视觉 content-parts 接受 + /v1/models embedding 型号入列（2026-11-02 评测产出修复）
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-11-02
# status: active
# tags: [test],[vision],[models],[integration]
# 凭据零字面量：全部取自 tests/conftest.py 的 os.environ 注入（pytest 专用占位值）

import os

_POOL = """[
  {"name": "flagship", "base_url": "http://flagship.test:8001", "models": ["nemotron-3.5-super-vl"], "priority": 1, "weight": 100},
  {"name": "embed-n1", "base_url": "http://embed.test:8100", "models": ["bge-m3", "baai/bge-m3", "*"], "capability": "embedding", "priority": 2},
  {"name": "rerank-n1", "base_url": "http://rerank.test:8101", "models": ["bge-reranker-v2-m3"], "capability": "rerank", "priority": 2}
]"""

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.upstream_registry import registry  # noqa: E402

pytestmark = pytest.mark.integration

_FIRST_KEY = (os.environ.get("API_KEYS") or "k").split(",")[0]


@pytest.fixture(autouse=True)
def _pool_context():
    from app.config import settings as _settings

    _settings.openai_compatible_upstreams = _POOL
    registry.load_from_env()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _auth():
    return {"X-API-Key": _FIRST_KEY}


def test_message_accepts_content_parts():
    """Message.content 接受 OpenAI content-parts（422 根因修复回归）"""
    from app.api.schemas import Message

    m = Message(role="user", content=[
        {"type": "text", "text": "数一数"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
    ])
    assert m.text_content() == "数一数"
    with pytest.raises(Exception):
        Message(role="user", content=[{"type": "audio", "data": "x"}])
    with pytest.raises(Exception):
        Message(role="user", content=[])


def test_models_lists_embedding_and_rerank(client):
    """/v1/models 补列 embed/rerank 精确型号（盲区修复）；通配符不入列"""
    r = client.get("/v1/models", headers=_auth())
    assert r.status_code == 200, r.text
    ids = [m["id"] for m in r.json()]
    assert "bge-m3" in ids and "baai/bge-m3" in ids and "bge-reranker-v2-m3" in ids
    assert not any(i == "*" or i == "embed-n1" for i in ids)


@respx.mock
def test_chat_with_content_parts_passes_validation(client):
    """视觉消息体过校验并透传上游（parts 原样进上游 payload）"""
    route = respx.post("http://flagship.test:8001/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": "nemotron-3.5-super-vl",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "3"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    parts = [{"type": "text", "text": "图中有几个红色的圆形？"},
             {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}]
    r = client.post("/v1/chat/completions", headers=_auth(), json={
        "model": "nemotron-3.5-super-vl",
        "messages": [{"role": "user", "content": parts}],
        "max_tokens": 32,
    })
    assert r.status_code == 200, r.text
    assert route.called
    sent = route.calls[0].request.read().decode()
    assert "image_url" in sent
