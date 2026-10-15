#!/usr/bin/env python3
"""
@file test_chat_spend_error.py
@description R5 chat 记账可观测性——_record_spend_error 载荷契约 + _record_spend 成功路径新列透传
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-10-15
@tags [test,duallink,r5,spend,observability]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

os.environ.setdefault("API_KEYS", "test-key-1")

import asyncio  # noqa: E402

# noqa flake8: E402 以下为 conftest 注册后的 app 导入
from app.api import chat  # noqa: E402
from app.services import virtual_key_manager as vkm  # noqa: E402

_VK = {"id": "vk-test-0001"}


def _capture_enqueue(monkeypatch):
    captured = []

    async def _fake_enqueue(entry):
        captured.append(entry)

    monkeypatch.setattr(vkm.vk_manager, "enqueue_spend", _fake_enqueue)
    return captured


def test_record_spend_error_payload(monkeypatch):
    """错误行载荷: status=error + error_code, 零 token 零成本, vk id 透传"""
    captured = _capture_enqueue(monkeypatch)

    async def _run():
        chat._record_spend_error(_VK, "glm-4-flash", "zhipu", 1234.5, "upstream_error")

    asyncio.run(_run())
    # create_task 已调度 — 让事件循环收尾执行
    asyncio.run(asyncio.sleep(0))
    assert len(captured) == 1
    entry = captured[0]
    assert entry["status"] == "error"
    assert entry["error_code"] == "upstream_error"
    assert entry["key_id"] == "vk-test-0001"
    assert entry["prompt_tokens"] == 0 and entry["completion_tokens"] == 0
    assert entry["cost_usd"] == 0.0
    assert entry["latency_ms"] == 1234


def test_record_spend_error_direct_key(monkeypatch):
    """网关直连（vk=None）同样留痕: key_id NULL"""
    captured = _capture_enqueue(monkeypatch)

    async def _run():
        chat._record_spend_error(None, "glm-4-flash", "gateway", 50.0, "vk_tpm_limited")

    asyncio.run(_run())
    asyncio.run(asyncio.sleep(0))
    assert captured[0]["key_id"] is None
    assert captured[0]["error_code"] == "vk_tpm_limited"


def test_record_spend_ok_passthrough(monkeypatch):
    """成功路径: status=ok + 网关响应 id 作 request_id 透传"""
    captured = _capture_enqueue(monkeypatch)
    pricing_stub_cost = {"called": False}

    def _fake_cost(model, pt, ct):
        pricing_stub_cost["called"] = True
        return 0.01

    # chat.pricing 是 services.pricing.pricing 实例（方法级替换）
    monkeypatch.setattr(chat.pricing, "completion_cost", _fake_cost)

    response = {
        "id": "chatcmpl-test-123",
        "usage": {"prompt_tokens": 100, "completion_tokens": 40},
    }

    async def _run():
        cost = chat._record_spend(_VK, response, "glm-4-flash", "zhipu", 800.0)
        assert cost == 0.01

    asyncio.run(_run())
    asyncio.run(asyncio.sleep(0))
    assert pricing_stub_cost["called"] is True
    assert len(captured) == 1
    entry = captured[0]
    assert entry["status"] == "ok"
    assert entry["request_id"] == "chatcmpl-test-123"
    assert entry["cost_usd"] == 0.01
