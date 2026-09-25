#!/usr/bin/env python3
"""
@file test_a2a_worker.py
@description 业务 Agent 外置 Worker 测试——消费者组原语（ACK/重试/DLQ）/任务分发/提交端点/端到端闭环
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-26
@tags [test,a2a,worker,stream,integration]

Redis 以内存桩替（消费者组语义简化模拟：">" 只投递 last_delivered 之后的新消息），
零外部依赖；异步路径经 asyncio.run 桥接（项目无 pytest-asyncio，范式同 test_a2a_protocol）；
测试密钥值运行时随机生成（凭据零硬编码）。
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))
# 密钥读 conftest 统一注入值（收集顺序加固：测试文件只读不写，详见 tests/conftest.py）
_TEST_API_KEY = os.environ["API_KEYS"]
_TEST_RUNNER_KEY = os.environ["ADMIN_API_KEYS"]

import pytest  # noqa: E402
from redis.exceptions import ResponseError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import a2a_protocol as proto  # noqa: E402
from app.services import agent_workers as workers_mod  # noqa: E402

pytestmark = pytest.mark.integration


def _auth():
    return {"X-API-Key": _TEST_API_KEY}


class _FakeAsyncRedis:
    """异步 Redis 内存桩：Hash + Stream（消费者组/重试计数/DLQ 所需面）。

    消费者组简化语义：xreadgroup ">" 投递 (stream, group) 内 last_delivered 之后
    的全部新消息（count 截断），投递即记 delivered；xack 记入 acked 集合。
    """

    def __init__(self):
        self.hash: dict = {}
        self.streams: dict = {}  # stream -> [(msg_id, fields)]
        self.groups: dict = {}  # (stream, group) -> {"last_delivered": id, "acked": set}
        self.retry_counters: dict = {}
        self._seq = 0

    # ── Hash（注册中心）──
    async def hget(self, key, field):
        return self.hash.get(field)

    async def hset(self, key, field, value):
        self.hash[field] = value

    async def hgetall(self, key):
        return dict(self.hash)

    # ── Stream ──
    async def xadd(self, stream, fields, maxlen=None, approximate=None):
        self._seq += 1
        msg_id = f"{self._seq}-1"
        self.streams.setdefault(stream, []).append((msg_id, dict(fields)))
        return msg_id

    async def xrange(self, stream, min="-", max="+", count=None):
        entries = self.streams.get(stream, [])
        if min != "-" and max != "-":
            return [(i, f) for i, f in entries if i == min]  # 精确 id 查询（nack DLQ 迁移）
        return list(entries)

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        key = (stream, group)
        if key in self.groups:
            raise ResponseError("BUSYGROUP Consumer Group name already exists")
        self.groups[key] = {"last_delivered": "0", "acked": set()}

    async def xreadgroup(self, groupname, consumername, streams, count=None, block=None):
        stream, _from = next(iter(streams.items()))
        key = (stream, groupname)
        state = self.groups.setdefault(key, {"last_delivered": "0", "acked": set()})
        entries = self.streams.get(stream, [])
        pending = [
            (i, f)
            for i, f in entries
            if int(i.split("-")[0]) > int(state["last_delivered"].split("-")[0])
        ]
        batch = pending[: count or len(pending)]
        if batch:
            state["last_delivered"] = batch[-1][0]
        return [(stream, batch)] if batch else []

    async def xack(self, stream, groupname, *msg_ids):
        state = self.groups.setdefault((stream, groupname), {"last_delivered": "0", "acked": set()})
        state["acked"].update(msg_ids)
        return len(msg_ids)

    # ── 重试计数 ──
    async def incr(self, key):
        self.retry_counters[key] = self.retry_counters.get(key, 0) + 1
        return self.retry_counters[key]

    async def expire(self, key, ttl):
        return True


@pytest.fixture()
def fake_redis(monkeypatch):
    """内存桩替换 a2a_protocol 的异步 Redis 客户端（任务通道 + 注册中心 + 审计流）。"""
    fake = _FakeAsyncRedis()
    monkeypatch.setattr(proto, "redis_client", fake)
    return fake


@pytest.fixture()
def clean_instances():
    """Agent 实例缓存隔离（跨用例零状态）。"""
    workers_mod._instances.clear()
    yield
    workers_mod._instances.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _seed_task(fake, agent_id, task_type, payload, trace_id="t-seed"):
    """向目标 Agent 任务流预置一条信封消息，返回 stream_msg_id。"""
    message = proto.build_message(
        trace_id=trace_id,
        msg_type="task_request",
        sender="gateway",
        receiver=agent_id,
        task_type=task_type,
        payload=payload,
    )
    return asyncio.run(proto.send_task_message(agent_id, message))


# ════════════════════ 消费者组原语 ════════════════════


class TestConsumerGroup:
    def test_ensure_group_idempotent(self, fake_redis):
        """BUSYGROUP 幂等容忍：重复建组不抛（镜像原型 _ensure_group）。"""
        stream = proto.task_stream("yushu-wanwu-001")
        asyncio.run(proto.ensure_group(stream, "g-1"))
        asyncio.run(proto.ensure_group(stream, "g-1"))  # 不抛即通过

    def test_send_poll_roundtrip(self, fake_redis):
        """投递 → 消费者组读取：信封字段与 payload 反序列化完整往返。"""
        message = proto.build_message(
            trace_id="t-rt",
            msg_type="task_request",
            sender="gateway",
            receiver="yushu-wanwu-001",
            task_type="data_analysis",
            payload={"input": "分析营收"},
        )
        asyncio.run(proto.send_task_message("yushu-wanwu-001", message))
        got = asyncio.run(
            proto.poll_messages(proto.task_stream("yushu-wanwu-001"), "g", "c", block_ms=10)
        )
        assert len(got) == 1
        stream_msg_id, msg = got[0]
        assert msg["trace_id"] == "t-rt"
        assert msg["payload"] == {"input": "分析营收"}  # 已反序列化
        assert stream_msg_id.endswith("-1")

    def test_nack_retry_then_dead_letter(self, fake_redis):
        """nack 重试链：前 2 次仅计数，第 3 次（达 MAX_RETRY）迁移死信流并 ACK。"""
        stream = proto.task_stream("yushu-wanwu-001")
        message = proto.build_message(
            trace_id="t-dlq",
            msg_type="task_request",
            sender="gateway",
            receiver="yushu-wanwu-001",
            task_type="data_analysis",
            payload={"input": "boom"},
        )
        msg_id = asyncio.run(proto.send_task_message("yushu-wanwu-001", message))
        asyncio.run(proto.ensure_group(stream, "g"))
        assert asyncio.run(proto.nack_message(stream, "g", msg_id, "err-1", "t-dlq")) == 1
        assert asyncio.run(proto.nack_message(stream, "g", msg_id, "err-2", "t-dlq")) == 2
        assert proto.dlq_stream("yushu-wanwu-001") not in fake_redis.streams  # 未达限不入死信
        count = asyncio.run(proto.nack_message(stream, "g", msg_id, "err-3", "t-dlq"))
        assert count == proto.MAX_RETRY
        dlq = fake_redis.streams[proto.dlq_stream("yushu-wanwu-001")]
        assert len(dlq) == 1
        assert dlq[0][1]["trace_id"] == "t-dlq"  # 原文迁移
        assert msg_id in fake_redis.groups[(stream, "g")]["acked"]  # 迁移后 ACK
        # 审计留痕
        audits = fake_redis.streams.get(proto.AUDIT_STREAM, [])
        assert any(e.get("action") == "dead_letter" for _, e in audits)

    def test_retry_counter_ttl_key(self, fake_redis):
        """重试计数按 stream_msg_id 独立（不同消息互不串计数）。"""
        stream = proto.task_stream("yushu-wanwu-001")
        id_a = asyncio.run(proto.send_task_message("yushu-wanwu-001", {"trace_id": "a"}))
        id_b = asyncio.run(proto.send_task_message("yushu-wanwu-001", {"trace_id": "b"}))
        asyncio.run(proto.nack_message(stream, "g", id_a, "e"))
        assert asyncio.run(proto.nack_message(stream, "g", id_b, "e")) == 1  # b 首次


# ════════════════════ 任务分发（Mock 模式零网络）════════════════════


class TestTaskDispatch:
    def test_data_analysis(self, clean_instances):
        out = workers_mod.handle_task("data_analysis", {"input": "分析本季度营收"})
        assert "语枢·万物" in out["output"]

    def test_trend_forecast(self, clean_instances):
        out = workers_mod.handle_task(
            "trend_forecast",
            {"input": "预测营收", "metric_name": "营收", "historical_data": [100, 120, 130]},
        )
        assert out["output"]["status"] == "success"
        assert out["output"]["metric"] == "营收"

    def test_qualitative_analysis(self, clean_instances):
        out = workers_mod.handle_task("qualitative_analysis", {"input": "行业趋势研判"})
        assert "预见·先知" in out["output"]

    def test_report_polish(self, clean_instances):
        out = workers_mod.handle_task("report_polish", {"input": "原始报告内容"})
        assert "创想·灵韵" in out["output"]

    def test_creative_brainstorm(self, clean_instances):
        out = workers_mod.handle_task("creative_brainstorm", {"input": "智能网关方向"})
        assert isinstance(out["output"], list)

    def test_unknown_task_type(self, clean_instances):
        with pytest.raises(ValueError, match="未知 task_type"):
            workers_mod.handle_task("no_such_type", {"input": "x"})

    def test_missing_input(self, clean_instances):
        with pytest.raises(ValueError, match="payload.input"):
            workers_mod.handle_task("data_analysis", {"query": "缺 input"})


# ════════════════════ Worker 消费一轮 ════════════════════


class TestWorkerRunOnce:
    def _worker(self):
        return workers_mod.AgentWorker("yushu-wanwu-001")

    def test_run_once_success(self, fake_redis, clean_instances):
        """成功路径：handle → 结果回执流 task_result + ACK + 审计。"""
        w = self._worker()
        asyncio.run(proto.ensure_group(w.stream, w.group))
        _seed_task(fake_redis, "yushu-wanwu-001", "data_analysis", {"input": "分析"}, "t-ok")
        processed = asyncio.run(w.run_once())
        assert processed == 1
        results = fake_redis.streams[proto.RESULT_STREAM]
        assert results[0][1]["msg_type"] == "task_result"
        assert '"success": true' in results[0][1]["payload"]
        audits = [e for _, e in fake_redis.streams[proto.AUDIT_STREAM]]
        assert any(
            a["action"] == "task_result" and a["auditor"] == "yushu-wanwu-001" for a in audits
        )

    def test_run_once_failure_nack(self, fake_redis, clean_instances, monkeypatch):
        """失败路径：nack 计数 1（可重试）+ error 回执 + task_retry 审计。"""

        def _boom(task_type, payload):
            raise RuntimeError("推理通道异常")

        monkeypatch.setattr(workers_mod, "handle_task", _boom)
        w = self._worker()
        asyncio.run(proto.ensure_group(w.stream, w.group))
        _seed_task(fake_redis, "yushu-wanwu-001", "data_analysis", {"input": "x"}, "t-fail")
        processed = asyncio.run(w.run_once())
        assert processed == 1
        assert fake_redis.retry_counters[f"{proto.RETRY_KEY_PREFIX}1-1"] == 1
        results = fake_redis.streams[proto.RESULT_STREAM]
        assert results[0][1]["msg_type"] == "error"
        audits = [e for _, e in fake_redis.streams[proto.AUDIT_STREAM]]
        assert any(a["action"] == "task_retry" for a in audits)

    def test_run_once_empty(self, fake_redis, clean_instances):
        """空流空轮：返回 0，不产生任何副作用。"""
        w = self._worker()
        asyncio.run(proto.ensure_group(w.stream, w.group))
        assert asyncio.run(w.run_once()) == 0

    def test_consumer_name_unique(self):
        """消费者名含 agent_id（多 Agent 消费者不串）。"""
        w = workers_mod.AgentWorker("yujian-xianzhi-001")
        assert "yujian-xianzhi-001" in w.consumer
        assert w.group == "group-yujian-xianzhi-001"


# ════════════════════ 提交端点 + 端到端闭环 ════════════════════


class TestA2ATaskEndpoint:
    def test_submit_direct_receiver(self, client, fake_redis):
        """receiver 直投：202 + 信封落目标任务流。"""
        r = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "task_type": "data_analysis",
                "payload": {"input": "分析"},
                "receiver_agent_id": "yushu-wanwu-001",
            },
            headers=_auth(),
        )
        assert r.status_code == 202
        body = r.json()
        assert body["receiver"] == "yushu-wanwu-001"
        assert body["stream"] == "stream:agent:task:yushu-wanwu-001"
        assert body["status"] == "queued"
        seeded = fake_redis.streams["stream:agent:task:yushu-wanwu-001"]
        assert seeded[0][1]["msg_type"] == "task_request"

    def test_submit_capability_route(self, client, fake_redis):
        """capability 路由：在线卡片发现 → 投递至其任务流。"""
        asyncio.run(
            proto._registry_register(
                {
                    "agent_id": "yujian-xianzhi-002",
                    "capabilities": ["trend_forecast"],
                    "last_heartbeat": time.time(),
                }
            )
        )
        r = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "task_type": "trend_forecast",
                "payload": {"input": "x"},
                "capability": "trend_forecast",
            },
            headers=_auth(),
        )
        assert r.status_code == 202
        assert r.json()["receiver"] == "yujian-xianzhi-002"
        assert "stream:agent:task:yujian-xianzhi-002" in fake_redis.streams

    def test_submit_no_online_agent(self, client, fake_redis):
        """capability 无在线 Agent → 404 no_online_agent。"""
        r = client.post(
            "/v1/agent/a2a/tasks",
            json={"task_type": "t", "payload": {}, "capability": "never_existed"},
            headers=_auth(),
        )
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "no_online_agent"

    def test_submit_missing_route_target(self, client, fake_redis):
        """receiver 与 capability 均空 → 400。"""
        r = client.post(
            "/v1/agent/a2a/tasks",
            json={"task_type": "t", "payload": {}},
            headers=_auth(),
        )
        assert r.status_code == 400

    def test_end_to_end_submit_consume(self, client, fake_redis, clean_instances):
        """端到端：提交 → Worker 消费 → 结果回执闭环（submit → consume → result）。"""
        r = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "task_type": "data_analysis",
                "payload": {"input": "端到端"},
                "receiver_agent_id": "yushu-wanwu-001",
            },
            headers=_auth(),
        )
        assert r.status_code == 202
        w = workers_mod.AgentWorker("yushu-wanwu-001")
        asyncio.run(proto.ensure_group(w.stream, w.group))
        assert asyncio.run(w.run_once()) == 1
        results = fake_redis.streams[proto.RESULT_STREAM]
        envelope = proto.parse_message(dict(results[0][1]))
        assert envelope["trace_id"] == r.json()["trace_id"]
        assert envelope["payload"]["success"] is True
