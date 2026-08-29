# file: main.py
# description: FastAPI 应用入口文件
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [api],[main],[entry]

# @file main.py
# @description FastAPI 主应用 - 模型管理 API 端点
# @author YanYuCloudCube Team <admin@0379.email>
# @version v1.0.0
# @created 2026-03-14
# @updated 2026-03-14
# @status stable
# @license MIT
# @copyright Copyright (c) 2026 YanYuCloudCube Team
# @tags python,fastapi,api

import logging
import time
from datetime import datetime, timezone
from typing import List

import psutil
from app.api import chat, documents, knowledge_base, mcp, rag, websocket
from app.config import settings
from app.db import ModelRegistry, async_session
from app.middleware import AuthMiddleware, RateLimitMiddleware, VersioningMiddleware
from app.models import (
    ErrorRecord,
    ModelConfig,
    ModelStat,
    PingResponse,
    UsageSummary,
)
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select

app = FastAPI(
    title="YYC³ 统一模型网关",
    description="""
## 🎯 核心功能

### 支持的Provider
- **智谱GLM**: glm-4-flash, glm-4-plus（云端API）
- **Ollama**: llama3.2, codegeex4, qwen2.5等（本地部署）

### 主要接口
- `/v1/chat/completions` - 聊天完成（OpenAI兼容）
- `/v1/models` - 模型列表
- `/ws/chat` - WebSocket流式聊天
- `/ws/monitor` - 实时监控

### 知识库功能
- `/v1/knowledge-bases` - 知识库管理（创建、查询、更新、删除）
- `/v1/documents` - 文档管理（上传、解析、切片、向量化）
- `/v1/rag/search` - RAG语义检索
- `/v1/rag/ask` - 基于知识库的问答

### 认证方式
- **API Key**: 在请求头添加 `X-API-Key: YOUR_API_KEY`
- **JWT**: 在请求头添加 `Authorization: Bearer YOUR_JWT_TOKEN`

### 使用示例
```bash
# 获取模型列表
curl -H "X-API-Key: YOUR_API_KEY" https://api.0379.world/v1/models

# 聊天请求
curl -X POST https://api.0379.world/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 创建知识库
curl -X POST https://api.0379.world/v1/knowledge-bases \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -d '{
    "name": "技术文档库",
    "description": "包含所有技术文档"
  }'

# 上传文档
curl -X POST https://api.0379.world/v1/documents/upload?knowledge_base_id=xxx \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -F "file=@document.pdf"

# RAG检索
curl -X POST https://api.0379.world/v1/rag/search \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -d '{
    "query": "如何部署模型？",
    "knowledge_base_ids": ["xxx"],
    "top_k": 5
  }'
```
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    servers=[
        {"url": "https://api.0379.world", "description": "Production"},
    ],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# P0: 补全 OpenAPI Security Scheme，让 Swagger UI 出现 Authorize 按钮
from fastapi.openapi.utils import get_openapi


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "APIKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "YYC³ API Key 认证",
        },
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Token 认证",
        },
    }
    openapi_schema["security"] = [{"APIKey": []}, {"Bearer": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.on_event("startup")
async def validate_critical_config():
    """启动时校验关键配置，防止生产环境使用默认值"""
    logger = logging.getLogger(__name__)

    critical_checks = [
        ("JWT_SECRET_KEY", settings.jwt_secret_key,
         lambda v: v and v != "change_me_in_production"),
        ("API_KEYS", settings.api_keys,
         lambda v: bool(v)),
        ("POSTGRES_PASSWORD", settings.db_password,
         lambda v: v and v != "change_me_in_production"),
        ("REDIS_PASSWORD", settings.redis_password,
         lambda v: v and v != "change_me_in_production"),
    ]

    errors = []
    warnings = []

    for name, value, check in critical_checks:
        if not check(value):
            errors.append(name)

    if errors:
        msg = f"关键配置缺失或使用默认值: {', '.join(errors)}"
        if settings.auth_enabled:
            logger.critical(msg)
            raise RuntimeError(msg)
        else:
            logger.warning(f"[非生产模式] {msg}")

    # ── 非关键但建议配置的项 ──
    if not settings.zhipu_api_key:
        warnings.append("ZHIPU_API_KEY")
    if not settings.deepseek_api_key:
        warnings.append("DEEPSEEK_API_KEY")
    if not settings.openai_api_key:
        warnings.append("OPENAI_API_KEY")

    if not errors and warnings:
        logger.info(f"以下 API Key 未配置（按需忽略）: {', '.join(warnings)}")

    logger.info("配置校验通过，服务启动正常")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(VersioningMiddleware)

START_TIME = time.time()

app.include_router(chat.router, prefix="/v1", tags=["💬 聊天"])
app.include_router(mcp.router, prefix="/v1", tags=["🔧 MCP工具"])
app.include_router(websocket.router, tags=["🔌 WebSocket"])
app.include_router(knowledge_base.router, tags=["📚 知识库管理"])
app.include_router(documents.router, tags=["📄 文档管理"])
app.include_router(rag.router, tags=["🔍 RAG检索"])


@app.get("/health")
async def health_check():
    """
    健康检查端点

    返回系统状态、服务可用性、资源使用情况（并发检查）
    """
    from app.utils.metrics import metrics_manager

    async def _check_ollama():
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                return {
                    "status": "healthy" if resp.status_code == 200 else "unhealthy",
                    "latency_ms": int(resp.elapsed.total_seconds() * 1000),
                }
        except Exception:
            return {"status": "unreachable"}

    async def _check_redis():
        try:
            from app.cache import redis_client

            await redis_client.ping()
            return {"status": "healthy"}
        except Exception:
            return {"status": "unreachable"}

    async def _check_postgresql():
        try:
            from sqlalchemy import text as sa_text

            async with async_session() as session:
                await session.execute(sa_text("SELECT 1"))
                return {"status": "healthy"}
        except Exception:
            return {"status": "unreachable"}

    # 并发检查所有外部服务
    import asyncio

    ollama_result, redis_result, pg_result = await asyncio.gather(
        _check_ollama(),
        _check_redis(),
        _check_postgresql(),
        return_exceptions=True,
    )

    services = {
        "ollama": ollama_result if not isinstance(ollama_result, BaseException) else {"status": "error"},
        "zhipu": {
            "status": "configured" if settings.zhipu_api_key else "not_configured",
        },
        "redis": redis_result if not isinstance(redis_result, BaseException) else {"status": "error"},
        "postgresql": pg_result if not isinstance(pg_result, BaseException) else {"status": "error"},
    }

    # 系统资源
    system = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "uptime_seconds": int(time.time() - START_TIME),
        "services": services,
        "system": system,
        "metrics": {
            "active_requests": metrics_manager.get_active_requests(),
            "total_requests": metrics_manager.get_total_requests(),
            "cache_hit_rate": metrics_manager.get_cache_hit_rate(),
        },
    }


@app.get("/healthz")
async def healthz():
    """轻量存活探针（供监控/负载均衡高频探活）

    与 /health 的区别：不做外部服务依赖检查，仅确认进程存活，
    开销极小，适合 Prometheus/Traefik/监控探活高频调用。
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int(time.time() - START_TIME),
    }


@app.get("/v1/ping", response_model=PingResponse)
async def ping():
    """健康检查端点"""
    return PingResponse(status="ok")


@app.get("/v1/cache/stats")
async def get_cache_stats():
    """获取缓存统计（命中率、操作计数）"""
    from app.utils import cache_manager

    return cache_manager.get_stats()


@app.get("/v1/cache/info")
async def get_cache_info():
    """获取缓存详细信息（条目数、LRU淘汰状态、TTL配置）"""
    from app.cache import get_cache_info

    return await get_cache_info()


@app.post("/v1/cache/invalidate/{model_name}")
async def invalidate_cache(model_name: str):
    """按模型名主动失效缓存"""
    from app.cache import invalidate_model_cache

    count = await invalidate_model_cache(model_name)
    return {"model": model_name, "invalidated": count}


@app.delete("/v1/cache/all")
async def clear_cache():
    """清空所有LLM缓存"""
    from app.cache import clear_all_cache

    count = await clear_all_cache()
    return {"cleared": count}


@app.get("/v1/router/stats")
async def get_router_stats():
    """获取模型路由器节点统计（动态权重、EWMA延迟、错误率）"""
    from app.services.model_router import model_router

    return model_router.get_node_stats()


@app.get("/v1/router/health")
async def get_router_health():
    """触发一次路由器健康检查并返回结果"""
    from app.services.model_router import model_router

    await model_router.health_check()
    return model_router.get_node_stats()


@app.get("/v1/model/type")
async def get_model_type(model: str = Query(...)):
    """
    获取模型后端类型（用于 Traefik/HAProxy 的 GPU 感知路由）

    返回:
    - local_cpu: Ollama CPU 推理
    - local_gpu: Ollama GPU 推理（DGX Spark）
    - openai: OpenAI API
    - zhipu: 智谱 AI API
    - deepseek: DeepSeek API
    - unknown: 未注册模型
    """
    try:
        async with async_session() as session:
            from app.db import ModelRegistry
            from sqlalchemy import select

            result = await session.execute(
                select(ModelRegistry.backend_type, ModelRegistry.backend_name)
                .where(ModelRegistry.id == model)
                .where(ModelRegistry.enabled.is_(True))
            )
            row = result.first()
            if row:
                return {"model": model, "backend_type": row.backend_type, "backend_name": row.backend_name}
    except Exception:
        pass

    # 回退：根据模型名前缀推断
    if any(model.startswith(p) for p in ["glm-4", "zhipu:"]):
        return {"model": model, "backend_type": "zhipu", "backend_name": model}
    if any(model.startswith(p) for p in ["gpt-", "openai:"]):
        return {"model": model, "backend_type": "openai", "backend_name": model}
    if any(model.startswith(p) for p in ["deepseek-", "deepseek:"]):
        return {"model": model, "backend_type": "deepseek", "backend_name": model}
    if any(model.startswith(p) for p in ["llama", "codegeex", "qwen", "local:", "ollama:"]):
        return {"model": model, "backend_type": "local_cpu", "backend_name": model}

    return JSONResponse(status_code=404, content={"error": "Model not found", "model": model})


@app.get("/v1/versions")
async def get_api_versions():
    """获取所有API版本状态（current/deprecated/sunset）"""
    from app.middleware.versioning import VersioningMiddleware

    return VersioningMiddleware.get_version_info()


# ── 默认模型配置 ──────────────────────────────────────────
# 可通过数据库 model_registry 表动态扩展（Ollama模型）
DEFAULT_MODELS = [
    # 智谱GLM
    ModelConfig(id="glm-4-flash", display_name="智谱GLM-4 Flash", backend="zhipu",
                enabled=True, max_tokens=128000, temperature=0.7, top_p=0.9, cost_per_1k_tokens=0.001),
    ModelConfig(id="glm-4-plus", display_name="智谱GLM-4 Plus", backend="zhipu",
                enabled=True, max_tokens=128000, temperature=0.7, top_p=0.9, cost_per_1k_tokens=0.05),
    # DeepSeek
    ModelConfig(id="deepseek-chat", display_name="DeepSeek Chat", backend="deepseek",
                enabled=True, max_tokens=64000, temperature=0.7, top_p=0.9, cost_per_1k_tokens=0.001),
    ModelConfig(id="deepseek-coder", display_name="DeepSeek Coder", backend="deepseek",
                enabled=True, max_tokens=16000, temperature=0.7, top_p=0.9, cost_per_1k_tokens=0.001),
    # Ollama本地（默认）
    ModelConfig(id="llama3.2", display_name="Llama 3.2 (本地)", backend="ollama",
                enabled=True, max_tokens=128000, temperature=0.7, top_p=0.9, cost_per_1k_tokens=0.0),
    ModelConfig(id="codegeex4", display_name="CodeGeeX4 (本地)", backend="ollama",
                enabled=True, max_tokens=128000, temperature=0.7, top_p=0.9, cost_per_1k_tokens=0.0),
    ModelConfig(id="qwen2.5", display_name="通义千问 2.5 (本地)", backend="ollama",
                enabled=True, max_tokens=128000, temperature=0.7, top_p=0.9, cost_per_1k_tokens=0.0),
]

# DB注册的默认Ollama模型ID（避免重复）
_DEFAULT_OLLAMA_IDS = {"llama3.2", "codegeex4", "qwen2.5"}


@app.get("/v1/models", response_model=List[ModelConfig])
async def list_models():
    """
    获取可用模型列表

    支持的Provider：
    - zhipu: 智谱GLM（glm-4-flash, glm-4-plus）
    - deepseek: DeepSeek（deepseek-chat, deepseek-coder）
    - ollama: 本地模型（llama3.2, codegeex4, qwen2.5等）
    数据库动态注册的模型自动附加
    """
    models = list(DEFAULT_MODELS)

    # 从数据库加载动态注册的Ollama模型
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ModelRegistry.id, ModelRegistry.display_name)
                .where(ModelRegistry.enabled.is_(True))
                .where(ModelRegistry.backend_type == "ollama")
            )
            for row in result:
                if row.id not in _DEFAULT_OLLAMA_IDS:
                    models.append(
                        ModelConfig(
                            id=row.id, display_name=row.display_name,
                            backend="ollama", enabled=True,
                            max_tokens=128000, temperature=0.7, top_p=0.9,
                            cost_per_1k_tokens=0.0,
                        )
                    )
    except Exception:
        pass

    return models


@app.get("/v1/models/stats", response_model=List[ModelStat])
async def get_stats():
    """获取所有模型统计信息"""
    async with async_session() as session:
        from app.db import UsageLog
        from sqlalchemy import func

        result = await session.execute(
            select(
                UsageLog.model,
                func.count(UsageLog.id).label("usage_count"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
            ).group_by(UsageLog.model)
        )
        stats = []
        for row in result:
            stats.append(
                ModelStat(
                    model_id=row.model,
                    usage_count=row.usage_count or 0,
                    avg_latency_ms=0.0,
                    error_rate=0.0,
                    total_tokens=row.total_tokens or 0,
                )
            )
        return stats


@app.get("/v1/models/errors", response_model=List[ErrorRecord])
async def get_errors():
    """获取所有错误记录"""
    return []


@app.get("/v1/models/summary", response_model=UsageSummary)
async def get_summary():
    """获取使用摘要"""
    async with async_session() as session:
        from app.db import UsageLog
        from sqlalchemy import func

        result = await session.execute(
            select(
                func.count(UsageLog.id).label("total_requests"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
            )
        )
        row = result.first()
        total_requests = row.total_requests if row and row.total_requests else 0
        total_tokens = row.total_tokens if row and row.total_tokens else 0
        return UsageSummary(
            total_requests=total_requests,
            total_tokens=total_tokens,
            cost_usd=0.0,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
