#!/usr/bin/env python3
"""
@file test_video_tasks.py
@description 第五能力视频任务 API 测试——创建/列表/详情/领取/心跳/回报/失败/租约回收
@author: YanYuCloudCube Team
@version: v1.0.0
@date: 2026-09-24
@tags [test,video,tasks]

Redis 以内存桩替（monkeypatch 模块薄存储层），零外部依赖。
测试密钥值全部运行时随机生成（凭据零硬编码）。
"""

import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

_POOL = json.dumps(
    [
        {
            "name": "flagship",
            "base_url": "http://flagship.test:8001",
            "models": ["deepseek-v4-flash"],
            "priority": 1,
        }
    ]
)
# 测试专用 API Key（随机生成，非真实凭据）
_TEST_API_KEY = "pytest-" + uuid.uuid4().hex[:16]
_TEST_RUNNER_KEY = "runner-" + uuid.uuid4().hex[:16]
os.environ.update(
    {
        "API_KEYS": _TEST_API_KEY,
        "JWT_SECRET_KEY": "jwt-" + uuid.uuid4().hex,
        "POSTGRES_PASSWORD": "pg-" + uuid.uuid4().hex,
        "REDIS_PASSWORD": "redis-" + uuid.uuid4().hex,
        "OPENAI_COMPATIBLE_UPSTREAMS": _POOL,
    }
)

import pytest  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

pytestmark = pytest.mark.integration


def _auth():
    return {"X-API-Key": _TEST_API_KEY}


def _runner_auth():
    return {"X-API-Key": _TEST_RUNNER_KEY}


@pytest.fixture(autouse=True)
def _mem_storage(monkeypatch):
    """内存桩替换模块 Redis 薄存储层"""
    from app.api import video_tasks as vt

    tasks: dict = {}
    results: dict = {}
    queue: list = []
    index: set = set()

    async def store_task(task, ttl=None):
        tasks[task["id"]] = json.loads(json.dumps(task))

    async def load_task(task_id):
        return tasks.get(task_id)

    async def queue_push(task_id):
        queue.append(task_id)

    async def queue_pop():
        return queue.pop(0) if queue else None

    async def queue_len():
        return len(queue)

    async def index_add(task_id):
        index.add(task_id)

    async def index_all():
        return list(index)

    async def store_result(task_id, data, ttl=None):
        results[task_id] = data

    async def load_result(task_id):
        return results.get(task_id)

    monkeypatch.setattr(vt, "_store_task", store_task)
    monkeypatch.setattr(vt, "_load_task", load_task)
    monkeypatch.setattr(vt, "_queue_push", queue_push)
    monkeypatch.setattr(vt, "_queue_pop", queue_pop)
    monkeypatch.setattr(vt, "_queue_len", queue_len)
    monkeypatch.setattr(vt, "_index_add", index_add)
    monkeypatch.setattr(vt, "_index_all", index_all)
    monkeypatch.setattr(vt, "_store_result", store_result)
    monkeypatch.setattr(vt, "_load_result", load_result)
    yield


@pytest.fixture(autouse=True)
def _runner_admin_key(monkeypatch):
    """为 runner 端点注入随机管理密钥（测后还原）"""
    from app.config import settings as _s

    monkeypatch.setattr(_s, "admin_api_keys", _TEST_RUNNER_KEY)
    # auth 中间件的 AuthConfig 若缓存了 ADMIN_API_KEYS，一并刷新
    try:
        from app.middleware.auth import auth_config

        if hasattr(auth_config, "ADMIN_API_KEYS"):
            monkeypatch.setattr(
                type(auth_config), "ADMIN_API_KEYS", property(lambda self: {_TEST_RUNNER_KEY})
            )
    except Exception:
        pass
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_task_full_lifecycle(client):
    """创建 → 无管理密钥拒领 → 领取 → 心跳 → 回报成功 → 详情/下载"""
    r = client.post(
        "/v1/video/tasks",
        headers=_auth(),
        json={"quality": "preview", "prompt": "测试数字人"},
    )
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    assert r.json()["status"] == "queued"
    assert r.json()["queue_position"] == 0

    # 普通密钥访问 claim → 401/403（ADMIN 保护）
    r = client.post("/v1/admin/video/tasks/claim", headers=_auth(), json={"runner": "t"})
    assert r.status_code in (401, 403)

    # runner 领取
    r = client.post(
        "/v1/admin/video/tasks/claim",
        headers=_runner_auth(),
        json={"runner": "yyc3-22-mac", "lease_minutes": 10},
    )
    assert r.status_code == 200, r.text
    claimed = r.json()["claimed"]
    assert claimed and claimed["id"] == task_id and claimed["status"] == "running"

    # 心跳续租
    r = client.post(
        f"/v1/admin/video/tasks/{task_id}/heartbeat",
        headers=_runner_auth(),
        json={"runner": "yyc3-22-mac", "lease_minutes": 30},
    )
    assert r.status_code == 200

    # 回报成功（带视频文件）
    r = client.post(
        f"/v1/admin/video/tasks/{task_id}/result",
        headers=_runner_auth(),
        files={"file": ("v.mp4", b"\x00\x00fake-mp4", "video/mp4")},
        data={"archive_path": "/Volume1/yyc3_hd/video_tasks/x.mp4", "duration_seconds": "123.4"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "succeeded"

    # 公网详情：含 result_url / archive_path / 耗时
    r = client.get(f"/v1/video/tasks/{task_id}", headers=_auth())
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "succeeded"
    assert d["result_url"] == f"/v1/video/tasks/{task_id}/result"
    assert d["archive_path"].endswith("x.mp4")
    assert d["duration_seconds"] == 123.4

    # 结果下载（含 runner 上游头）
    r = client.get(f"/v1/video/tasks/{task_id}/result", headers=_auth())
    assert r.status_code == 200
    assert r.content == b"\x00\x00fake-mp4"
    assert r.headers.get("x-yyc3-upstream") == "video-runner-mac"


def test_task_failure_and_list(client):
    r = client.post("/v1/video/tasks", headers=_auth(), json={"quality": "full"})
    tid_fail = r.json()["id"]
    client.post("/v1/video/tasks", headers=_auth(), json={"quality": "preview"})

    # FIFO：先领取到的应是最早创建的 tid_fail
    r = client.post(
        "/v1/admin/video/tasks/claim",
        headers=_runner_auth(),
        json={"runner": "r1"},
    )
    assert r.json()["claimed"]["id"] == tid_fail

    # 回报失败
    r = client.post(
        f"/v1/admin/video/tasks/{tid_fail}/failure",
        headers=_runner_auth(),
        json={"error": "生成进程崩溃"},
    )
    assert r.status_code == 200

    # 列表可见混合状态
    r = client.get("/v1/video/tasks", headers=_auth())
    statuses = {t["status"] for t in r.json()["tasks"]}
    assert "failed" in statuses


def test_lease_sweep_requeues_then_fails(client, monkeypatch):
    """租约过期 → 重排队（attempts<2）→ 再过期 → failed"""
    r = client.post("/v1/video/tasks", headers=_auth(), json={"quality": "preview"})
    tid = r.json()["id"]

    from app.api import video_tasks as vt

    client.post(
        "/v1/admin/video/tasks/claim",
        headers=_runner_auth(),
        json={"runner": "dead-runner", "lease_minutes": 5},
    )

    orig_load = vt._load_task

    def _make_load_expired():
        async def patched_load(task_id):
            t = await orig_load(task_id)
            if t and t["id"] == tid and t["status"] == "running":
                t["lease_until"] = time.time() - 1
            return t

        return patched_load

    import asyncio

    loop = asyncio.new_event_loop()
    try:
        monkeypatch.setattr(vt, "_load_task", _make_load_expired())
        swept = loop.run_until_complete(vt._sweep_expired())
        assert swept >= 1  # 第一次过期 → 重排队

        # 恢复原始 load，HTTP 再领取 → 再过期 → failed
        monkeypatch.setattr(vt, "_load_task", orig_load)
        r = client.post(
            "/v1/admin/video/tasks/claim",
            headers=_runner_auth(),
            json={"runner": "r2", "lease_minutes": 5},
        )
        assert r.json()["claimed"] and r.json()["claimed"]["id"] == tid

        monkeypatch.setattr(vt, "_load_task", _make_load_expired())
        loop.run_until_complete(vt._sweep_expired())
    finally:
        loop.close()
        monkeypatch.setattr(vt, "_load_task", orig_load)

    r = client.get(f"/v1/video/tasks/{tid}", headers=_auth())
    assert r.json()["status"] == "failed"


def test_validation_errors(client):
    # 非法 quality
    r = client.post("/v1/video/tasks", headers=_auth(), json={"quality": "4k"})
    assert r.status_code == 422
    # 非法 base64
    r = client.post(
        "/v1/video/tasks", headers=_auth(), json={"ref_image_b64": "!!!not-base64!!!"}
    )
    assert r.status_code == 422
    # 不存在的任务
    r = client.get("/v1/video/tasks/nonexistent00", headers=_auth())
    assert r.status_code == 404
