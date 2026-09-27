# file: app/api/admin_upstreams.py
# description: 上游池 CRUD（第 3 步写通道）：OPENAI_COMPATIBLE_UPSTREAMS 运行时读写
#              双写：真源 = 宿主 .env（auto-deploy 兼容），容器内挂载 /run/secrets/gateway.env；
#              变更后 registry.load_from_env() 热重载，进程零重启。
# author: YanYuCloudCube Team
# created: 2026-09-27
# tags: [admin],[upstream],[crud]

import json
import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

ENV_VAR = "OPENAI_COMPATIBLE_UPSTREAMS"

# 安全：挂载点纯常量（不接受 env/请求覆盖——改动挂载位置需修改本文件走代码评审）
ENV_PATH = Path("/run/secrets") / "gateway.env"


def _read_pool() -> list:
    raw = os.environ.get(ENV_VAR, "[]")
    try:
        pool = json.loads(raw)
        return pool if isinstance(pool, list) else []
    except json.JSONDecodeError:
        return []


def _write_pool(pool: list) -> None:
    """进程 env 更新 + 挂载文件仅替换本变量行（其余行原样保留，原子替换）。"""
    val = json.dumps(pool, ensure_ascii=False)
    os.environ[ENV_VAR] = val
    if not ENV_PATH.is_file():
        logger.warning(f"env 挂载文件不存在（仅进程内生效，重启后丢失）: {ENV_PATH}")
        return
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        out, done = [], False
        for line in lines:
            if line.startswith(ENV_VAR + "="):
                out.append(ENV_VAR + "=" + val)
                done = True
            else:
                out.append(line)
        if not done:
            out.append(ENV_VAR + "=" + val)
        tmp = Path(str(ENV_PATH) + ".tmp")
        tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
        tmp.replace(ENV_PATH)
    except OSError as e:
        logger.warning(f"env 文件写入失败（仅进程内生效）: {e}")


class UpstreamIn(BaseModel):
    name: str
    base_url: str
    models: list = []
    capability: str = "chat"
    provider: str = "openai_compat"
    weight: float = 100.0
    priority: int = 10
    capacity: int = 32
    sovereign: bool = False
    fallback_url: str = ""
    health_path: str = "/health"


def _reload_registry():
    from app.services.upstream_registry import get_registry
    get_registry().load_from_env()


@router.get("/v1/admin/upstreams")
async def upstreams_list():
    try:
        _reload_registry()
    except Exception as e:
        logger.warning(f"热重载失败（返回 env 版本）: {e}")
    from app.services.upstream_registry import get_registry
    return {"upstreams": get_registry().snapshot(), "count": len(_read_pool())}


@router.post("/v1/admin/upstreams")
async def upstreams_create(u: UpstreamIn):
    pool = _read_pool()
    if any(x.get("name") == u.name for x in pool):
        raise HTTPException(409, f"上游名已存在: {u.name}")
    pool.append(u.dict(exclude_none=True))
    _write_pool(pool)
    _reload_registry()
    logger.info(f"上游池新增: {u.name} → {u.base_url}")
    return {"created": u.name, "count": len(pool)}


@router.put("/v1/admin/upstreams/{name}")
async def upstreams_update(name: str, u: UpstreamIn):
    pool = _read_pool()
    for i, x in enumerate(pool):
        if x.get("name") == name:
            merged = {**x, **{k: v for k, v in u.dict(exclude_none=True).items() if k != "name"}}
            pool[i] = merged
            _write_pool(pool)
            _reload_registry()
            return {"updated": name}
    raise HTTPException(404, f"上游不存在: {name}")


@router.delete("/v1/admin/upstreams/{name}")
async def upstreams_delete(name: str):
    pool = _read_pool()
    remaining = [x for x in pool if x.get("name") != name]
    if len(remaining) == len(pool):
        raise HTTPException(404, f"上游不存在: {name}")
    if not remaining:
        raise HTTPException(422, "拒绝删除最后一个上游（保留兜底）")
    _write_pool(remaining)
    _reload_registry()
    return {"deleted": name, "count": len(remaining)}
