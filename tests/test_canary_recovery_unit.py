#!/usr/bin/env python3
"""
@file test_canary_recovery_unit.py
@description Canary 自动回退落地 + 恢复探测状态机回归（2026-10-11 中期项闭环）
@author: YanYuCloudCube Team
@tags [test,canary,recovery,unit]

审计活捉背景（docs/0379-world-执行记录/21-深度审核与实况测试报告.md §四中期项）：
历史版本 canary_report_failure 达阈值仅打印「触发惰性回退」日志，weight=0 从未落库
（惰性回退依赖的 hash fails 字段无写入方）——自动回退事实不存在，更谈不上恢复。
本文件锁定修复后全链路：信号达阈值 → 回退落库（prev_weight 快照）→ 指数退避探测 →
连续成功自动恢复；以及人工接管（canary_set/delete）优先语义。
conftest._hermetic_redis 提供 fakeredis 实例（app.services.model_registry_svc 绑定已替换）。
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

from app.services import model_registry_svc as svc  # noqa: E402

pytestmark = pytest.mark.unit

ALIAS = "deepseek-v4-flash"
CANARY = "deepseek-v4-pro"


@pytest.fixture()
def clean_state():
    svc._canary_cache.clear()
    svc._recovery_watch.clear()
    yield
    svc._canary_cache.clear()
    svc._recovery_watch.clear()


def _run(coro):
    return asyncio.run(coro)


def _hash():
    return _run(svc.redis_client.hgetall(svc._canary_key(ALIAS)))


def _make_due(alias=ALIAS):
    """把观察项的下次探测时刻拨到过去（等价于退避到期）"""
    svc._recovery_watch[alias]["next"] = 0.0


class TestAutoRollbackLands:
    def test_threshold_rollback_lands(self, clean_state):
        """信号达阈值 → weight=0 真正落库 + prev_weight 快照 + 纳入观察集"""
        _run(svc.canary_set(ALIAS, ALIAS, CANARY, 20))
        for _ in range(svc._CANARY_FAIL_LIMIT):
            _run(svc.canary_report_failure(ALIAS))
        data = _hash()
        assert data["weight"] == "0"
        assert data["prev_weight"] == "20"
        assert ALIAS in svc._recovery_watch

    def test_below_threshold_no_rollback(self, clean_state):
        """阈值下信号只计数，不动 weight"""
        _run(svc.canary_set(ALIAS, ALIAS, CANARY, 20))
        for _ in range(svc._CANARY_FAIL_LIMIT - 1):
            _run(svc.canary_report_failure(ALIAS))
        assert _hash()["weight"] == "20"
        assert ALIAS not in svc._recovery_watch

    def test_rollback_idempotent(self, clean_state):
        """重复信号不覆盖 prev_weight、不重置观察退避（幂等守卫）"""
        _run(svc.canary_set(ALIAS, ALIAS, CANARY, 20))
        for _ in range(svc._CANARY_FAIL_LIMIT + 3):
            _run(svc.canary_report_failure(ALIAS))
        data = _hash()
        assert data["weight"] == "0"
        assert data["prev_weight"] == "20"

    def test_rollback_redis_down_no_raise(self, clean_state, monkeypatch):
        """回退写入 Redis 失败仅记日志，绝不向 chat 异常链二次抛错"""

        class _Down:
            async def hgetall(self, *a, **k):
                raise ConnectionError("down")

        monkeypatch.setattr(svc, "redis_client", _Down())
        _run(svc.canary_report_failure(ALIAS))  # 信号上报阶段即降级返回，不抛即通过


class TestRecoveryTick:
    @pytest.fixture()
    def rolled_back(self, clean_state, monkeypatch):
        """回退完成且探测可控的夹具：probe 结果由测试写 probe_result[0]"""
        _run(svc.canary_set(ALIAS, ALIAS, CANARY, 20))
        for _ in range(svc._CANARY_FAIL_LIMIT):
            _run(svc.canary_report_failure(ALIAS))
        probe_result = [True]

        async def _fake_probe(model):
            assert model == CANARY
            return probe_result[0]

        monkeypatch.setattr(svc, "_probe_canary_model", _fake_probe)
        return probe_result

    def test_success_restores_weight_after_two_strikes(self, rolled_back):
        """连续 2 次探测成功 → weight 恢复 prev_weight、清失败计数、摘出观察集"""
        _make_due()
        _run(svc.canary_recovery_tick())
        assert _hash()["weight"] == "0"  # 首次成功只计数，未恢复
        assert svc._recovery_watch[ALIAS]["successes"] == 1

        _make_due()
        _run(svc.canary_recovery_tick())
        data = _hash()
        assert data["weight"] == "20"
        assert ALIAS not in svc._recovery_watch
        # 失败计数键已清（下次回退周期重新计数）
        fail_key = f"yyc3:canary:fail:{ALIAS}"
        assert _run(svc.redis_client.exists(fail_key)) == 0

    def test_failure_backs_off_exponentially(self, rolled_back):
        """探测失败 → 成功计数清零、退避 ×2（30→60）、weight 保持 0"""
        rolled_back[0] = False
        _make_due()
        _run(svc.canary_recovery_tick())
        st = svc._recovery_watch[ALIAS]
        assert st["successes"] == 0
        assert st["backoff"] == svc._CANARY_RECOVERY_INITIAL_BACKOFF * 2
        assert st["next"] > 0
        assert _hash()["weight"] == "0"

    def test_failure_then_success_resets_streak(self, rolled_back):
        """失败清零连续成功计数：成功→失败→成功 不构成「连续 2 次」"""
        _make_due()
        _run(svc.canary_recovery_tick())  # 成功 #1
        rolled_back[0] = False
        _make_due()
        _run(svc.canary_recovery_tick())  # 失败，清零
        rolled_back[0] = True
        _make_due()
        _run(svc.canary_recovery_tick())  # 成功 #1（重新计）
        assert _hash()["weight"] == "0"
        assert svc._recovery_watch[ALIAS]["successes"] == 1

    def test_not_due_skips_probe(self, rolled_back, monkeypatch):
        """未到探测时刻不发起探测（退避期零请求）"""
        called = [0]

        async def _counting_probe(model):
            called[0] += 1
            return rolled_back[0]

        monkeypatch.setattr(svc, "_probe_canary_model", _counting_probe)
        svc._recovery_watch[ALIAS]["next"] = svc.time.time() + 9999
        _run(svc.canary_recovery_tick())
        assert called[0] == 0

    def test_manual_set_takes_over(self, rolled_back):
        """人工 canary_set 新权重 → 摘出观察集，自动恢复不再介入"""
        _run(svc.canary_set(ALIAS, ALIAS, CANARY, 50))
        assert ALIAS not in svc._recovery_watch
        _run(svc.canary_recovery_tick())  # 观察集已空，直接返回
        assert _hash()["weight"] == "50"

    def test_delete_removes_watch(self, rolled_back):
        _run(svc.canary_delete(ALIAS))
        assert ALIAS not in svc._recovery_watch

    def test_abnormal_prev_weight_no_restore(self, rolled_back):
        """prev_weight 缺失/异常 → 安全默认不恢复（待人工配置），摘出观察集"""
        _run(svc.redis_client.hset(svc._canary_key(ALIAS), "prev_weight", "0"))
        _make_due()
        _run(svc.canary_recovery_tick())
        _make_due()
        _run(svc.canary_recovery_tick())
        assert _hash()["weight"] == "0"
        assert ALIAS not in svc._recovery_watch

    def test_config_vanished_drops_watch(self, rolled_back):
        """探测前配置被删 → 摘出观察集，不再空转"""
        _run(svc.redis_client.delete(svc._canary_key(ALIAS)))
        _make_due()
        _run(svc.canary_recovery_tick())
        assert ALIAS not in svc._recovery_watch


class TestStartupRebuild:
    def test_rebuild_recovers_rolled_back_aliases(self, clean_state):
        """重启重建：weight=0 + prev_weight>0 的别名重回观察集（计数键须按段过滤）"""
        _run(svc.canary_set(ALIAS, ALIAS, CANARY, 20))
        _run(
            svc.redis_client.hset(
                svc._canary_key(ALIAS), mapping={"weight": "0", "prev_weight": "20"}
            )
        )
        # 健康中的别名不应被纳入
        _run(svc.canary_set("glm-4-flash", "glm-4-flash", "glm-4-flash-v2", 10))
        _run(svc.canary_report_failure(ALIAS))  # 顺手制造计数键验证过滤

        _run(svc._rebuild_watch_from_redis())
        assert ALIAS in svc._recovery_watch
        assert "glm-4-flash" not in svc._recovery_watch


class TestProbeCanaryModel:
    def test_probe_200_is_healthy(self, clean_state, monkeypatch):
        """探测与真实流量同路径：select → POST /chat/completions，200 判活"""
        from app.services.upstream_registry import registry

        class _U:
            base_url = "http://canary.test:8100"
            api_key = None

        monkeypatch.setattr(registry, "select", lambda model, capability="chat": _U())

        import httpx

        class _Resp:
            status_code = 200

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, headers=None):
                assert url == "http://canary.test:8100/v1/chat/completions"
                assert json["max_tokens"] == 1
                return _Resp()

        monkeypatch.setattr(httpx, "AsyncClient", _Client)
        assert _run(svc._probe_canary_model(CANARY)) is True

    def test_probe_select_miss_or_error_is_unhealthy(self, clean_state, monkeypatch):
        """选路失败 / 任意异常 → 判不活，绝不抛出"""
        from app.services.upstream_registry import registry

        monkeypatch.setattr(registry, "select", lambda model, capability="chat": None)
        assert _run(svc._probe_canary_model(CANARY)) is False

        def _boom(model, capability="chat"):
            raise RuntimeError("registry broken")

        monkeypatch.setattr(registry, "select", _boom)
        assert _run(svc._probe_canary_model(CANARY)) is False
