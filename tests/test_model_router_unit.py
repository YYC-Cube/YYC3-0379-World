#!/usr/bin/env python3
"""
@file test_model_router_unit.py
@description 模型路由器（EWMA 动态权重反馈循环）纯单元测试——0% 覆盖盲区攻坚
@author: YanYuCloudCube Team
@tags [test,model-router,ewma,unit]

背景：services/model_router.py（197 语句）为 README 头号卖点「智能调度」核心，
此前 0% 覆盖（docs/0379-world-执行记录/21-深度审核与实况测试报告.md §三 P2-2）。
本文件锁定：选路过滤/各策略正确性/EWMA 数学/状态升降级/健康检查/负载释放。
模块自包含（无 Redis/DB），asyncio.run 桥接（项目无 pytest-asyncio）。
"""

import asyncio
import os
import random as random_module
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

from app.services.model_router import (  # noqa: E402
    ModelRouter,
    NodeInfo,
    NodeStatus,
    NoAvailableNodeError,
    RequestRecord,
    RoutingStrategy,
)
from app.services import model_router as mr_mod  # noqa: E402

pytestmark = pytest.mark.unit


def _run(coro):
    return asyncio.run(coro)


def _fake_time(monkeypatch, start=1_000_000.0):
    """替换模块 time：time.time() 走受控时钟，time.monotonic 同步推进"""
    clock = [start]
    monkeypatch.setattr(
        mr_mod,
        "time",
        types.SimpleNamespace(time=lambda: clock[0], monotonic=lambda: clock[0]),
    )
    return clock


# ── 初始化 ────────────────────────────────────────────────


def test_default_nodes_initialized_with_ewma_seeded():
    router = ModelRouter()
    assert set(router.nodes) == {"yyc3-22", "yyc3-33", "yyc3-45"}
    for node in router.nodes.values():
        assert node.ewma_latency == node.latency  # EWMA 以静态延迟为初值
        assert node.status == NodeStatus.HEALTHY


# ── 选路：候选过滤与异常 ──────────────────────────────────


def test_route_unknown_model_raises():
    router = ModelRouter()
    with pytest.raises(NoAvailableNodeError):
        _run(router.route_request("no-such-model", {}))


def test_route_excludes_unhealthy_but_keeps_degraded():
    router = ModelRouter()
    router.routing_strategy = RoutingStrategy.ROUND_ROBIN
    # llama3.2 仅 yyc3-22 服务：先补一个同模型节点作替代候选
    router.add_node(
        NodeInfo(node_id="backup-1", node_type="ollama", models=["llama3.2"], capacity=50)
    )
    router.nodes["yyc3-22"].status = NodeStatus.UNHEALTHY
    assert _run(router.route_request("llama3.2", {})) == "backup-1"  # UNHEALTHY 被排除
    # DEGRADED 不排除：仍可能选中
    router2 = ModelRouter()
    router2.routing_strategy = RoutingStrategy.ROUND_ROBIN
    router2.nodes["yyc3-22"].status = NodeStatus.DEGRADED
    assert _run(router2.route_request("llama3.2", {})) == "yyc3-22"


def test_route_request_increments_load_and_total():
    router = ModelRouter()
    router.routing_strategy = RoutingStrategy.ROUND_ROBIN
    before_load = router.nodes["yyc3-22"].current_load
    before_total = router.nodes["yyc3-22"].total_requests
    _run(router.route_request("llama3.2", {}))
    assert router.nodes["yyc3-22"].current_load == before_load + 1
    assert router.nodes["yyc3-22"].total_requests == before_total + 1


def test_all_unhealthy_raises():
    router = ModelRouter()
    for n in router.nodes.values():
        n.status = NodeStatus.UNHEALTHY
    with pytest.raises(NoAvailableNodeError):
        _run(router.route_request("llama3.2", {}))


# ── 传统策略 ──────────────────────────────────────────────


def test_round_robin_cycles():
    router = ModelRouter()
    router.routing_strategy = RoutingStrategy.ROUND_ROBIN
    # glm-4-flash 仅 yyc3-33 服务 → 恒选中，但索引仍推进
    for _ in range(3):
        assert _run(router.route_request("glm-4-flash", {})) == "yyc3-33"
    assert router._round_robin_index == 3


def test_least_connections_picks_min_load():
    router = ModelRouter()
    router.nodes["yyc3-33"].current_load = 50
    router.nodes["yyc3-45"].current_load = 5
    assert router._select_by_least_connections(["yyc3-33", "yyc3-45"]) == "yyc3-45"


def test_weighted_latency_picks_best_ratio():
    router = ModelRouter()
    router.nodes["yyc3-33"].latency = 1000.0  # 慢
    router.nodes["yyc3-45"].latency = 10.0  # 快
    assert router._select_by_weighted_latency(["yyc3-33", "yyc3-45"]) == "yyc3-45"


def test_random_strategy_uses_choice(monkeypatch):
    router = ModelRouter()
    monkeypatch.setattr(random_module, "choice", lambda nodes: nodes[-1])
    assert router._select_by_random(["a", "b", "c"]) == "c"


# ── ADAPTIVE 策略 ─────────────────────────────────────────


def test_adaptive_weighted_pick_boundary(monkeypatch):
    """加权随机两端确定性：r≈0 选中候选首项（慢节点），r≈total 选中快节点。

    权重比极端（5000ms vs 1ms，延迟归一上限 5.0）→ 快节点占权重 ~96%，
    r≈total 恒命中快节点；两端断言不依赖随机抽样，无统计抖动。"""
    router = ModelRouter()
    monkeypatch.setattr(router, "_recompute_weight", lambda nid: None)  # 关闭懒重算
    router.nodes["yyc3-33"].ewma_latency = 5000.0  # 慢
    router.nodes["yyc3-45"].ewma_latency = 1.0  # 快
    router.nodes["yyc3-33"].dynamic_weight = 1.0
    router.nodes["yyc3-45"].dynamic_weight = 1.0

    monkeypatch.setattr(random_module, "uniform", lambda a, b: b * 0.999)
    assert router._select_adaptive(["yyc3-33", "yyc3-45"]) == "yyc3-45"

    monkeypatch.setattr(random_module, "uniform", lambda a, b: 0.0)
    assert router._select_adaptive(["yyc3-33", "yyc3-45"]) == "yyc3-33"


def test_adaptive_zero_r_picks_first(monkeypatch):
    router = ModelRouter()
    monkeypatch.setattr(router, "_recompute_weight", lambda nid: None)
    monkeypatch.setattr(random_module, "uniform", lambda a, b: 0.0)
    assert router._select_adaptive(["yyc3-33", "yyc3-45"]) == "yyc3-33"


# ── EWMA 数学与状态升降级 ─────────────────────────────────


def _seed_records(node, records):
    node.recent_records.clear()
    node.recent_records.extend(records)


def test_recompute_ewma_math(monkeypatch):
    router = ModelRouter()
    clock = _fake_time(monkeypatch)
    node = router.nodes["yyc3-22"]
    node.ewma_latency = 100.0
    node.ewma_error_rate = 0.0
    clock[0] = 5000.0
    _seed_records(
        node,
        [
            RequestRecord(timestamp=4990.0, latency=200.0, success=True),
            RequestRecord(timestamp=4995.0, latency=400.0, success=False),
        ],
    )
    router._recompute_weight("yyc3-22")
    # avg_lat=300, error_rate=0.5；alpha=0.3
    assert node.ewma_latency == pytest.approx(0.3 * 300.0 + 0.7 * 100.0)
    assert node.ewma_error_rate == pytest.approx(0.3 * 0.5)
    assert node.success_rate == pytest.approx(1.0 - 0.15)
    assert node.last_weight_update == 5000.0


def test_recompute_promotes_degraded_and_recovers(monkeypatch):
    router = ModelRouter()
    clock = _fake_time(monkeypatch)
    node = router.nodes["yyc3-22"]
    clock[0] = 5000.0
    # 注意：升降级判定基于 EWMA 平滑值（alpha=0.3），非原始错误率。
    # 单批 3 败 2 成（原始 60%）→ ewma=0.18 > 0.15 → DEGRADED
    _seed_records(
        node,
        [
            RequestRecord(timestamp=4990.0, latency=100.0, success=False),
            RequestRecord(timestamp=4991.0, latency=100.0, success=False),
            RequestRecord(timestamp=4992.0, latency=100.0, success=False),
            RequestRecord(timestamp=4995.0, latency=100.0, success=True),
            RequestRecord(timestamp=4998.0, latency=100.0, success=True),
        ],
    )
    router._recompute_weight("yyc3-22")
    assert node.ewma_error_rate > router.DEGRADED_ERROR_THRESHOLD
    assert node.status == NodeStatus.DEGRADED
    # 恢复：连续多批全成功，ewma 按 (1-α)^n 衰减至 <7.5% 且延迟 <5s → HEALTHY
    for _ in range(4):
        _seed_records(
            node,
            [RequestRecord(timestamp=4999.0, latency=100.0, success=True) for _ in range(10)],
        )
        router._recompute_weight("yyc3-22")
    assert node.ewma_error_rate < router.DEGRADED_ERROR_THRESHOLD / 2
    assert node.status == NodeStatus.HEALTHY


def test_recompute_ignores_stale_records(monkeypatch):
    router = ModelRouter()
    clock = _fake_time(monkeypatch)
    node = router.nodes["yyc3-22"]
    node.ewma_latency = 123.0
    clock[0] = 5000.0
    _seed_records(node, [RequestRecord(timestamp=1000.0, latency=9999.0, success=False)])
    router._recompute_weight("yyc3-22")
    assert node.ewma_latency == 123.0  # 全部记录超 5min 窗口 → 不变
    assert node.status == NodeStatus.HEALTHY


def test_recompute_no_records_is_noop():
    router = ModelRouter()
    node = router.nodes["yyc3-22"]
    node.ewma_latency = 77.0
    router._recompute_weight("yyc3-22")  # 无记录直接返回
    assert node.ewma_latency == 77.0


# ── 反馈循环 ──────────────────────────────────────────────


def test_record_result_updates_load_and_failures():
    router = ModelRouter()
    node = router.nodes["yyc3-22"]
    node.current_load = 1
    before_failed = node.failed_requests
    _run(router.record_result("yyc3-22", "llama3.2", latency=120.0, success=False, tokens=7))
    assert node.current_load == 0
    assert node.failed_requests == before_failed + 1
    assert len(node.recent_records) == 1
    assert node.recent_records[0].tokens == 7


def test_record_result_load_never_negative():
    router = ModelRouter()
    node = router.nodes["yyc3-22"]
    node.current_load = 0
    _run(router.record_result("yyc3-22", "llama3.2", latency=50.0, success=True))
    assert node.current_load == 0


def test_record_result_unknown_node_is_noop():
    router = ModelRouter()
    _run(router.record_result("ghost", "m", latency=1.0, success=True))  # 不抛即通过


def test_record_result_lazy_recompute_triggers(monkeypatch):
    router = ModelRouter()
    clock = _fake_time(monkeypatch)
    node = router.nodes["yyc3-22"]
    node.ewma_latency = 100.0
    clock[0] = 5000.0
    node.last_weight_update = 5000.0 - router.WEIGHT_UPDATE_INTERVAL - 1  # 已超间隔
    _run(router.record_result("yyc3-22", "llama3.2", latency=400.0, success=True))
    assert node.ewma_latency != 100.0  # 懒重算已发生


# ── 健康检查 ──────────────────────────────────────────────


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code


class _HCClient:
    """按脚本响应/抛异常的 httpx.AsyncClient 桩"""

    def __init__(self, script):
        self.script = list(script)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        item = self.script.pop(0) if self.script else _Resp(200)
        if isinstance(item, Exception):
            raise item
        return item


def _patch_httpx(monkeypatch, script):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _HCClient(script))


def test_health_check_success_keeps_degraded(monkeypatch):
    router = ModelRouter()
    router.nodes["yyc3-33"].status = NodeStatus.DEGRADED
    _patch_httpx(monkeypatch, [_Resp(200)])
    _run(router._check_node_health("yyc3-33"))
    assert router.nodes["yyc3-33"].status == NodeStatus.DEGRADED  # 200 不清除降级
    assert router.nodes["yyc3-33"].latency > 0  # 实测延迟写回


def test_health_check_bad_status_marks_unhealthy(monkeypatch):
    router = ModelRouter()
    _patch_httpx(monkeypatch, [_Resp(503)])
    _run(router._check_node_health("yyc3-22"))
    assert router.nodes["yyc3-22"].status == NodeStatus.UNHEALTHY


def test_health_check_exception_marks_unhealthy_and_counts(monkeypatch):
    router = ModelRouter()
    before = router.nodes["yyc3-45"].failed_requests
    _patch_httpx(monkeypatch, [ConnectionError("down")])
    _run(router._check_node_health("yyc3-45"))
    assert router.nodes["yyc3-45"].status == NodeStatus.UNHEALTHY
    assert router.nodes["yyc3-45"].failed_requests == before + 1


def test_health_check_covers_all_nodes(monkeypatch):
    router = ModelRouter()
    _patch_httpx(monkeypatch, [_Resp(200)] * len(router.nodes))
    _run(router.health_check())
    assert all(n.status == NodeStatus.HEALTHY for n in router.nodes.values())


# ── 管理接口 ──────────────────────────────────────────────


def test_release_node_floor_and_fail_count():
    router = ModelRouter()
    node = router.nodes["yyc3-22"]
    node.current_load = 1
    before = node.failed_requests
    router.release_node("yyc3-22", success=False)
    assert node.current_load == 0
    assert node.failed_requests == before + 1
    router.release_node("yyc3-22")  # 再次释放不越界
    assert node.current_load == 0
    router.release_node("ghost")  # 未知节点静默


def test_add_remove_node():
    router = ModelRouter()
    router.add_node(NodeInfo(node_id="n-9", node_type="ollama", models=["m"], capacity=10))
    assert "n-9" in router.nodes
    router.remove_node("n-9")
    assert "n-9" not in router.nodes
    router.remove_node("n-9")  # 幂等


def test_get_node_stats_shape():
    router = ModelRouter()
    router.nodes["yyc3-22"].current_load = 3
    stats = router.get_node_stats()
    assert set(stats) == set(router.nodes)
    s = stats["yyc3-22"]
    for key in (
        "status",
        "current_load",
        "capacity",
        "ewma_latency",
        "ewma_error_rate",
        "dynamic_weight",
        "success_rate",
        "recent_samples",
    ):
        assert key in s
    assert s["current_load"] == 3
    assert s["recent_samples"] == 0
