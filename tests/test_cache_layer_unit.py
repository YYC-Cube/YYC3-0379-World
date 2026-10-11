#!/usr/bin/env python3
"""
@file test_cache_layer_unit.py
@description 缓存层（core/api/cache.py Redis 封装 + utils/cache.py CacheManager）单测
@author: YanYuCloudCube Team
@tags [test,cache,lru,unit]

背景：core/api/cache.py（112 语句，21%）与 utils/cache.py（78 语句，22%）为
LLM 缓存/LRU 淘汰核心，此前仅经桩替间接覆盖。本文件用内存 FakeRedis 走通
真实分支：读写往返、LRU 索引维护、标签失效、淘汰数学、统计口径。
"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

import app.cache as cache_mod  # noqa: E402
from app.utils import cache as util_cache  # noqa: E402

pytestmark = pytest.mark.unit


def _run(coro):
    return asyncio.run(coro)


class FakeRedis:
    """内存版 Redis 桩：str/zset/set 三类数据结构 + 立即执行 pipeline"""

    def __init__(self):
        self.store = {}
        self.zsets = {}
        self.sets = {}

    # string
    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value

    async def setex(self, key, _ttl, value):
        self.store[key] = value

    async def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store or k in self.zsets or k in self.sets:
                n += 1
            self.store.pop(k, None)
            self.zsets.pop(k, None)
            self.sets.pop(k, None)
        return n

    # zset
    async def zadd(self, name, mapping):
        self.zsets.setdefault(name, {}).update(mapping)
        return len(mapping)

    async def zrem(self, name, *members):
        z = self.zsets.get(name, {})
        n = 0
        for m in members:
            if m in z:
                del z[m]
                n += 1
        return n

    async def zcard(self, name):
        return len(self.zsets.get(name, {}))

    async def zrange(self, name, start, end, withscores=False):
        items = sorted(self.zsets.get(name, {}).items(), key=lambda kv: kv[1])
        if end < 0:  # Redis 语义：负 end 相对末尾（-1 = 最后一个）
            end = len(items) + end
        slice_ = items[start : end + 1]
        if withscores:
            return slice_
        return [m for m, _ in slice_]

    # set
    async def sadd(self, name, *members):
        s = self.sets.setdefault(name, set())
        before = len(s)
        s.update(members)
        return len(s) - before

    async def smembers(self, name):
        return set(self.sets.get(name, set()))

    # pipeline（收集操作、execute 时按序立即执行）
    def pipeline(self):
        return _Pipeline(self)


class _Pipeline:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def delete(self, key):
        self._ops.append(("delete", key))
        return self

    def zrem(self, name, key):
        self._ops.append(("zrem", name, key))
        return self

    async def execute(self):
        results = []
        for op, *args in self._ops:
            results.append(await getattr(self._redis, op)(*args))
        self._ops.clear()
        return results


@pytest.fixture()
def fake_redis(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(cache_mod, "redis_client", client)
    return client


# ── core/api/cache.py：读写与索引 ─────────────────────────


def test_set_get_roundtrip(fake_redis):
    _run(cache_mod.set_cached("k1", {"answer": 42}))
    assert _run(cache_mod.get_cached("k1")) == {"answer": 42}
    assert "k1" in fake_redis.zsets[cache_mod.CACHE_INDEX_KEY]  # LRU 索引已登记


def test_get_miss_returns_none(fake_redis):
    assert _run(cache_mod.get_cached("不存在")) is None


def test_get_refreshes_lru_index(fake_redis):
    _run(cache_mod.set_cached("k1", {"v": 1}))
    old_score = fake_redis.zsets[cache_mod.CACHE_INDEX_KEY]["k1"]
    fake_redis.zsets[cache_mod.CACHE_INDEX_KEY]["k1"] = old_score - 1000  # 人为置旧
    _run(cache_mod.get_cached("k1"))
    assert fake_redis.zsets[cache_mod.CACHE_INDEX_KEY]["k1"] > old_score - 1000


def test_set_with_ttl_and_tags(fake_redis):
    _run(cache_mod.set_cached("k2", {"v": 2}, ttl=600, tags=["model:glm-4-flash"]))
    assert json.loads(fake_redis.store["k2"]) == {"v": 2}
    assert "k2" in fake_redis.sets["cache_tag:model:glm-4-flash"]


def test_delete_clears_index(fake_redis):
    _run(cache_mod.set_cached("k3", {"v": 3}))
    _run(cache_mod.delete_cached("k3"))
    assert "k3" not in fake_redis.store
    assert "k3" not in fake_redis.zsets[cache_mod.CACHE_INDEX_KEY]


# ── 主动失效 ──────────────────────────────────────────────


def test_invalidate_by_tag(fake_redis):
    _run(cache_mod.set_cached("a", {"v": 1}, tags=["t1"]))
    _run(cache_mod.set_cached("b", {"v": 2}, tags=["t1"]))
    _run(cache_mod.set_cached("c", {"v": 3}, tags=["t2"]))
    n = _run(cache_mod.invalidate_by_tag("t1"))
    assert n == 2
    assert "a" not in fake_redis.store and "b" not in fake_redis.store
    assert "c" in fake_redis.store  # 其他标签不受影响
    assert _run(cache_mod.invalidate_by_tag("t1")) == 0  # 二次失效 0 条


def test_invalidate_model_cache(fake_redis):
    _run(cache_mod.set_cached("m1", {"v": 1}, tags=["model:deepseek-chat"]))
    n = _run(cache_mod.invalidate_model_cache("deepseek-chat"))
    assert n == 1 and "m1" not in fake_redis.store


def test_clear_all(fake_redis):
    for i in range(4):
        _run(cache_mod.set_cached(f"x{i}", {"v": i}))
    n = _run(cache_mod.clear_all_cache())
    assert n == 4
    assert not fake_redis.store
    assert cache_mod.CACHE_INDEX_KEY not in fake_redis.zsets


# ── LRU 淘汰 ──────────────────────────────────────────────


def test_lru_evicts_oldest(fake_redis, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_MAX_ENTRIES", 3)
    # 预置 6 条带梯度时间戳的索引与数据（不经 set_cached，避免中途触发淘汰）
    for i in range(6):
        fake_redis.store[f"e{i}"] = json.dumps({"v": i})
        fake_redis.zsets.setdefault(cache_mod.CACHE_INDEX_KEY, {})[f"e{i}"] = float(i)
    # 6 > 3 → 淘汰 int((6-3)*1.2)+1 = 4 条最旧（e0~e3）
    _run(cache_mod._evict_if_needed())
    remaining = fake_redis.zsets.get(cache_mod.CACHE_INDEX_KEY, {})
    assert set(remaining) == {"e4", "e5"}
    assert "e0" not in fake_redis.store and "e3" not in fake_redis.store


def test_lru_noop_under_limit(fake_redis, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_MAX_ENTRIES", 100)
    _run(cache_mod.set_cached("safe", {"v": 1}))
    _run(cache_mod._evict_if_needed())
    assert "safe" in fake_redis.store


# ── 统计 ──────────────────────────────────────────────────


def test_get_cache_info(fake_redis):
    _run(cache_mod.set_cached("i1", {"v": 1}))
    _run(cache_mod.set_cached("i2", {"v": 2}))
    info = _run(cache_mod.get_cache_info())
    assert info["total_entries"] == 2
    assert info["max_entries"] == cache_mod.CACHE_MAX_ENTRIES
    assert info["usage_percent"] == round(2 / cache_mod.CACHE_MAX_ENTRIES * 100, 2)
    assert info["oldest_entry_ts"] <= info["newest_entry_ts"]
    assert info["default_ttl"] == cache_mod.CACHE_TTL


# ── utils/cache.py CacheManager ───────────────────────────


@pytest.fixture()
def manager(fake_redis, monkeypatch):
    """CacheManager 直走真实 app.cache 函数（已桩 FakeRedis）"""
    m = util_cache.CacheManager(default_ttl=120)
    return m


def test_manager_get_set_delete(manager):
    assert _run(manager.get("mk")) is None
    assert _run(manager.set("mk", {"v": 1})) is True
    assert _run(manager.get("mk")) == {"v": 1}
    assert manager.stats["hits"] == 1 and manager.stats["misses"] == 1
    assert _run(manager.delete("mk")) is True
    assert _run(manager.get("mk")) is None


def test_manager_invalidate_by_tags(manager):
    _run(manager.set("t-a", {"v": 1}, tags=["tg"]))
    _run(manager.set("t-b", {"v": 2}, tags=["tg"]))
    _run(manager.set("t-c", {"v": 3}, tags=["other"]))
    n = _run(manager.invalidate_by_tags(["tg"]))
    assert n == 2
    assert manager.stats["evictions"] == 2
    assert _run(manager.get("t-c")) == {"v": 3}


def test_manager_stats_and_reset(manager):
    _run(manager.set("s1", {"v": 1}))
    _run(manager.get("s1"))
    _run(manager.get("s2"))  # miss
    stats = manager.get_stats()
    assert stats["hit_rate"] == 0.5
    assert stats["sets"] == 1 and stats["total"] == 2
    manager.reset_stats()
    assert manager.get_stats()["total"] == 0


def test_manager_decorator(fake_redis, monkeypatch):
    calls = {"n": 0}

    # conftest 的 autouse 夹具把全局 cache_manager.get/set 旁路为 no-op，
    # 装饰器走的是全局实例——此处换挂走 FakeRedis 的真实实例
    real = util_cache.CacheManager(default_ttl=60)
    monkeypatch.setattr(util_cache, "cache_manager", real)

    @util_cache.cached("prefix", ttl=60)
    async def expensive(x):
        calls["n"] += 1
        return {"result": x * 2}

    assert _run(expensive(3)) == {"result": 6}
    assert _run(expensive(3)) == {"result": 6}
    assert calls["n"] == 1  # 第二次命中缓存
