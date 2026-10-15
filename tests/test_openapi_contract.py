#!/usr/bin/env python3
"""
@file test_openapi_contract.py
@description 契约守卫——openapi schema 必须包含双端联通全部消费端点（防路由漂移/误删）
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-10-15
@tags [test,contract,openapi,duallink]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

os.environ.setdefault("API_KEYS", "test-key-1")

from app.main import app  # noqa: E402


def _paths():
    return set(app.openapi()["paths"].keys())


def test_duallink_p1_data_endpoints_present():
    """R4 P1 四数据端点必须在 schema（B端 /audit /alerts /报表 消费源）"""
    paths = _paths()
    assert "/v1/logs" in paths
    assert "/v1/usage/timeline" in paths
    assert "/v1/admin/alerts" in paths
    assert "/v1/models/summary" in paths


def test_skill_capability_endpoints_present():
    """§11 技能封装消费端点（缓存/路由/MCP/OCR/ASR）必须在 schema"""
    paths = _paths()
    assert "/v1/cache/stats" in paths
    assert "/v1/admin/upstreams/probe" in paths
    assert "/v1/mcp/tools" in paths
    assert "/v1/mcp/execute" in paths
    assert "/v1/ocr" in paths
    assert "/v1/audio/transcriptions" in paths


def test_frozen_baseline_endpoints_present():
    """v5.1 冻结快照关键端点抽查（chat/WS 非本测试面, 查 HTTP 代表项）"""
    paths = _paths()
    for p in (
        "/v1/chat/completions",
        "/v1/models",
        "/v1/models/stats",
        "/v1/router/stats",
        "/v1/admin/usage/summary",
        "/registry/v1/events",
    ):
        assert p in paths, f"frozen endpoint missing: {p}"


def test_openapi_path_count_baseline():
    """端点总量基线: ≥ 98（openapi paths 口径, WS 三通道不计入; 只增不减防误删,
    下调须同步冻结文档升版——口径差异: 路由总数 111 含 WS/多方法展开）"""
    paths = _paths()
    assert len(paths) >= 98, f"openapi paths {len(paths)} < 98 baseline"
