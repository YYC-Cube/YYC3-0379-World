#!/usr/bin/env python3
"""
@file test_model_register_agent.py
@description 注册 Agent 测试——payload 构建/健康URL/指标抽取/状态机步骤（假 HTTP 桩）
@tags [test,registry,agent,fast]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "scripts"))

import json  # noqa: E402
import urllib.request  # noqa: E402

import pytest  # noqa: E402
from model_register_agent import (  # noqa: E402
    CONTRACT_VERSION,
    RegisterAgent,
    build_register_payload,
    extract_runtime_metrics,
    service_health_url,
    start_contract_server,
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

    def __call__(self, method, url, key, body=None, timeout=10, **kwargs):
        # **kwargs 兼容治理日后新增调用形参（如 registry_token），mock 不随签名演进漂移
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
        payload = build_register_payload(
            dict(_META), {"node_id": None, "model_type": "asr"}
        )
        assert payload["node_id"] == "yyc3-101"  # None 覆盖被忽略
        assert payload["model_type"] == "asr"

    def test_missing_model_id_raises(self):
        with pytest.raises(ValueError):
            build_register_payload({"display_name": "x"})


class TestHelpers:
    def test_health_url_strips_v1(self):
        assert (
            service_health_url("http://10.0.0.101:8000/v1")
            == "http://10.0.0.101:8000/health"
        )
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
        agent = RegisterAgent(
            "http://gw:8000/", dict(_META), "k1", http=http, sleep=lambda s: None
        )
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
            method == "PATCH"
            and url.endswith("/models/qwen3.8-27b")
            and body == {"state": "ready"}
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


class TestContractServer:
    """契约端点三件（规范 02 §2）——真起 ephemeral server（port 0）localhost 实调"""

    @pytest.fixture()
    def server(self):
        http = _FakeHTTP(
            {"/health": (200, {"gpu_utilization": 41.5, "active_requests": 2})}
        )
        agent = RegisterAgent(
            "http://gw:8000", build_register_payload(dict(_META)), "k", http=http
        )
        srv = start_contract_server(agent, 0)
        yield f"http://127.0.0.1:{srv.server_address[1]}"
        srv.shutdown()
        srv.server_close()

    @staticmethod
    def _get(base, path):
        with urllib.request.urlopen(base + path, timeout=5) as r:
            return r.status, json.loads(r.read().decode())

    def test_metadata_contract_version_and_payload(self, server):
        code, body = self._get(server, "/v1/model/metadata")
        assert code == 200
        assert body["contract"] == CONTRACT_VERSION
        assert body["model_id"] == "qwen3.8-27b" and body["base_url"].startswith(
            "http://"
        )

    def test_capabilities_from_payload(self, server):
        _, body = self._get(server, "/v1/model/capabilities")
        assert body == {"model_id": "qwen3.8-27b", "capabilities": ["chat"]}

    def test_capabilities_fallback_to_model_type(self):
        http = _FakeHTTP()
        meta = {k: v for k, v in _META.items() if k != "capabilities"}
        agent = RegisterAgent(
            "http://gw:8000", build_register_payload(meta), "k", http=http
        )
        srv = start_contract_server(agent, 0)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            _, body = self._get(base, "/v1/model/capabilities")
            assert body["capabilities"] == [
                "chat"
            ], "无 capabilities 字段时降级 model_type"
        finally:
            srv.shutdown()
            srv.server_close()

    def test_health_probes_service(self, server):
        _, body = self._get(server, "/v1/model/health")
        assert body["status"] == "healthy" and body["upstream_status"] == 200
        assert body["gpu_utilization"] == 41.5 and body["active_requests"] == 2

    def test_unknown_path_404_with_endpoint_hints(self, server):
        try:
            urllib.request.urlopen(server + "/nope", timeout=5)
            raised = False
        except urllib.error.HTTPError as e:
            raised = e.code == 404
        assert raised
