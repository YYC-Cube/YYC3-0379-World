# file: test_registry_hot_reload.py
# description: 多 worker 热一致性——真源 env 文件 mtime 变化 → registry 懒重载（单测·tmp_path）
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-11-16
# status: active
# tags: [test],[registry],[hot-reload],[unit]

import json

import pytest

from app.config import settings
from app.services import upstream_registry as ur

pytestmark = pytest.mark.unit


@pytest.fixture()
def hot_env_file(tmp_path, monkeypatch):
    """临时真源 env 文件 + registry 指向它；初始池 = 主力一条"""
    f = tmp_path / "gateway.env"
    pool_a = [{"name": "flagship", "base_url": "http://a.test:8000",
               "models": ["nemotron-3.5-super-vl"], "priority": 1}]
    f.write_text("OPENAI_COMPATIBLE_UPSTREAMS=" + json.dumps(pool_a) + "\n", encoding="utf-8")
    monkeypatch.setattr(ur, "ENV_FILE", f)
    settings.openai_compatible_upstreams = json.dumps(pool_a)
    ur.registry.load_from_env()
    ur._env_sig_cache["sig"] = None  # 强制下次请求式重载建立基线
    yield f
    monkeypatch.undo()


def test_first_call_establishes_baseline(hot_env_file):
    ur.reload_if_env_changed()
    assert "flagship" in ur.registry.upstreams


def test_file_change_triggers_hot_reload(hot_env_file):
    ur.reload_if_env_changed()  # 建基线
    assert "embed-hot" not in ur.registry.upstreams
    pool_b = [
        {"name": "flagship", "base_url": "http://a.test:8000",
         "models": ["nemotron-3.5-super-vl"], "priority": 1},
        {"name": "embed-hot", "base_url": "http://hot.test:8002",
         "models": ["probe-embed"], "capability": "embedding", "priority": 1},
    ]
    hot_env_file.write_text("OPENAI_COMPATIBLE_UPSTREAMS=" + json.dumps(pool_b) + "\n",
                            encoding="utf-8")
    ur.reload_if_env_changed()
    assert "embed-hot" in ur.registry.upstreams
    assert ur.registry.upstreams["embed-hot"].capability == "embedding"


def test_unchanged_file_no_op(hot_env_file):
    ur.reload_if_env_changed()
    before = dict(ur.registry.upstreams)
    for _ in range(3):
        ur.reload_if_env_changed()
    assert set(ur.registry.upstreams) == set(before)
