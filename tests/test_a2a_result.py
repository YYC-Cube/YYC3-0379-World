#!/usr/bin/env python3
"""
@file test_a2a_result.py
@description A2A 结果流消费端测试——聚合等待（wait_one/wait_all）/挂起回收（XAUTOCLAIM）/批量消费/同步闭环端点
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-26
@tags [test,a2a,result,stream,integration]

Redis 以内存桩替（消费者组语义简化模拟：">" 只投递 last_delivered 之后的新消息；
投递记入 PEL 并记交付时刻，xautoclaim 按空闲阈值认领），零外部依赖；
异步路径经 asyncio.run 桥接（项目无 pytest-asyncio，范式同 test_a2a_worker）；
等待场景全部在单一事件循环内驱动（asyncio.Event 跨循环 set 不安全，不可多线程混驱）；
测试密钥值运行时随机生成（凭据零硬编码）。
"""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))
# 密钥读 conftest 统一注入值（收集顺序加固：测试文件只读不写，详见 tests/conftest.py）
_TEST_API_KEY = os.environ["API_KEYS"]
_TEST_RUNNER_KEY = os.environ["ADMIN_API_KEYS"]

import pytest  # noqa: E402
from redis.exceptions import ResponseError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import a2a_metrics  # noqa: E402
from app.services import a2a_result  # noqa: E402
from app.services import a2a_protocol as proto  # noqa: E402

pytestmark = pytest.mark.integration


def _auth():
    return {"X-API-Key": _TEST_API_KEY}


class _FakeAsyncRedis:
    """异步 Redis 内存桩：Stream + 消费者组（PEL 挂起/时钟/XAUTOCLAIM 所需面）。"""

    def __init__(self):
        self.hash: dict = {}  # 注册中心 Hash
        self.streams: dict = {}  # stream -> [(msg_id, fields)]
        self.groups: dict = {}  # (stream, group) -> {"last_delivered", "acked", "pending"}
        self.retry_counters: dict = {}
        self._seq = 0
        self.now = 0.0  # 毫秒时钟（advance 推进，模拟空闲时长）
        self._delivery: dict = {}  # (stream, msg_id) -> 交付时刻（投递即记）

    def advance(self, ms: float) -> None:
        self.now += ms

    def _state(self, stream, group):
        return self.groups.setdefault(
            (stream, group), {"last_delivered": "0", "acked": set(), "pending": []}
        )

    async def xadd(self, stream, fields, maxlen=None, approximate=None):
        self._seq += 1
        msg_id = f"{self._seq}-1"
        self.streams.setdefault(stream, []).append((msg_id, dict(fields)))
        return msg_id

    async def xlen(self, name):
        return len(self.streams.get(name, []))

    async def xrange(self, stream, min="-", max="+", count=None):
        entries = self.streams.get(stream, [])
        if min != "-" and max != "-":
            return [(i, f) for i, f in entries if i == min]
        return list(entries)

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        key = (stream, group)
        if key in self.groups:
            raise ResponseError("BUSYGROUP Consumer Group name already exists")
        self._state(stream, group)

    async def xreadgroup(self, groupname, consumername, streams, count=None, block=None):
        stream, _from = next(iter(streams.items()))
        state = self._state(stream, groupname)
        entries = self.streams.get(stream, [])
        fresh = [
            (i, f)
            for i, f in entries
            if int(i.split("-")[0]) > int(state["last_delivered"].split("-")[0])
        ]
        batch = fresh[: count or len(fresh)]
        if batch:
            state["last_delivered"] = batch[-1][0]
            state["pending"].extend(batch)
            for msg_id, _fields in batch:
                self._delivery[(stream, msg_id)] = self.now
        return [(stream, batch)] if batch else []

    async def xack(self, stream, groupname, *msg_ids):
        state = self._state(stream, groupname)
        state["acked"].update(msg_ids)
        state["pending"] = [(i, f) for i, f in state["pending"] if i not in msg_ids]
        return len(msg_ids)

    async def xautoclaim(
        self,
        stream,
        groupname,
        consumername,
        min_idle_time,
        start_id="0-0",
        count=None,
        justid=False,
    ):
        state = self._state(stream, groupname)
        claimed = [
            (i, f)
            for i, f in state["pending"]
            if self.now - self._delivery.get((stream, i), self.now) >= min_idle_time
        ][: count or 10]
        return ["0-0", claimed]  # 2 元响应（Redis 6.2 形态；协议层兼容 3 元）

    async def incr(self, key):
        self.retry_counters[key] = self.retry_counters.get(key, 0) + 1
        return self.retry_counters[key]

    async def expire(self, key, ttl):
        return True

    # ── Hash（注册中心，capability 路由端点所需面）──
    async def hget(self, key, field):
        return self.hash.get(field)

    async def hset(self, key, field, value):
        self.hash[field] = value

    async def hgetall(self, key):
        return dict(self.hash)

    # ── List（spend 队列，vk 记账路径所需面）──
    async def lpush(self, name, *values):
        self.spend_queue = [v for v in values] + getattr(self, "spend_queue", [])
        return len(self.spend_queue)


@pytest.fixture()
def fake_redis(monkeypatch):
    """内存桩替换协议层异步 Redis 客户端（结果流 + 任务流 + 注册中心 + 审计流 + vk 缓存）。

    vk 模块经 `from app.cache import redis_client` 持模块级自有绑定，需一并补丁
    （否则 TPM 滑窗 / spend 入队穿透到真实 Redis：限流放行、记账丢弃）。
    """
    fake = _FakeAsyncRedis()
    monkeypatch.setattr(proto, "redis_client", fake)
    monkeypatch.setattr("app.cache.redis_client", fake)
    monkeypatch.setattr("app.services.virtual_key_manager.redis_client", fake)
    return fake


@pytest.fixture()
def hub_clean():
    """ResultHub 单例与生命周期任务隔离（跨用例零状态）。"""
    a2a_result._hub = None
    a2a_result._hub_task = None
    yield
    a2a_result._hub = None
    a2a_result._hub_task = None


@pytest.fixture()
def client():
    return TestClient(app)


# ── vk（虚拟密钥）fixture：TOP1 计费门控 / 中间件记账测试 ────────────

_TEST_VK_ID = "vk-test-a2a"
_TEST_VK_PLAINTEXT = "vk-" + uuid.uuid4().hex[:16]


def _vk_record(**over):
    """虚拟密钥记录（budget=0 不限预算 / 空白名单 / 无 TPM 限流为默认放行态）。"""
    rec = {
        "id": _TEST_VK_ID,
        "key_hash": "unused",
        "name": "pytest-vk",
        "owner": "pytest",
        "model_whitelist": [],
        "monthly_budget_usd": 0.0,
        "spent_usd": 0.0,
        "rate_limit_tpm": 0,
        "status": "active",
    }
    rec.update(over)
    return rec


@pytest.fixture()
def vk_unlimited(monkeypatch):
    """vk 校验链桩：任意密钥 → 默认放行 vk 记录（不经 Redis/PG）；返回桩记录。"""
    rec = _vk_record()
    _patch_vk_auth(monkeypatch, rec)
    return rec


def _make_async(fn):
    """同步函数 → 异步可调用包装（async def lambda 语法不支持）。"""

    async def wrapper(*a, **kw):
        return fn(*a, **kw)

    return wrapper


def _patch_vk_auth(monkeypatch, rec):
    """vk 校验链桩：强制 vk 分支（authenticate 返回桩记录 + 静态 Key 校验禁用）。

    防降级：vk 明文与 conftest 静态 API_KEYS 不同源，若 authenticate 返回 None 会走
    verify_api_key 命中静态键而误判为静态身份；故同时 disable 静态/管理键命中。
    """
    monkeypatch.setattr(
        "app.services.virtual_key_manager.vk_manager.authenticate",
        _make_async(lambda _key: dict(rec)),
    )
    monkeypatch.setattr(
        "app.middleware.auth.AuthMiddleware._authenticate_vk_or_static",
        _make_async(lambda self, request, key: (True, {"type": "virtual_key", "vk": dict(rec)})),
    )


@pytest.fixture()
def vk_expired(monkeypatch):
    """vk 校验链桩：预算耗尽（spent > budget>0）→ 402 预算闸门触发。"""
    rec = _vk_record(monthly_budget_usd=1.0, spent_usd=2.0)
    _patch_vk_auth(monkeypatch, rec)
    return rec


async def _send_result(
    trace_id, sender="yushu-wanwu-001", msg_type="task_result", data=None
) -> str:
    """向结果流写入一条回执信封（async 原语：可嵌套进场景事件循环）。"""
    message = proto.build_message(
        trace_id=trace_id,
        msg_type=msg_type,
        sender=sender,
        receiver="gateway",
        task_type="data_analysis",
        payload=(
            {"success": True, "data": data or {"output": "ok"}}
            if msg_type == "task_result"
            else {"success": False, "error": "boom", "retryable": False}
        ),
    )
    return await proto.send_result_message(message)


def _seed_result(
    fake_unused, trace_id, sender="yushu-wanwu-001", msg_type="task_result", data=None
):
    """同步语境预置回执（asyncio.run 桥接）；事件循环内请用 _send_result。"""
    return asyncio.run(_send_result(trace_id, sender, msg_type, data))


async def _deliver_and_age(fake, trace_id) -> None:
    """模拟原消费者取走回执后宕机（投递出 PEL、不 ACK），并推时钟过空闲阈值。"""
    await _send_result(trace_id)
    got = await proto.poll_messages(
        proto.RESULT_STREAM, proto.RESULT_GROUP, "dead-consumer", block_ms=10
    )
    assert len(got) == 1
    fake.advance(a2a_result.CLAIM_IDLE_MS + 1)


def _deliver_then_age(fake, trace_id) -> None:
    """同步语境版（asyncio.run 桥接）；事件循环内请用 _deliver_and_age。"""
    asyncio.run(_deliver_and_age(fake, trace_id))


# ════════════════════ 消费者组与往返 ════════════════════


class TestConsumerGroup:
    def test_ensure_result_group_idempotent(self, fake_redis):
        """BUSYGROUP 幂等容忍：重复建组不抛。"""
        asyncio.run(proto.ensure_group(proto.RESULT_STREAM, proto.RESULT_GROUP))
        asyncio.run(proto.ensure_group(proto.RESULT_STREAM, proto.RESULT_GROUP))  # 不抛即通过

    def test_result_send_poll_roundtrip(self, fake_redis):
        """结果回执写入 → 消费者组读取：信封字段与 payload 反序列化完整往返。"""
        _seed_result(fake_redis, "t-rt", data={"output": "往返"})
        got = asyncio.run(
            proto.poll_messages(proto.RESULT_STREAM, proto.RESULT_GROUP, "c-1", block_ms=10)
        )
        assert len(got) == 1
        stream_msg_id, msg = got[0]
        assert msg["trace_id"] == "t-rt"
        assert msg["msg_type"] == "task_result"
        assert msg["payload"] == {"success": True, "data": {"output": "往返"}}  # 已反序列化


# ════════════════════ 聚合等待 ════════════════════


class TestAggregation:
    def test_wait_one_resolves_on_first_result(self, fake_redis, hub_clean):
        """wait_one：任一回执到达即唤醒（同循环内注册 → 派发 → 等待）。"""

        async def scenario():
            hub = a2a_result.ResultHub(consumer="t-hub")
            waiter = asyncio.create_task(hub.wait_one("t-w1", timeout=5))
            await asyncio.sleep(0.05)  # 等待者先注册
            await _send_result("t-w1", data={"output": "首回执"})
            processed = await hub.run_once()
            return await waiter, processed

        result, processed = asyncio.run(scenario())
        assert processed == 1
        assert result["msg_type"] == "task_result"
        assert result["payload"]["data"]["output"] == "首回执"

    def test_wait_one_timeout_raises(self, fake_redis, hub_clean):
        """wait_one 超时：无回执到达抛 asyncio.TimeoutError。"""
        hub = a2a_result.ResultHub(consumer="t-hub")
        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(hub.wait_one("t-timeout", timeout=0.05))

    def test_wait_all_fan_in(self, fake_redis, hub_clean):
        """wait_all：多 Agent 扇入等齐（2 份回执，1 成 1 败），快照进度 2/2。"""

        async def scenario():
            hub = a2a_result.ResultHub(consumer="t-hub")
            waiter = asyncio.create_task(hub.wait_all("t-fan", total=2, timeout=5))
            await asyncio.sleep(0.05)
            await _send_result("t-fan", sender="yushu-wanwu-001")
            await _send_result("t-fan", sender="yujian-xianzhi-001", msg_type="error")
            await hub.run_once()
            return await waiter

        snapshot = asyncio.run(scenario())
        assert snapshot["status"] == "completed"
        assert snapshot["progress"] == "2/2"
        assert snapshot["completed"] == 1
        assert snapshot["failed"] == 1
        assert set(snapshot["results"]) == {"yushu-wanwu-001", "yujian-xianzhi-001"}

    def test_same_sender_replay_idempotent(self, hub_clean):
        """同 sender 回执重放幂等：覆盖式存储不重复计数，total=2 不被重放凑满。"""
        agg = a2a_result._TraceAggregate("t-replay", total=2)
        agg.record({"sender": "a-1", "msg_type": "task_result", "payload": {}})
        agg.record({"sender": "a-1", "msg_type": "task_result", "payload": {"v": 2}})
        assert len(agg.results) == 1
        assert not agg.done.is_set()  # 重放不凑满
        assert agg.results["a-1"]["payload"] == {"v": 2}  # 后到覆盖

    def test_orphan_result_audited_and_acked(self, fake_redis, hub_clean):
        """孤儿回执（无等待者注册）：result_orphan 审计留痕后 ACK，不滞留 PEL。"""
        _seed_result(fake_redis, "t-orphan")
        hub = a2a_result.ResultHub(consumer="t-hub")
        assert asyncio.run(hub.run_once()) == 1
        audits = fake_redis.streams.get(proto.AUDIT_STREAM, [])
        assert any(e.get("action") == "result_orphan" for _, e in audits)
        state = fake_redis.groups[(proto.RESULT_STREAM, proto.RESULT_GROUP)]
        assert len(state["pending"]) == 0  # 已 ACK

    def test_status_not_found_then_running(self, hub_clean):
        """status：未注册 not_found；注册后 running（0/? 进度）。"""
        hub = a2a_result.ResultHub(consumer="t-hub")
        assert hub.status("t-x") == {"status": "not_found"}
        hub.register("t-x")
        assert hub.status("t-x")["status"] == "running"
        assert hub.status("t-x")["progress"] == "0/?"


# ════════════════════ 批量消费 ════════════════════


class TestRunOnce:
    def test_run_once_processes_batch(self, fake_redis, hub_clean):
        """批量消费：多条回执一轮全处理、全 ACK、各自派发到聚合器。"""
        hub = a2a_result.ResultHub(consumer="t-hub")
        hub.register("t-b1")
        hub.register("t-b2")
        hub.register("t-b3")
        _seed_result(fake_redis, "t-b1")
        _seed_result(fake_redis, "t-b2", msg_type="error")
        _seed_result(fake_redis, "t-b3")
        assert asyncio.run(hub.run_once(count=10, block_ms=10)) == 3
        assert hub.status("t-b1")["completed"] == 1
        assert hub.status("t-b2")["failed"] == 1
        assert hub.status("t-b3")["status"] == "completed"
        state = fake_redis.groups[(proto.RESULT_STREAM, proto.RESULT_GROUP)]
        assert len(state["pending"]) == 0 and len(state["acked"]) == 3

    def test_run_once_empty_returns_zero(self, fake_redis, hub_clean):
        """空轮消费：返回 0（不抛）。"""
        hub = a2a_result.ResultHub(consumer="t-hub")
        assert asyncio.run(hub.run_once()) == 0


# ════════════════════ 挂起回收（XAUTOCLAIM） ════════════════════


class TestReclaim:
    def test_claim_stale_returns_idle_messages(self, fake_redis):
        """XAUTOCLAIM 原语：空闲超阈值的挂起消息被认领，新鲜消息不认领。"""
        _deliver_then_age(fake_redis, "t-stale")
        _seed_result(fake_redis, "t-fresh")  # 未投递，天然不在 PEL
        claimed = asyncio.run(
            proto.claim_stale_messages(
                proto.RESULT_STREAM, proto.RESULT_GROUP, "t-c", min_idle_ms=60_000
            )
        )
        assert len(claimed) == 1
        assert claimed[0][1]["trace_id"] == "t-stale"

    def test_reclaim_once_dispatches_to_waiter(self, fake_redis, hub_clean):
        """回收唤醒等待者：原消费者宕机滞留的回执经 reclaim_once 派发，wait_one 解析。"""

        async def scenario():
            hub = a2a_result.ResultHub(consumer="t-hub")
            waiter = asyncio.create_task(hub.wait_one("t-rc", timeout=5))
            await asyncio.sleep(0.05)
            await _deliver_and_age(fake_redis, "t-rc")
            reclaimed = await hub.reclaim_once(min_idle_ms=60_000)
            return await waiter, reclaimed

        result, reclaimed = asyncio.run(scenario())
        assert reclaimed == 1
        assert result["msg_type"] == "task_result"
        assert result["payload"]["success"] is True

    def test_reclaim_orphan_audited(self, fake_redis, hub_clean):
        """回收无等待者的滞留回执：孤儿审计 + ACK（等待者超时离开后的兜底路径）。"""
        _deliver_then_age(fake_redis, "t-rc-orphan")
        hub = a2a_result.ResultHub(consumer="t-hub")
        assert asyncio.run(hub.reclaim_once(min_idle_ms=60_000)) == 1
        audits = fake_redis.streams.get(proto.AUDIT_STREAM, [])
        assert any(e.get("action") == "result_orphan" for _, e in audits)


# ════════════════════ 同步闭环端点 ════════════════════


class TestSyncEndpoint:
    def _body(self, **over):
        base = {
            "receiver_agent_id": "yushu-wanwu-001",
            "task_type": "data_analysis",
            "payload": {"input": "分析营收"},
            "timeout_seconds": 1,
        }
        base.update(over)
        return base

    def test_sync_requires_route(self, fake_redis, hub_clean, client):
        """路由校验：receiver 与 capability 均空 → 400。"""
        resp = client.post(
            "/v1/agent/a2a/tasks/sync", json=self._body(receiver_agent_id=None), headers=_auth()
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "receiver_agent_id 或 capability 必填其一"

    def test_sync_no_online_agent(self, fake_redis, hub_clean, client):
        """capability 无在线 Agent → 404。"""
        resp = client.post(
            "/v1/agent/a2a/tasks/sync",
            json=self._body(receiver_agent_id=None, capability="no_such_capability"),
            headers=_auth(),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "no_online_agent"

    def test_sync_timeout_returns_timeout(self, fake_redis, hub_clean, client):
        """等待超时：status=timeout，任务信封仍已投递（Worker 后续正常消费）。"""
        resp = client.post("/v1/agent/a2a/tasks/sync", json=self._body(), headers=_auth())
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "timeout"
        assert body["result"] is None
        tasks = fake_redis.streams.get(proto.task_stream("yushu-wanwu-001"), [])
        assert len(tasks) == 1 and tasks[0][1]["trace_id"] == body["trace_id"]

    def test_sync_success_closed_loop(self, fake_redis, hub_clean, client):
        """端到端闭环：投递 → 追平在途回执 → 同步返回 succeeded（payload 完整透传）。"""
        _seed_result(fake_redis, "trace-sync-1", data={"output": "分析完成"})
        resp = client.post(
            "/v1/agent/a2a/tasks/sync",
            json=self._body(trace_id="trace-sync-1", timeout_seconds=5),
            headers=_auth(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "succeeded"
        assert body["receiver"] == "yushu-wanwu-001"
        assert body["result"]["msg_type"] == "task_result"
        assert body["result"]["payload"]["data"]["output"] == "分析完成"
        # 任务信封已投递目标任务流
        tasks = fake_redis.streams.get(proto.task_stream("yushu-wanwu-001"), [])
        assert len(tasks) == 1 and tasks[0][1]["trace_id"] == "trace-sync-1"


# ════════════════════ vk 计费门控（TOP1：白名单/预算/TPM + 记账） ════════════════════


def _vk_auth_headers():
    return {"X-API-Key": _TEST_VK_PLAINTEXT}


class TestVkGates:
    def test_vk_model_whitelist_forbidden(self, fake_redis, hub_clean, client, monkeypatch):
        """vk 模型白名单：未授权 task_type → 403 model_not_allowed。"""
        rec = _vk_record(model_whitelist=["other_*"])
        _patch_vk_auth(monkeypatch, rec)
        resp = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "receiver_agent_id": "yushu-wanwu-001",
                "task_type": "data_analysis",
                "payload": {"input": "x"},
            },
            headers=_vk_auth_headers(),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"]["type"] == "model_not_allowed"

    def test_vk_budget_exceeded_402(self, fake_redis, hub_clean, client, vk_expired):
        """vk 预算耗尽：spent>budget → 402 budget_exceeded（对齐 chat 402 语义）。"""
        resp = client.post(
            "/v1/agent/a2a/tasks/sync",
            json={
                "receiver_agent_id": "yushu-wanwu-001",
                "task_type": "data_analysis",
                "payload": {"input": "x"},
                "timeout_seconds": 1,
            },
            headers=_vk_auth_headers(),
        )
        assert resp.status_code == 402
        assert resp.json()["detail"]["error"]["type"] == "budget_exceeded"

    def test_vk_tpm_rate_limit_429(self, fake_redis, hub_clean, client, monkeypatch):
        """vk TPM 滑窗限流：rate_limit_tpm=1 时首请求占用额度（est=1 恰达上限），次请求 → 429。

        check_tpm 语义：count + est - 1 <= limit 才放行；首请求 count=1/est=1/limit=1 恰放行，
        同窗口第二请求 count=2 超限拒绝（对齐 chat 链路 est_tokens=1 惯例）。
        """
        rec = _vk_record(rate_limit_tpm=1)
        _patch_vk_auth(monkeypatch, rec)
        body = {
            "receiver_agent_id": "yushu-wanwu-001",
            "task_type": "data_analysis",
            "payload": {"input": "x"},
        }
        first = client.post("/v1/agent/a2a/tasks", json=body, headers=_vk_auth_headers())
        assert first.status_code == 202  # 首请求恰占用窗口额度
        resp = client.post("/v1/agent/a2a/tasks", json=body, headers=_vk_auth_headers())
        assert resp.status_code == 429
        assert resp.json()["detail"]["error"]["type"] == "rate_limit_exceeded"

    def test_static_key_no_billing_queued(self, fake_redis, hub_clean, client):
        """静态 API Key（非 vk）：不计费不门控，spend 队列为空。"""
        resp = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "receiver_agent_id": "yushu-wanwu-001",
                "task_type": "data_analysis",
                "payload": {"input": "x"},
            },
            headers=_auth(),
        )
        assert resp.status_code == 202
        assert getattr(fake_redis, "spend_queue", []) == []

    def test_vk_request_enqueued_spend(self, fake_redis, hub_clean, client, vk_unlimited):
        """vk 身份 A2A 请求：中间件记账 → spend 队列入队（兜底成本，协同事务无 token usage）。"""
        resp = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "receiver_agent_id": "yushu-wanwu-001",
                "task_type": "data_analysis",
                "payload": {"input": "x"},
            },
            headers=_vk_auth_headers(),
        )
        assert resp.status_code == 202
        queue = getattr(fake_redis, "spend_queue", [])
        assert len(queue) == 1
        import json as _json

        entry = _json.loads(queue[0])
        assert entry["key_id"] == _TEST_VK_ID
        assert entry["capability"] == "agent"
        assert entry["cost_usd"] > 0  # 兜底常量


# ════════════════════ 多 Agent 编排入口（TOP2：扇出 + wait_all 等齐） ════════════════════


def _register_card(fake, agent_id):
    """注册中心预置在线 Agent 卡片（heartbeat=0 即当前时刻在线）。"""
    import time as _time

    card = {
        "agent_id": agent_id,
        "agent_name": agent_id,
        "role": "worker",
        "capabilities": ["data_analysis"],
        "endpoint": proto.task_stream(agent_id),
        "layer": "business",
        "status": "online",
        "heartbeat": int(_time.time()),
        "last_heartbeat": int(_time.time()),
    }
    fake.hash[agent_id] = __import__("json").dumps(card, ensure_ascii=False, default=str)


class TestOrchestration:
    def _body(self, **over):
        base = {
            "capability": "data_analysis",
            "task_type": "data_analysis",
            "payload": {"input": "编排"},
            "timeout_seconds": 1,
        }
        base.update(over)
        return base

    def test_orchestrate_no_online_404(self, fake_redis, hub_clean, client):
        """capability 无在线 Agent → 404 no_online_agent。"""
        resp = client.post("/v1/agent/a2a/orchestrate", json=self._body(), headers=_auth())
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "no_online_agent"

    def test_orchestrate_fan_out_waits_all(self, fake_redis, hub_clean, client):
        """端到端等齐：2 Agent 扇出 → 2 份回执扇入 wait_all 等齐 → completed，进度 2/2。

        同步 HTTP 客户端与异步回执不在同一事件循环，直接驱动 ResultHub 验证等齐语义。
        """
        _register_card(fake_redis, "yushu-wanwu-001")
        _register_card(fake_redis, "yujian-xianzhi-001")
        hub = a2a_result.ResultHub(consumer="t-orch")
        trace_id = "trace-orch-1"
        hub.register(trace_id, total=2)

        async def drive():
            for receiver in ("yushu-wanwu-001", "yujian-xianzhi-001"):
                message = proto.build_message(
                    trace_id=trace_id,
                    msg_type="task_request",
                    sender="gateway",
                    receiver=receiver,
                    task_type="data_analysis",
                    payload={"input": "编排"},
                    priority=5,
                )
                await proto.send_task_message(receiver, message)
            await _send_result(trace_id, sender="yushu-wanwu-001")
            await _send_result(trace_id, sender="yujian-xianzhi-001")
            await hub.run_once(count=10, block_ms=10)
            return await hub.wait_all(trace_id, total=2, timeout=5)

        snapshot = asyncio.run(drive())
        assert snapshot["status"] == "completed"
        assert snapshot["progress"] == "2/2"
        assert set(snapshot["results"]) == {"yushu-wanwu-001", "yujian-xianzhi-001"}


# ════════════════════ 成本直报（TOP2：X-A2A-Cost 按任务类型定价回填） ════════════════════


class TestCostHeader:
    def test_tasks_async_reports_cost_header(self, fake_redis, hub_clean, client):
        """异步投递：X-A2A-Cost = task_cost(data_analysis) = 0.002000（pricing 任务类型定价）。"""
        resp = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "receiver_agent_id": "yushu-wanwu-001",
                "task_type": "data_analysis",
                "payload": {"input": "x"},
            },
            headers=_auth(),
        )
        assert resp.status_code == 202
        assert resp.headers["X-A2A-Cost"] == "0.002000"

    def test_tasks_async_unknown_type_zero_cost(self, fake_redis, hub_clean, client):
        """未知 task_type：X-A2A-Cost = 0.000000（中间件兜底常量接管记账）。"""
        resp = client.post(
            "/v1/agent/a2a/tasks",
            json={
                "receiver_agent_id": "yushu-wanwu-001",
                "task_type": "never_heard_of",
                "payload": {"input": "x"},
            },
            headers=_auth(),
        )
        assert resp.status_code == 202
        assert resp.headers["X-A2A-Cost"] == "0.000000"

    def test_orchestrate_reports_aggregated_cost(self, fake_redis, hub_clean, client):
        """编排扇出：X-A2A-Cost = 单价 × 扇出数（2 Agent × 0.002 = 0.004000）。"""
        _register_card(fake_redis, "yushu-wanwu-001")
        _register_card(fake_redis, "yujian-xianzhi-001")
        resp = client.post(
            "/v1/agent/a2a/orchestrate",
            json={
                "capability": "data_analysis",
                "task_type": "data_analysis",
                "payload": {"input": "编排"},
                "timeout_seconds": 1,
            },
            headers=_auth(),
        )
        assert resp.status_code == 200
        assert resp.headers["X-A2A-Cost"] == "0.004000"


# ════════════════════ 可观测埋点（TOP3：DLQ/孤儿/回收 Counter + 快照 Gauge） ════════════════════


class TestObservability:
    def test_orphan_increments_counter(self, fake_redis, hub_clean):
        """孤儿回执 → a2a_result_orphan_total 计数 +1。"""
        before = _counter_value(a2a_metrics._result_orphan)
        _seed_result(fake_redis, "t-obs-orphan")
        hub = a2a_result.ResultHub(consumer="t-obs")
        asyncio.run(hub.run_once())
        assert _counter_value(a2a_metrics._result_orphan) == before + 1

    def test_reclaim_increments_counter(self, fake_redis, hub_clean):
        """挂起回收 → a2a_result_reclaimed_total 计数 +N（按认领条数）。"""
        _deliver_then_age(fake_redis, "t-obs-rc")
        hub = a2a_result.ResultHub(consumer="t-obs")
        before = _counter_value(a2a_metrics._result_reclaimed)
        assert asyncio.run(hub.reclaim_once(min_idle_ms=60_000)) == 1
        assert _counter_value(a2a_metrics._result_reclaimed) == before + 1

    def test_refresh_gauges_snapshots(self, fake_redis, hub_clean, monkeypatch):
        """快照采集：结果流长度 + DLQ 深度（XLEN）回填 Gauge 摘要。"""
        monkeypatch.setenv("A2A_WORKER_AGENTS", "yushu-wanwu-001")
        # 结果流预置 2 条；yushu DLQ 预置 1 条
        _seed_result(fake_redis, "t-g1")
        _seed_result(fake_redis, "t-g2")

        async def _seed_dlq():
            message = proto.build_message(
                trace_id="t-dlq",
                msg_type="task_request",
                sender="gateway",
                receiver="yushu-wanwu-001",
                task_type="data_analysis",
                payload={},
            )
            await proto.redis_client.xadd(
                proto.dlq_stream("yushu-wanwu-001"), proto._stringify(message)
            )

        asyncio.run(_seed_dlq())
        summary = asyncio.run(a2a_metrics.refresh_gauges())
        assert summary["result_stream_len"] == 2
        assert summary["dlq_depths"].get("yushu-wanwu-001") == 1

    def test_infer_survivable_env(self, monkeypatch):
        """受控环境解析：SURVIVABLE_ENV 优先，POD_NAMESPACE 回退，均空 None。"""
        monkeypatch.delenv("SURVIVABLE_ENV", raising=False)
        monkeypatch.delenv("POD_NAMESPACE", raising=False)
        assert a2a_metrics.infer_survivable_env() is None
        monkeypatch.setenv("POD_NAMESPACE", "prod")
        assert a2a_metrics.infer_survivable_env() == "prod"
        monkeypatch.setenv("SURVIVABLE_ENV", "staging")
        assert a2a_metrics.infer_survivable_env() == "staging"


def _counter_value(counter) -> float:
    """安全读取 Prometheus Counter 值（兼容版本差异，同 utils.metrics 范式）。"""
    try:
        samples = counter.collect()
        if samples and samples[0].samples:
            return float(samples[0].samples[0].value)
    except Exception:
        pass
    return 0.0
