#!/usr/bin/env python3
"""
@file test_model_register_agent.py
@description 注册 Agent 测试——payload 构建/健康URL/指标抽取/状态机步骤（假 HTTP 桩）
@tags [test,registry,agent,fast]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "scripts"))

import pytest  # noqa: E402
from model_register_agent import (  # noqa: E402
    RegisterAgent,
    build_register_payload,
    extract_runtime_metrics,
    service_health_url,
)

_META = {
    "model_id": "qwen3.8-27b",
    "display_name": "Qwen3.8 27B",
    "backend": "vllm",
    "base_url": "http://10.0.0.101:8000/v1",
    "node_id": "yyc3-101",
    "model_type": "chat",
    "capabilities": ["chat"],
}


class _FakeHTTP:
    """HTTP 桩：按 (method, url 尾段) 路由返回。"""

    def __init__(self, routes=None):
        self.calls = []
        self.routes = routes or {}

    def __call__(self, method, url, key, body=None, timeout=10):
        self.calls.append((method, url, body))
        for suffix, (status, resp) in self.routes.items():
            if url.endswith(suffix):
                return status, resp
        return 200, None


class TestPayload:
    def test_backend_alias_normalized(self):
        payload = build_register_payload(dict(_META))
        assert payload["backend_type"] == "vllm"  # backend → backend_type 归一

    def test_overrides_win_and_drop_none(self):
        payload = build_register_payload(dict(_META), {"node_id": None, "model_type": "asr"})
        assert payload["node_id"] == "yyc3-101"  # None 覆盖被忽略
        assert payload["model_type"] == "asr"

    def test_missing_model_id_raises(self):
        with pytest.raises(ValueError):
            build_register_payload({"display_name": "x"})


class TestHelpers:
    def test_health_url_strips_v1(self):
        assert service_health_url("http://10.0.0.101:8000/v1") == "http://10.0.0.101:8000/health"
        assert service_health_url("http://h:9/") == "http://h:9/health"

    def test_metrics_extract_best_effort(self):
        assert extract_runtime_metrics(
            {"gpu_utilization": 0.7, "active_requests": 3, "noise": "x"}
        ) == {"gpu_utilization": 0.7, "active_requests": 3}
        assert extract_runtime_metrics(None) == {}
        assert extract_runtime_metrics({"gpu_utilization": "70%"}) == {}  # 非数值忽略


class TestAgentSteps:
    def _agent(self, routes=None):
        http = _FakeHTTP(routes)
        agent = RegisterAgent("http://gw:8000/", dict(_META), "k1", http=http, sleep=lambda s: None)
        return agent, http

    def test_wait_ready_polls_until_200(self):
        agent, _ = self._agent({"/health": (200, {"status": "ok"})})
        assert agent.wait_service_ready(timeout=1) is True

    def test_wait_ready_timeout(self):
        agent, _ = self._agent({"/health": (0, None)})
        agent._stopped = True  # 立即终止轮询
        assert agent.wait_service_ready(timeout=0.1) is False

    def test_register_posts_to_models(self):
        agent, http = self._agent({"/registry/v1/models": (201, {"id": "qwen3.8-27b"})})
        assert agent.register() is True
        method, url, body = http.calls[-1]
        assert method == "POST" and url.endswith("/registry/v1/models")
        assert body["model_id"] == "qwen3.8-27b"

    def test_register_fail_4xx(self):
        agent, _ = self._agent({"/registry/v1/models": (422, {"detail": "x"})})
        assert agent.register() is False

    def test_set_state_patches(self):
        agent, http = self._agent()
        assert agent.set_state("ready") is True
        method, url, body = http.calls[-1]
        assert (
            method == "PATCH" and url.endswith("/models/qwen3.8-27b") and body == {"state": "ready"}
        )

    def test_heartbeat_carries_runtime_metrics(self):
        agent, http = self._agent(
            {
                "/health": (200, {"gpu_utilization": 0.5, "active_requests": 2}),
            }
        )
        assert agent.heartbeat_once() is True
        method, url, body = http.calls[-1]
        assert method == "POST" and url.endswith("/heartbeat")
        assert body["gpu_utilization"] == 0.5 and body["status"] == "healthy"
