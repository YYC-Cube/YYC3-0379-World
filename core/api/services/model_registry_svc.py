# file: model_registry_svc.py
# description: 模型注册中心服务 - 五表 CRUD / 心跳 TTL / 事件发布 / env 双通道合并（Phase A MVP）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-27
# status: active
# tags: [registry],[model],[heartbeat],[events],[dual-channel]
# spec: docs/模型接入与注册/02-Registry目标架构.md

"""
@file: app/services/model_registry_svc.py
@description: Model Registry 服务层（规范 02 目标架构的 Phase A MVP 落地）。
    - 五表：model_registry（主表增量列）/ model_versions / model_heartbeats /
            model_events / model_audit_log（005 迁移；sqlite 由 ensure_tables 自建）
    - 心跳 TTL 三级阶梯（规范 02 §4.4）：>90s degraded / >180s unreachable / >300s 视为摘除
    - 事件：写 PG model_events + Redis pub/sub（yyc3:registry:events）双投递，
            网关侧 Push（SSE 订阅）/ Pull（list_models）双通道（规范 02 §4.2）
    - 双通道兼容：registry_upstreams() 产出 env 同构上游条目供 upstream_registry 合并，
            REGISTRY_ENABLED=false 时完全旁路（env 通道行为不变）
    - 幂等注册：重复注册同 model_id = 覆盖更新（不产生副本），版本历史追加
    Phase A 边界（生产实况 2026-09-28）：
    - merge 为 startup 一次性（main.py startup 钩子）——运行中注册需网关重启方入池，
      运行时增量合并（SSE 事件驱动）属 Phase B（规范 02 §4.2）
    - 心跳衰减语义：last_heartbeat_at 为 NULL 的注册（未启用心跳的手动模式）持续纳入
      registry_upstreams 不衰减；一旦开始上报心跳，停跳超 300s（TTL_REMOVED）即从
      产出中摘除——register_agent.py 落地（规范 01 附录 A）前的生产注册均用手动模式
    高可用语义：DB 不可达一律返回空/False 并告警，绝不阻塞网关（env 通道兜底）。
@author: YanYuCloudCube Team <admin@0379.email>
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
"""

import asyncio
import calendar
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from app.cache import redis_client

logger = logging.getLogger(__name__)

REGISTRY_EVENTS_CHANNEL = "yyc3:registry:events"  # Redis pub/sub 事件通道（网关 SSE 转发源）

# 心跳 TTL 三级阶梯（秒，规范 02 §4.4 统一口径）
TTL_DEGRADED = 90
TTL_UNREACHABLE = 180
TTL_REMOVED = 300

# 主表查询列（id 即 model_id——沿用存量 ORM 表主键语义）
_COLS = (
    "id, display_name, backend_type, backend_name, enabled, created_at, "
    "version, capabilities, tags, description, max_tokens, context_window, "
    "temperature_default, top_p_default, cost_per_1k_tokens, avg_latency_ms, "
    "throughput_tps, max_concurrency, node_id, node_role, base_url, fallback_url, "
    "weights_path, weights_size_gb, quantization, model_type, state, health_status, "
    "last_heartbeat_at, breaker_state, manifest_hash, owner, updated_at"
)

# 注册可写字段（白名单；model_id/id 由路径或必填项单独处理）
_WRITABLE = {
    "display_name",
    "backend_type",
    "backend_name",
    "enabled",
    "version",
    "capabilities",
    "tags",
    "description",
    "max_tokens",
    "context_window",
    "temperature_default",
    "top_p_default",
    "cost_per_1k_tokens",
    "avg_latency_ms",
    "throughput_tps",
    "max_concurrency",
    "node_id",
    "node_role",
    "base_url",
    "fallback_url",
    "weights_path",
    "weights_size_gb",
    "quantization",
    "model_type",
    "state",
    "manifest_hash",
    "owner",
}


def registry_enabled() -> bool:
    """Registry 双通道开关（REGISTRY_ENABLED，默认 false=纯 env 现状行为）。"""
    return os.getenv("REGISTRY_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def _j(value: Any) -> str:
    """结构化值 → JSON 串（capabilities/tags/manifest 统一 TEXT 存储，跨方言）。"""
    return value if isinstance(value, str) else json.dumps(value or [], ensure_ascii=False)


def _parse_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """行 → 对外 dict：JSON 串反序列化 + 心跳 TTL 实时判定（读时计算，无后台任务）。"""
    rec = dict(row)
    for field in ("capabilities", "tags"):
        raw = rec.get(field)
        if isinstance(raw, str):
            try:
                rec[field] = json.loads(raw)
            except Exception:
                rec[field] = []
    # TTL 三级阶梯：基于 last_heartbeat_at 与当前时刻差值判定健康
    last_beat = rec.get("last_heartbeat_at")
    if rec.get("state") in ("ready", "loading") and last_beat is not None:
        age = time.time() - _to_epoch(last_beat)
        if age > TTL_UNREACHABLE:
            rec["health_status"] = "unreachable"
        elif age > TTL_DEGRADED:
            rec["health_status"] = "degraded"
        elif rec.get("health_status") in (None, "unknown"):
            rec["health_status"] = "healthy"
    return rec


def _to_epoch(value: Any) -> float:
    """TIMESTAMPTZ/datetime/str → epoch 秒（方言与驱动差异归一）。

    sqlite CURRENT_TIMESTAMP 返回 UTC 无时区字符串（空格分隔）——timegm 按 UTC
    解释（mktime 会按本地时区，产生 UTC+8 偏移即 28800s 假超时）；
    PG TIMESTAMPTZ 经 asyncpg 返回 aware datetime，.timestamp() 自带正确语义。
    """
    if value is None:
        return 0.0
    if hasattr(value, "timestamp"):  # datetime（aware/naive——naive 按 UTC 补零差）
        return value.timestamp() if value.tzinfo else calendar.timegm(value.timetuple())
    if isinstance(value, (int, float)):
        return float(value)
    try:
        normalized = str(value).replace(" ", "T")[:19]
        return float(calendar.timegm(time.strptime(normalized, "%Y-%m-%dT%H:%M:%S")))
    except Exception:
        return 0.0


async def ensure_tables() -> None:
    """sqlite 本地模式自建五表（PG 由 005 迁移管；幂等）。"""
    from app.db import DATABASE_URL, engine

    if not DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS model_registry ("
                "id VARCHAR(100) PRIMARY KEY, display_name VARCHAR(200) NOT NULL, "
                "backend_type VARCHAR(20) NOT NULL, backend_name VARCHAR(100) NOT NULL, "
                "enabled BOOLEAN DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "version VARCHAR(50) DEFAULT 'v1.0.0', capabilities TEXT DEFAULT '[]', "
                "tags TEXT DEFAULT '[]', description TEXT, max_tokens INT DEFAULT 4096, "
                "context_window INT DEFAULT 8192, temperature_default FLOAT DEFAULT 0.7, "
                "top_p_default FLOAT DEFAULT 0.9, cost_per_1k_tokens FLOAT DEFAULT 0, "
                "avg_latency_ms FLOAT DEFAULT 0, throughput_tps FLOAT DEFAULT 0, "
                "max_concurrency INT DEFAULT 1, node_id VARCHAR(50), "
                "node_role VARCHAR(20) DEFAULT 'primary', base_url VARCHAR(500), "
                "fallback_url VARCHAR(500), weights_path VARCHAR(500), "
                "weights_size_gb FLOAT, quantization VARCHAR(20), "
                "model_type VARCHAR(20) DEFAULT 'chat', state VARCHAR(20) DEFAULT 'offline', "
                "health_status VARCHAR(20) DEFAULT 'unknown', last_heartbeat_at TIMESTAMP, "
                "breaker_state VARCHAR(20) DEFAULT 'closed', manifest_hash VARCHAR(64), "
                "owner VARCHAR(200), updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        for ddl in (
            "CREATE TABLE IF NOT EXISTS model_versions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, model_id VARCHAR(100) NOT NULL, "
            "version VARCHAR(50) NOT NULL, manifest TEXT DEFAULT '{}', "
            "manifest_hash VARCHAR(64) DEFAULT '', action VARCHAR(20) NOT NULL, "
            "actor VARCHAR(200) NOT NULL, reason TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS model_heartbeats ("
            "model_id VARCHAR(100) PRIMARY KEY, "
            "last_beat_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "consecutive_miss INT DEFAULT 0, metadata TEXT DEFAULT '{}')",
            "CREATE TABLE IF NOT EXISTS model_events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, event_type VARCHAR(30) NOT NULL, "
            "model_id VARCHAR(100) NOT NULL, version VARCHAR(50), "
            "payload TEXT DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE IF NOT EXISTS model_audit_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, actor VARCHAR(200) NOT NULL, "
            "action VARCHAR(50) NOT NULL, model_id VARCHAR(100), before_state TEXT, "
            "after_state TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        ):
            await conn.execute(text(ddl))


# ── 事件与审计（内部） ────────────────────────────────────────────


async def _emit_event(
    event_type: str, model_id: str, version: Optional[str], payload: dict
) -> None:
    """事件双投递：PG model_events（持久，Pull 兜底源）+ Redis pub/sub（实时，SSE 转发源）。"""
    from sqlalchemy import text

    from app.db import async_session

    event = {
        "event_type": event_type,
        "model_id": model_id,
        "version": version,
        "payload": payload,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        async with async_session() as session:
            await session.execute(
                text(
                    "INSERT INTO model_events (event_type, model_id, version, payload) "
                    "VALUES (:t, :m, :v, :p)"
                ),
                {"t": event_type, "m": model_id, "v": version, "p": _j(payload)},
            )
            await session.commit()
    except Exception as exc:
        logger.warning("[registry] 事件落库失败（继续推送）: %s", exc)
    try:
        await redis_client.publish(REGISTRY_EVENTS_CHANNEL, json.dumps(event, ensure_ascii=False))
    except Exception as exc:
        logger.debug("[registry] 事件 Redis 推送失败: %s", exc)


async def _audit(
    actor: str, action: str, model_id: str, before: Optional[dict], after: Optional[dict]
) -> None:
    """审计日志（model_audit_log；失败仅告警不阻断）。"""
    from sqlalchemy import text

    from app.db import async_session

    try:
        async with async_session() as session:
            await session.execute(
                text(
                    "INSERT INTO model_audit_log (actor, action, model_id, before_state, "
                    "after_state) VALUES (:a, :ac, :m, :b, :af)"
                ),
                {
                    "a": actor,
                    "ac": action,
                    "m": model_id,
                    "b": _j(before or {}),
                    "af": _j(after or {}),
                },
            )
            await session.commit()
    except Exception as exc:
        logger.warning("[registry] 审计写入失败（不阻断）: %s", exc)


async def _append_version(
    model_id: str,
    version: str,
    action: str,
    actor: str,
    manifest: dict,
    manifest_hash: str,
    reason: str = "",
) -> None:
    """版本历史追加（append-only 事件日志语义：同版本可有 register→rollback 多条）。"""
    from sqlalchemy import text

    from app.db import async_session

    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO model_versions (model_id, version, manifest, manifest_hash, "
                "action, actor, reason) VALUES (:m, :v, :mf, :mh, :a, :ac, :r)"
            ),
            {
                "m": model_id,
                "v": version,
                "mf": _j(manifest),
                "mh": manifest_hash,
                "a": action,
                "ac": actor,
                "r": reason,
            },
        )
        await session.commit()


def _manifest_hash(model_id: str, version: str, manifest: dict) -> str:
    """Manifest 哈希（sha256；规范 02 §2.2 不可变版本语义的最小实现）。"""
    return hashlib.sha256(
        f"{model_id}@{version}:{json.dumps(manifest, sort_keys=True, ensure_ascii=False)}".encode()
    ).hexdigest()


# ── CRUD（对外） ──────────────────────────────────────────────────


async def register_model(payload: dict, actor: str = "registry-api") -> dict:
    """注册/更新模型（幂等覆盖）；写主表 + 版本历史 + 事件 + 审计。

    :raises ValueError: 必填字段缺失
    """
    from sqlalchemy import text

    from app.db import async_session

    model_id = str(payload.get("model_id") or payload.get("id") or "").strip()
    if not model_id:
        raise ValueError("model_id 必填")
    display_name = payload.get("display_name") or model_id
    backend_type = payload.get("backend_type") or payload.get("backend") or "vllm"
    backend_name = payload.get("backend_name") or backend_type
    version = payload.get("version") or "v1.0.0"

    fields = {
        "display_name": display_name,
        "backend_type": str(backend_type),
        "backend_name": str(backend_name),
        "enabled": bool(payload.get("enabled", True)),  # PG boolean 列须绑 bool（整数会炸）
        "version": str(version),
    }
    for key in _WRITABLE - set(fields):
        if key in payload and payload[key] is not None:
            value = payload[key]
            fields[key] = _j(value) if key in ("capabilities", "tags") else value
    # 注册语义：默认 offline（实例就绪后由心跳/管理面置 ready）
    fields.setdefault("state", "offline")

    cols = ", ".join(fields)
    params: Dict[str, Any] = dict(fields)
    params["id"] = model_id
    async with async_session() as session:
        existing = (
            await session.execute(
                text("SELECT id FROM model_registry WHERE id = :id"), {"id": model_id}
            )
        ).first()
        if existing:
            sets = ", ".join(f"{c} = :{c}" for c in fields if c != "id")
            await session.execute(
                text(
                    f"UPDATE model_registry SET {sets}, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = :id"
                ),
                params,
            )
        else:
            await session.execute(
                text(
                    f"INSERT INTO model_registry (id, {cols}) VALUES (:id, "
                    f"{', '.join(':' + c for c in fields)})"
                ),
                params,
            )
        await session.commit()

    manifest = payload.get("manifest") or {"registered_fields": sorted(fields)}
    m_hash = payload.get("manifest_hash") or _manifest_hash(model_id, str(version), manifest)
    await _append_version(model_id, str(version), "register", actor, manifest, m_hash)
    await _emit_event(
        "registered" if not existing else "updated", model_id, str(version), {"actor": actor}
    )
    await _audit(
        actor,
        "model.registered" if not existing else "model.updated",
        model_id,
        None,
        {"version": version},
    )
    result = await get_model(model_id) or {"id": model_id}
    result["manifest_hash"] = m_hash
    return result


async def get_model(model_id: str) -> Optional[dict]:
    """单模型详情（含 TTL 实时健康判定）；不存在返回 None。"""
    from sqlalchemy import text

    from app.db import async_session

    try:
        async with async_session() as session:
            row = (
                (
                    await session.execute(
                        text(f"SELECT {_COLS} FROM model_registry WHERE id = :id"), {"id": model_id}
                    )
                )
                .mappings()
                .first()
            )
    except Exception as exc:
        logger.warning("[registry] 主表查询不可达: %s", exc)
        return None
    return _parse_row(dict(row)) if row else None


async def list_models(enabled_only: bool = False, model_type: Optional[str] = None) -> List[dict]:
    """模型列表（Pull 通道数据源）。"""
    from sqlalchemy import text

    from app.db import async_session

    sql = f"SELECT {_COLS} FROM model_registry"
    conds, params = [], {}
    if enabled_only:
        # PG boolean 列不接受整数比较（sqlite 习惯的 enabled=1 会 UndefinedFunctionError）
        # 参数化 bool 绑定两端通吃：asyncpg→boolean / aiosqlite→integer(0/1)
        conds.append("enabled = :en")
        params["en"] = True
    if model_type:
        conds.append("model_type = :mt")
        params["mt"] = model_type
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY id"
    try:
        async with async_session() as session:
            rows = (await session.execute(text(sql), params)).mappings().all()
    except Exception as exc:
        logger.warning("[registry] 列表查询不可达（返回空，env 通道兜底）: %s", exc)
        return []
    return [_parse_row(dict(r)) for r in rows]


async def update_model(model_id: str, patch: dict, actor: str = "registry-api") -> Optional[dict]:
    """局部更新（白名单字段）；写事件 + 审计。不存在返回 None。"""
    from sqlalchemy import text

    from app.db import async_session

    before = await get_model(model_id)
    if before is None:
        return None
    fields = {
        k: (_j(v) if k in ("capabilities", "tags") else v)
        for k, v in patch.items()
        if k in _WRITABLE and v is not None
    }
    if not fields:
        return before
    async with async_session() as session:
        sets = ", ".join(f"{c} = :{c}" for c in fields)
        await session.execute(
            text(
                f"UPDATE model_registry SET {sets}, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = :id"
            ),
            {**fields, "id": model_id},
        )
        await session.commit()
    await _emit_event("updated", model_id, before.get("version"), {"fields": sorted(fields)})
    await _audit(actor, "model.updated", model_id, before, patch)
    return await get_model(model_id)


async def deregister_model(model_id: str, actor: str = "registry-api") -> bool:
    """注销模型（删主表行 + 置 archived 语义：版本历史保留可回溯）。"""
    from sqlalchemy import text

    from app.db import async_session

    before = await get_model(model_id)
    if before is None:
        return False
    async with async_session() as session:
        await session.execute(text("DELETE FROM model_registry WHERE id = :id"), {"id": model_id})
        await session.execute(
            text("DELETE FROM model_heartbeats WHERE model_id = :id"), {"id": model_id}
        )
        await session.commit()
    await _emit_event("deregistered", model_id, before.get("version"), {"actor": actor})
    await _audit(actor, "model.deregistered", model_id, before, None)
    return True


async def rollback_model(
    model_id: str, target_version: str, actor: str = "registry-api", reason: str = ""
) -> Optional[dict]:
    """回滚：主表 version 切回目标版本 + 版本历史追加 rollback 记录 + 事件。

    :raises ValueError: 目标版本在历史中不存在（防盲滚）
    """
    history = await list_versions(model_id)
    target = next((v for v in history if v.get("version") == target_version), None)
    if target is None:
        raise ValueError(f"目标版本 {target_version} 不在 {model_id} 版本历史中")
    manifest = target.get("manifest") or {}
    updated = await update_model(
        model_id,
        {
            "version": target_version,
            "manifest_hash": target.get("manifest_hash")
            or _manifest_hash(model_id, target_version, manifest),
        },
        actor=actor,
    )
    await _append_version(
        model_id,
        target_version,
        "rollback",
        actor,
        manifest,
        target.get("manifest_hash") or "",
        reason or "rollback",
    )
    await _emit_event("updated", model_id, target_version, {"rollback_from": None, "actor": actor})
    await _audit(
        actor,
        "model.rolled_back",
        model_id,
        {"version": (updated or {}).get("version")},
        {"version": target_version},
    )
    return updated


async def list_versions(model_id: str) -> List[dict]:
    """版本历史（新→旧）；manifest 反序列化。"""
    from sqlalchemy import text

    from app.db import async_session

    try:
        async with async_session() as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT id, version, manifest, manifest_hash, action, actor, reason, "
                            "created_at FROM model_versions WHERE model_id = :m "
                            "ORDER BY id DESC"
                        ),
                        {"m": model_id},
                    )
                )
                .mappings()
                .all()
            )
    except Exception as exc:
        logger.warning("[registry] 版本历史查询不可达: %s", exc)
        return []
    result = []
    for r in rows:
        rec = dict(r)
        raw = rec.get("manifest")
        try:
            rec["manifest"] = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            rec["manifest"] = {}
        result.append(rec)
    return result


# ── 心跳（模型服务 → Registry） ──────────────────────────────────


async def heartbeat(model_id: str, status: str = "healthy", **runtime: Any) -> bool:
    """心跳上报：upsert 心跳表 + 主表 last_heartbeat_at/health_status 刷新。

    runtime 附带运行时指标（gpu_utilization/active_requests 等）存心跳表 metadata。
    """
    from sqlalchemy import text

    from app.db import async_session

    existing = await get_model(model_id)
    if existing is None:
        return False
    now_expr = "CURRENT_TIMESTAMP"
    async with async_session() as session:
        await session.execute(
            text(
                "INSERT INTO model_heartbeats (model_id, last_beat_at, consecutive_miss, metadata) "
                f"VALUES (:m, {now_expr}, 0, :meta) "
                "ON CONFLICT(model_id) DO UPDATE SET last_beat_at = CURRENT_TIMESTAMP, "
                "consecutive_miss = 0, metadata = :meta"
            ),
            {"m": model_id, "meta": _j({"status": status, **{k: v for k, v in runtime.items()}})},
        )
        await session.execute(
            text(
                "UPDATE model_registry SET last_heartbeat_at = CURRENT_TIMESTAMP, "
                "health_status = :hs WHERE id = :id"
            ),
            {"hs": "degraded" if status == "degraded" else "healthy", "id": model_id},
        )
        await session.commit()
    return True


async def get_health(model_id: str) -> Optional[dict]:
    """实时健康（TTL 判定 + 最近心跳 metadata）。"""
    from sqlalchemy import text

    from app.db import async_session

    model = await get_model(model_id)
    if model is None:
        return None
    hb_meta: dict = {}
    try:
        async with async_session() as session:
            row = (
                (
                    await session.execute(
                        text(
                            "SELECT last_beat_at, consecutive_miss, metadata FROM model_heartbeats "
                            "WHERE model_id = :m"
                        ),
                        {"m": model_id},
                    )
                )
                .mappings()
                .first()
            )
        if row:
            raw = row.get("metadata")
            try:
                hb_meta = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except Exception:
                hb_meta = {}
    except Exception as exc:
        logger.debug("[registry] 心跳表查询失败: %s", exc)
    return {
        "model_id": model_id,
        "state": model.get("state"),
        "health_status": model.get("health_status"),
        "last_heartbeat_at": str(model.get("last_heartbeat_at") or ""),
        "heartbeat_age_seconds": (
            round(time.time() - _to_epoch(model.get("last_heartbeat_at")), 1)
            if model.get("last_heartbeat_at")
            else None
        ),
        "runtime": hb_meta,
    }


# ── 事件流（SSE 数据源） ─────────────────────────────────────────


async def recent_events(since_id: int = 0, limit: int = 100) -> List[dict]:
    """事件回放（SSE 连接建立时追平在途事件，防漏；payload 反序列化）。"""
    from sqlalchemy import text

    from app.db import async_session

    try:
        async with async_session() as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT id, event_type, model_id, version, payload, created_at "
                            "FROM model_events WHERE id > :sid ORDER BY id LIMIT :lim"
                        ),
                        {"sid": since_id, "lim": limit},
                    )
                )
                .mappings()
                .all()
            )
    except Exception as exc:
        logger.warning("[registry] 事件回放查询失败: %s", exc)
        return []
    result = []
    for r in rows:
        rec = dict(r)
        raw = rec.pop("payload")
        try:
            rec["payload"] = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            rec["payload"] = {}
        result.append(rec)
    return result


# ── 双通道合并（网关侧 Pull 集成点） ──────────────────────────────


async def registry_upstreams() -> List[dict]:
    """Registry → env 同构上游条目（enabled 且 ready、非 unreachable、TTL 未摘除）。

    供 upstream_registry 合并（规范 02 §4.1 Phase A：Registry 优先，env 兜底）；
    输出字段与 OPENAI_COMPATIBLE_UPSTREAMS 条目同构（name/base_url/models/priority/…）。
    """
    models = await list_models(enabled_only=True)
    upstreams: List[dict] = []
    for m in models:
        if m.get("state") != "ready":
            continue
        if m.get("health_status") == "unreachable":
            continue
        last_beat = m.get("last_heartbeat_at")
        if last_beat is not None:
            age = time.time() - _to_epoch(last_beat)
            if age > TTL_REMOVED:
                continue  # 300s 无心跳：视为已摘除
        base_url = m.get("base_url")
        if not base_url:
            continue
        entry: Dict[str, Any] = {
            "name": f"registry-{m['id']}",
            "base_url": base_url,
            "models": [m["id"]],
            "priority": 5 if m.get("node_role") == "primary" else 8,
        }
        if m.get("fallback_url"):
            entry["fallback_url"] = m["fallback_url"]
        if m.get("model_type") and m["model_type"] != "chat":
            entry["capability"] = m["model_type"]
        if m.get("max_concurrency"):
            entry["capacity"] = int(m["max_concurrency"])
        upstreams.append(entry)
    return upstreams


# ── Phase B 增量合并（事件驱动，消除重启依赖） ────────────────────

_merge_task: Optional[asyncio.Task] = None


async def _handle_registry_event(event: dict) -> None:
    """单事件处理：registered/updated → 全量重合并（幂等）；deregistered → 定点摘除。

    全量重合并而非单条增量：merge 幂等且 DB 列表查询毫秒级——一致性优先于
    微优化（避免事件 payload 与 DB 态的窗口分歧）。
    """
    from app.services import upstream_registry

    event_type = str(event.get("event_type") or "")
    model_id = str(event.get("model_id") or "")
    if event_type == "deregistered" and model_id:
        removed = upstream_registry.registry.upstreams.pop(f"registry-{model_id}", None)
        if removed:
            logger.info("[registry] Phase B 事件摘除上游 registry-%s（无需重启）", model_id)
    elif event_type in ("registered", "updated"):
        merged = await upstream_registry.merge_registry_upstreams()
        logger.info(
            "[registry] Phase B 事件重合并（%s → %s）：%d 上游入池", event_type, model_id, merged
        )


async def _merge_consumer_loop() -> None:
    """pub/sub 订阅循环：yyc3:registry:events → _handle_registry_event。"""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(REGISTRY_EVENTS_CHANNEL)
    logger.info("[registry] Phase B 增量合并消费者已启动（频道 %s）", REGISTRY_EVENTS_CHANNEL)
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if not msg or msg.get("type") != "message":
                continue
            data = msg.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8", "replace")
            if not isinstance(data, str):
                continue
            try:
                await _handle_registry_event(json.loads(data))
            except (json.JSONDecodeError, TypeError):
                logger.debug("[registry] 事件解析失败（跳过）: %s", str(data)[:120])
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # Redis 抖动：告警退避（Pull 兜底仍在）
        logger.warning("[registry] Phase B 消费者异常退出（下次重启自愈）: %s", exc)
    finally:
        try:
            await pubsub.unsubscribe(REGISTRY_EVENTS_CHANNEL)
            await pubsub.close()
        except Exception:
            pass


async def start_merge_consumer() -> None:
    """startup 挂载（REGISTRY_ENABLED=true 时；幂等）。"""
    global _merge_task
    if _merge_task is None or _merge_task.done():
        _merge_task = asyncio.create_task(_merge_consumer_loop())


async def stop_merge_consumer() -> None:
    global _merge_task
    if _merge_task is not None:
        _merge_task.cancel()
        try:
            await _merge_task
        except asyncio.CancelledError:
            pass
        _merge_task = None


# ── 心跳断流观测（TOP3b）：Prometheus 指标 + 状态翻转告警日志 ──────

_watch_task: Optional[asyncio.Task] = None
_STALE_THRESHOLD = 120  # 断流阈值（秒）：4 个心跳周期，早于 TTL 300s 摘除
_stale_state: Dict[str, bool] = {}  # model_id → 是否已断流（翻转去抖）


def _gauges():
    """懒初始化 Prometheus Gauges（注册默认 registry → instrumentator /metrics 自动暴露；
    prometheus_client 不可用时返回 None 降级纯日志模式）。"""
    try:
        from prometheus_client import Gauge

        global _g_hb_age, _g_ready
        if "_g_hb_age" not in globals():
            _g_hb_age = Gauge(
                "yyc3_registry_model_heartbeat_age_seconds",
                "Registry 模型心跳年龄（无心跳注册为 -1；断流阈值 120s / TTL 摘除 300s）",
                ["model_id", "node_id"],
            )
            _g_ready = Gauge(
                "yyc3_registry_model_ready",
                "Registry 模型 state==ready（1/0）",
                ["model_id", "node_id"],
            )
        return _g_hb_age, _g_ready
    except Exception:
        return None


async def _watch_once(models: Optional[List[dict]] = None) -> None:
    """单轮观测（可测单元）：刷新 Gauges + 断流翻转告警。models 可注入（缺省查库）。"""
    models = models if models is not None else await list_models()
    gauges = _gauges()
    for m in models:
        mid, node = str(m.get("id")), str(m.get("node_id") or "")
        last_beat = m.get("last_heartbeat_at")
        age = time.time() - _to_epoch(last_beat) if last_beat is not None else -1.0
        # -1 = 手动模式（未启用心跳），不参与断流判定
        stale = age >= _STALE_THRESHOLD
        prev = _stale_state.get(mid)
        if stale and prev is False:
            logger.warning(
                "[registry] ⚠️ 心跳断流告警: %s age=%.0fs（阈值 %ds；TTL %ds 后摘除）",
                mid,
                age,
                _STALE_THRESHOLD,
                TTL_REMOVED,
            )
        elif not stale and prev is True:
            logger.info("[registry] ✅ 心跳恢复: %s age=%.0fs", mid, age)
        _stale_state[mid] = stale
        if gauges:
            gauges[0].labels(model_id=mid, node_id=node).set(age)
            gauges[1].labels(model_id=mid, node_id=node).set(1 if m.get("state") == "ready" else 0)


async def _watch_loop() -> None:
    """周期刷新心跳指标 + 断流翻转告警（REGISTRY_ENABLED 时随 merge consumer 同生命周期）。

    告警链：状态翻转（healthy↔stale）时 logger.warning/info → 结构化日志入 Loki
    （既有 shipper 链）→ Grafana 可查/可接既有告警通道；Prometheus 抓取 15s 自动采集
    Gauge（NAS prometheus.yml job=yyc3-gateway 已覆盖 /metrics）。
    """
    logger.info("[registry] 心跳观测循环已启动（周期 30s，断流阈值 %ds）", _STALE_THRESHOLD)
    while True:
        try:
            await _watch_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("[registry] 心跳观测轮次异常（继续）: %s", exc)
        await asyncio.sleep(30)


async def start_heartbeat_watch() -> None:
    global _watch_task
    if _watch_task is None or _watch_task.done():
        _watch_task = asyncio.create_task(_watch_loop())


async def stop_heartbeat_watch() -> None:
    global _watch_task
    if _watch_task is not None:
        _watch_task.cancel()
        try:
            await _watch_task
        except asyncio.CancelledError:
            pass
        _watch_task = None
