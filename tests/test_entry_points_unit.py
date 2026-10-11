#!/usr/bin/env python3
"""
@file test_entry_points_unit.py
@description 容器入口（orchestrator_entry / worker_entry）纯单元测试——0% 盲区攻坚
@author: YanYuCloudCube Team
@tags [test,entrypoint,a2a,unit]

背景：api/orchestrator_entry.py（41 语句）、api/worker_entry.py（25 语句）
此前 0% 覆盖（21 号审计报告 §三 P2-2）。两入口均为长驻进程（signal + 事件循环），
测试策略：桩替全部长驻协程（run_forever/observe_loop/ship_loop/run_workers），
验证任务编排组合、参数透传与 main() 启动-收敛闭环。
"""

import asyncio
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

oe = importlib.import_module("app.orchestrator_entry")
we = importlib.import_module("app.worker_entry")

pytestmark = pytest.mark.unit


class _Recorder:
    """记录调用的长驻协程桩"""

    def __init__(self, log, name):
        self.log = log
        self.name = name

    async def run(self):
        self.log.append(self.name)


@pytest.fixture()
def a2a_stubs(monkeypatch):
    """桩替 a2a_result/a2a_metrics/a2a_audit 的长驻入口"""
    from app.services import a2a_audit, a2a_metrics, a2a_result

    log = []

    class _Hub:
        async def run_forever(self):
            log.append("hub")

    monkeypatch.setattr(a2a_result, "result_hub", lambda: _Hub())
    monkeypatch.setattr(a2a_metrics, "observe_loop", _Recorder(log, "metrics").run)
    monkeypatch.setattr(a2a_audit, "ship_loop", _Recorder(log, "audit").run)
    return log, a2a_audit


# ── orchestrator_entry._run 任务编排 ──────────────────────


def test_run_all_tasks(a2a_stubs, monkeypatch):
    log, a2a_audit = a2a_stubs
    monkeypatch.setattr(a2a_audit, "_enabled", lambda: True)
    asyncio.run(oe._run(with_metrics=True, with_audit=True))
    assert sorted(log) == ["audit", "hub", "metrics"]


def test_run_metrics_only(a2a_stubs, monkeypatch):
    log, a2a_audit = a2a_stubs
    monkeypatch.setattr(a2a_audit, "_enabled", lambda: True)
    asyncio.run(oe._run(with_metrics=True, with_audit=False))
    assert sorted(log) == ["hub", "metrics"]


def test_run_audit_disabled_env(a2a_stubs, monkeypatch):
    """--with-audit 但环境开关关闭 → 不启 shipper"""
    log, a2a_audit = a2a_stubs
    monkeypatch.setattr(a2a_audit, "_enabled", lambda: False)
    asyncio.run(oe._run(with_metrics=False, with_audit=True))
    assert log == ["hub"]


def test_main_completes_and_sets_consumer(monkeypatch):
    """main() 启动-收敛闭环 + --consumer 透传环境变量"""
    ran = {}

    async def _fake_run(with_metrics, with_audit):
        ran["metrics"] = with_metrics
        ran["audit"] = with_audit

    monkeypatch.setattr(oe, "_run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["orchestrator-entry", "--no-metrics", "--consumer", "c-9"])
    monkeypatch.delenv("A2A_RESULT_CONSUMER", raising=False)
    oe.main()
    assert ran == {"metrics": False, "audit": False}
    assert os.environ.get("A2A_RESULT_CONSUMER") == "c-9"


def test_main_default_flags(monkeypatch):
    ran = {}

    async def _fake_run(with_metrics, with_audit):
        ran["metrics"] = with_metrics

    monkeypatch.setattr(oe, "_run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["orchestrator-entry"])
    oe.main()
    assert ran["metrics"] is True  # 缺省 metrics 开


# ── worker_entry.main ─────────────────────────────────────


def test_worker_entry_main(monkeypatch):
    from app.services import agent_workers

    ran = {}

    def _fake_ids():
        return ["语枢·未来", "言启·象限"]

    async def _fake_run(ids):
        ran["ids"] = list(ids)

    monkeypatch.setattr(agent_workers, "worker_agent_ids", _fake_ids)
    monkeypatch.setattr(agent_workers, "run_workers", _fake_run)
    monkeypatch.setattr(sys, "argv", ["worker-entry"])
    we.main()
    assert ran["ids"] == ["语枢·未来", "言启·象限"]
