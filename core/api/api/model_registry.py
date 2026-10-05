# file: model_registry.py
# description: 模型注册中心 API - /registry/v1 16 端点（CRUD/版本/回滚/心跳/健康/事件SSE/审计 + 别名热切换/排空）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.1.0
# created: 2026-09-27
# status: active
# tags: [api],[registry],[model],[sse],[heartbeat]
# spec: docs/模型接入与注册/02-Registry目标架构.md §3.2

"""
@file: app/api/model_registry.py
@description: Model Registry 端点（规范 02 §3.2 十二端点落地，Phase A MVP）。
    认证分层：
    - /registry/v1/** 全程经 AuthMiddleware（普通认证：API Key/JWT/vk 任一）
    - 写操作（POST/PATCH/DELETE/rollback）端点内再校验 admin（request.state.user.admin）
    - 心跳（R-08）普通认证（模型服务身份）
    SSE（R-10）：连接建立先回放 model_events 在途事件（防漏），再订阅 Redis
    pub/sub（yyc3:registry:events）实时转发——Push 通道；Pull 通道为 R-01 轮询。
    Registry 未启用（REGISTRY_ENABLED=false）时写端点 503（只读兼容探查）。
"""

import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services import model_registry_svc as svc
from app.utils import metrics_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ── 请求模型 ─────────────────────────────────────────────────────


class ModelRegisterRequest(BaseModel):
    """注册/更新模型（幂等：同 model_id 覆盖）"""

    model_id: str = Field(..., max_length=100, description="全局唯一模型 ID")
    display_name: str = Field(..., max_length=200)
    backend: str = Field(
        "vllm",
        max_length=20,
        description="vllm/nim/ollama/openai/zhipu/deepseek/upstream",
    )
    version: str = Field("v1.0.0", max_length=50)
    capabilities: list = Field(
        default_factory=list, description="chat/embedding/rerank/asr/ocr/..."
    )
    enabled: bool = True
    description: Optional[str] = None
    max_tokens: int = Field(4096, ge=1)
    context_window: int = Field(8192, ge=256)
    cost_per_1k_tokens: float = Field(0, ge=0)
    avg_latency_ms: float = Field(0, ge=0)
    throughput_tps: float = Field(0, ge=0)
    max_concurrency: int = Field(1, ge=1)
    node_id: Optional[str] = Field(None, max_length=50, description="yyc3-101/yyc3-102")
    node_role: str = Field("primary", description="primary/secondary/fallback")
    base_url: Optional[str] = Field(None, max_length=500)
    fallback_url: Optional[str] = Field(None, max_length=500)
    weights_path: Optional[str] = Field(None, max_length=500)
    weights_size_gb: Optional[float] = None
    quantization: Optional[str] = Field(None, max_length=20)
    model_type: str = Field("chat", description="chat/embedding/rerank/asr/ocr")
    owner: Optional[str] = Field(None, max_length=200)
    tags: list = Field(default_factory=list)
    manifest: Optional[dict] = Field(None, description="版本清单（不可变，见规范 02 §2.2）")


class RollbackRequest(BaseModel):
    """回滚到指定历史版本"""

    target_version: str = Field(..., max_length=50)
    reason: str = Field("", max_length=500)


class HeartbeatRequest(BaseModel):
    """心跳上报（模型服务 30s 周期）"""

    status: str = Field("healthy", description="healthy/degraded")
    gpu_utilization: Optional[float] = None
    gpu_memory_used_gb: Optional[float] = None
    active_requests: Optional[int] = None
    uptime_seconds: Optional[int] = None


class AliasSetRequest(BaseModel):
    """别名切换（规范 03 §3.5：改别名指向，公网 API 不中断）"""

    model_id: str = Field(..., max_length=100, description="别名新指向的模型 ID（须 ready）")
    reason: str = Field("", max_length=500, description="切换原因（审计）")


class DrainRequest(BaseModel):
    """排空置位（规范 03 §3.4：不接新流量，存量 SSE 自然完成后下线）"""

    reason: str = Field("", max_length=500, description="排空原因（审计）")


def _require_admin(request: Request) -> None:
    """写操作管理权限校验（AuthMiddleware 已注入 request.state.user）。"""
    user = getattr(request.state, "user", None)
    if not isinstance(user, dict) or not (user.get("admin") or user.get("role") == "admin"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "registry_write_requires_admin",
                "message": "Registry 写操作需要管理面密钥（ADMIN_API_KEYS）",
            },
        )


def _require_registry_enabled() -> None:
    """写闸门：REGISTRY_ENABLED=false 时 503（Phase A 灰度开关，env 通道不受影响）。"""
    if not svc.registry_enabled():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "registry_disabled",
                "message": "REGISTRY_ENABLED 未开启（Phase A 灰度；env 通道不受影响）",
            },
        )


# ── R-01/R-02 读 ─────────────────────────────────────────────────


@router.get("/registry/v1/models", tags=["📦 模型注册中心"])
async def list_models(
    enabled_only: bool = Query(False, description="仅 enabled=true"),
    model_type: Optional[str] = Query(None, description="按能力过滤 chat/embedding/..."),
):
    """R-01 模型列表（Pull 通道数据源；含 TTL 实时健康判定）。"""
    models = await svc.list_models(enabled_only=enabled_only, model_type=model_type)
    return {"models": models, "count": len(models)}


@router.get("/registry/v1/models/{model_id}", tags=["📦 模型注册中心"])
async def get_model(model_id: str):
    """R-02 模型详情。"""
    model = await svc.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail={"error": "model_not_found"})
    return model


# ── R-03/R-04/R-05 写（admin） ───────────────────────────────────


@router.post("/registry/v1/models", status_code=201, tags=["📦 模型注册中心"])
async def register_model(req: ModelRegisterRequest, request: Request):
    """R-03 注册/更新模型（幂等覆盖；admin）。"""
    _require_admin(request)
    _require_registry_enabled()
    payload = req.model_dump()
    payload["backend_type"] = payload.pop("backend")
    payload["backend_name"] = payload["backend_type"]
    try:
        result = await svc.register_model(payload, actor=_actor(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    return {"status": "registered", **result}


@router.patch("/registry/v1/models/{model_id}", tags=["📦 模型注册中心"])
async def update_model(model_id: str, patch: dict, request: Request):
    """R-04 局部更新（白名单字段；admin）。"""
    _require_admin(request)
    _require_registry_enabled()
    updated = await svc.update_model(model_id, patch or {}, actor=_actor(request))
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "model_not_found"})
    return updated


@router.delete("/registry/v1/models/{model_id}", tags=["📦 模型注册中心"])
async def deregister_model(model_id: str, request: Request):
    """R-05 注销模型（版本历史保留可回溯；admin）。"""
    _require_admin(request)
    _require_registry_enabled()
    ok = await svc.deregister_model(model_id, actor=_actor(request))
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "model_not_found"})
    return {"status": "deregistered", "model_id": model_id}


# ── R-06/R-07 版本与回滚 ─────────────────────────────────────────


@router.get("/registry/v1/models/{model_id}/versions", tags=["📦 模型注册中心"])
async def list_versions(model_id: str):
    """R-06 版本历史（新→旧）。"""
    versions = await svc.list_versions(model_id)
    return {"versions": versions, "count": len(versions)}


@router.post("/registry/v1/models/{model_id}/rollback", tags=["📦 模型注册中心"])
async def rollback_model(model_id: str, req: RollbackRequest, request: Request):
    """R-07 回滚到历史版本（admin；目标版本必须在版本历史中存在）。"""
    _require_admin(request)
    _require_registry_enabled()
    try:
        updated = await svc.rollback_model(
            model_id, req.target_version, actor=_actor(request), reason=req.reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "model_not_found"})
    metrics_manager.record_rollback(model_id, req.target_version)
    return {
        "status": "rolled_back",
        "target_version": req.target_version,
        "model": updated,
    }


# ── Canary / Shadow（规范 03 §4-§5 半自动最小闭环，2026-10-05）──────────


class CanarySetRequest(BaseModel):
    """灰度配置（幂等覆盖；weight 0-100，0=暂停灰度仅保留 shadow 采样）"""

    baseline: str = Field(..., max_length=100, description="基线（当前公网别名指向的 model_id）")
    canary: str = Field(..., max_length=100, description="金丝雀 model_id（须 ready）")
    weight: int = Field(0, ge=0, le=100, description="灰度分流百分比")
    shadow: Optional[str] = Field(None, max_length=100, description="影子采样 model_id（可选）")


@router.put("/registry/v1/canary/{alias}", tags=["📦 模型注册中心"])
async def canary_set(alias: str, req: CanarySetRequest, request: Request):
    """创建/更新灰度配置（03 §5 stages 建议步进 5→10→30→50→100）。"""
    _require_admin(request)
    _require_registry_enabled()
    data = await svc.canary_set(
        alias, req.baseline, req.canary, req.weight, req.shadow, actor="admin-api"
    )
    return {"status": "canary_set", "alias": alias, **data}


@router.get("/registry/v1/canary/{alias}", tags=["📦 模型注册中心"])
async def canary_get(alias: str, request: Request):
    """读灰度配置（含当前生效 weight，自动回退已反映）。"""
    data = await svc.canary_get(alias)
    if not data:
        raise HTTPException(status_code=404, detail={"error": "canary_not_found"})
    return {"alias": alias, **data}


@router.delete("/registry/v1/canary/{alias}", tags=["📦 模型注册中心"])
async def canary_delete(alias: str, request: Request):
    """删除灰度配置（全量回 baseline）。"""
    _require_admin(request)
    _require_registry_enabled()
    existed = await svc.canary_delete(alias, actor="admin-api")
    if not existed:
        raise HTTPException(status_code=404, detail={"error": "canary_not_found"})
    return {"status": "canary_deleted", "alias": alias}


# ── R-08/R-09 心跳与健康 ─────────────────────────────────────────


def _check_heartbeat_token(request: "Request") -> None:
    """心跳独立认证（02 §3.2：X-YYC3-Registry-Token）。

    REGISTRY_HEARTBEAT_TOKEN 未配置 → 跳过校验（灰度兼容，现状行为不变）；
    已配置 → 模型服务心跳必须携带匹配头，否则 401（防伪造心跳注入上游池）。
    """
    expected = os.getenv("REGISTRY_HEARTBEAT_TOKEN", "").strip()
    if not expected:
        return
    provided = request.headers.get("X-YYC3-Registry-Token", "")
    if provided != expected:
        raise HTTPException(
            status_code=401,
            detail={"error": "registry_token_mismatch", "message": "X-YYC3-Registry-Token 不匹配"},
        )


@router.post("/registry/v1/models/{model_id}/heartbeat", tags=["📦 模型注册中心"])
async def heartbeat(model_id: str, req: HeartbeatRequest, request: Request):
    """R-08 心跳上报（模型服务身份；30s 周期，TTL 三级阶梯见规范 02 §4.4）。"""
    _check_heartbeat_token(request)
    ok = await svc.heartbeat(
        model_id,
        status=req.status,
        gpu_utilization=req.gpu_utilization,
        gpu_memory_used_gb=req.gpu_memory_used_gb,
        active_requests=req.active_requests,
        uptime_seconds=req.uptime_seconds,
    )
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "model_not_registered"})
    return {"model_id": model_id, "status": "received"}


@router.get("/registry/v1/models/{model_id}/health", tags=["📦 模型注册中心"])
async def get_health(model_id: str):
    """R-09 实时健康（TTL 判定 + 最近心跳运行时指标）。"""
    health = await svc.get_health(model_id)
    if health is None:
        raise HTTPException(status_code=404, detail={"error": "model_not_found"})
    return health


# ── Phase C：别名热切换与排空（规范 03 §3；admin 写 + 灰度闸门） ──


@router.get("/registry/v1/aliases", tags=["📦 模型注册中心"])
async def list_aliases():
    """R-13 别名列表（alias → model_id 路由表现状）。"""
    aliases = await svc.list_aliases()
    return {
        "aliases": aliases,
        "count": len(aliases),
        "route_cache": dict(svc._alias_cache),
    }


@router.put("/registry/v1/aliases/{alias}", tags=["📦 模型注册中心"])
async def set_alias(alias: str, req: AliasSetRequest, request: Request):
    """R-14 设置/切换别名（admin；防呆：目标须 ready。切换事件实时广播，公网 API 不中断）。"""
    _require_admin(request)
    _require_registry_enabled()
    try:
        result = await svc.set_alias(alias, req.model_id, actor=_actor(request), reason=req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    return {"status": "switched", **result}


@router.delete("/registry/v1/aliases/{alias}", tags=["📦 模型注册中心"])
async def delete_alias(alias: str, request: Request):
    """R-14b 删除别名（admin；下线流程 §8 第 2 步）。"""
    _require_admin(request)
    _require_registry_enabled()
    ok = await svc.delete_alias(alias, actor=_actor(request))
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "alias_not_found"})
    return {"status": "deleted", "alias": alias}


@router.post("/registry/v1/models/{model_id}/drain", tags=["📦 模型注册中心"])
async def drain_model(model_id: str, req: DrainRequest, request: Request):
    """R-15 置 draining 排空态（admin；不接新流量 + 存量排空观测，幂等）。

    恢复承接流量用既有 PATCH state=ready（undrain 语义）；彻底下线见规范 03 §8。
    """
    _require_admin(request)
    _require_registry_enabled()
    health = await svc.drain_model(model_id, actor=_actor(request), reason=req.reason)
    if health is None:
        raise HTTPException(status_code=404, detail={"error": "model_not_found"})
    return {"status": "draining", "drain_observation": health}


# ── R-10 事件流（SSE） ───────────────────────────────────────────


@router.get("/registry/v1/events", tags=["📦 模型注册中心"])
async def events_stream(
    since_id: int = Query(0, ge=0), timeout_seconds: int = Query(300, ge=1, le=3600)
):
    """R-10 事件流（SSE）：先回放在途事件（model_events，防漏）再订阅 Redis 实时推送。"""
    from app.cache import redis_client

    async def _stream():
        last_id = since_id
        # 追平在途事件（连接建立前已发生的）
        for event in await svc.recent_events(since_id=last_id):
            last_id = max(last_id, event["id"])
            payload = json.dumps(event, ensure_ascii=False, default=str)
            yield f"id: {event['id']}\ndata: {payload}\n\n"
        yield ": replay_done\n\n"
        # 实时订阅（Push 通道）
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(svc.REGISTRY_EVENTS_CHANNEL)
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        try:
            while asyncio.get_event_loop().time() < deadline:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if msg and msg.get("type") == "message":
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", "replace")
                    yield f"data: {data}\n\n"
                else:
                    yield ": ping\n\n"  # 保活注释帧
        finally:
            try:
                await pubsub.unsubscribe(svc.REGISTRY_EVENTS_CHANNEL)
                await pubsub.close()
            except Exception:
                pass

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── R-11/R-12 Manifest 与审计 ────────────────────────────────────


@router.get("/registry/v1/manifests/{manifest_hash}", tags=["📦 模型注册中心"])
async def get_manifest(manifest_hash: str):
    """R-11 按 hash 取 Manifest（不可变版本清单）。"""
    rec = await svc.get_manifest_by_hash(manifest_hash)
    if rec is None:
        raise HTTPException(status_code=404, detail={"error": "manifest_not_found"})
    return rec


@router.get("/registry/v1/audit", tags=["📦 模型注册中心"])
async def list_audit(
    request: Request,
    model_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """R-12 审计日志（admin；保留 365 天）。"""
    _require_admin(request)
    logs = await svc.list_audit_logs(model_id, limit)
    return {"logs": logs, "count": len(logs)}


def _actor(request: Request) -> str:
    """操作者标识（审计用；admin 面从认证上下文取，缺省 registry-api）。"""
    user = getattr(request.state, "user", None)
    if isinstance(user, dict):
        return user.get("type") or user.get("user_id") or "registry-api"
    return "registry-api"
