---
file: YYC3-API-全链路闭环文档.md
description: YYC3-0379-World 生产级 API 全链路闭环文档
author: YanYuCloudCube Team <admin@0379.email>
version: v1.1.0
created: 2026-08-30
updated: 2026-09-03
status: active
tags: [api],[full-link],[production],[closed-loop]
category: documentation
---

# YYC3-0379-World API 全链路闭环文档

> **版本**: v1.1.0 | **更新日期**: 2026-09-03（原 v1.0.0 2026-08-30）
> **网关版本**: v2.0.0 | **生产域名**: `https://api.0379.world`
> **文档定位**: 面向开发、测试、运维三团队的单一事实来源 (Single Source of Truth)
>
> **v1.1 实况改版要点（2026-09-03 基线）**：
> ① **推理底座已换代**——双 DGX 经 NCCL 2.30.7 门禁后，**DeepSeek-V4-Flash（284B MoE/A13B）TP=2 双机张量并行服务在 N1:8001 上线**（QSFP 210Gbps 链路，双机内存对称 96G/121G，64K ctx）；
> ② 部署链已 GitOps 化（Mac 部署桥自动同步，见 §9.5）；③ RAG 组件三件套处于"旗舰独占期暂离"（恢复=容器化 §9.6）；④ 网关代码五缺陷（路由死代码/上游硬编码/4 端点缺失/观测假数据）仍未修——**本文档所有"规划态"均以《Gateway代码分析与落地方案》A 线为准绳**；⑤ 新模型三路在途（GLM-5.3-Flash 306G/Qwen3.8-Flash-Next 131 分片/MiniMax-H3-NF4 视频生成，hf-mirror 通道 29-117MB/s）。

---

## 目录

- [一、系统架构总览](#一系统架构总览)
- [二、设备矩阵与基础设施](#二设备矩阵与基础设施)
- [三、模型资产清单](#三模型资产清单)
- [四、API 接口规范](#四api-接口规范)
- [五、数据流转流程](#五数据流转流程)
- [六、安全策略](#六安全策略)
- [七、错误处理机制](#七错误处理机制)
- [八、性能指标与监控](#八性能指标与监控)
- [九、部署指南](#九部署指南)
- [十、维护与运维手册](#十维护与运维手册)
- [附录 A: 环境变量清单](#附录-a-环境变量清单)
- [附录 B: 快速命令参考](#附录-b-快速命令参考)

---

## 一、系统架构总览

### 1.1 全链路拓扑

```
┌─────────────┐     ┌──────────────────────────────────────────────────────┐
│  公网用户   │────▶│  yyc3-33 ECS (39.97.53.176)                        │
│             │     │  Ubuntu 24.04 / 7.1GB RAM / 79GB Disk               │
│             │     │  Traefik v2 (TLS 1.3, Let's Encrypt)               │
│             │     │  路由: gateway-api-primary@file                    │
└─────────────┘     └──────────────┬───────────────────────────────────────┘
                                   │ Tailscale VPN (100.x.x.x)
                                   ▼
└─────────────┐     ┌──────────────────────────────────────────────────────┐
│  DGX GPU    │     │  yyc3-45 NAS (100.65.172.88)                        │
│  推理集群   │     │  TerraMaster F4-423 / 32GB DDR4                    │
│             │     │  Docker Compose (bridge: yyc3-network)              │
│             │     │  ┌─────────────────────────────────────┐            │
│             │     │  │  Gateway v2.0.0 (:8000)             │            │
│             │     │  │  FastAPI + Uvicorn (4 workers)      │            │
│             │     │  │  ┌──────────┐ ┌──────────┐         │            │
│             │     │  │  │ PostgreSQL│ │  Redis 7  │         │            │
│             │     │  │  │  15-alpine│ │  7-alpine │         │            │
│             │     │  │  └──────────┘ └──────────┘         │            │
│             │     │  └─────────────┬───────────────────────┘            │
└─────────────┘     └────────────────┼────────────────────────────────────┘
                                   │ 模型路由 (Backend Selection)
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
     │ 云端 API       │  │ Ollama 本地    │  │ DGX vLLM       │
     │ (公网直连)     │  │ (:11434)       │  │ (GPU 推理)     │
     │                │  │                │  │                │
     │ - 智谱 GLM-4   │  │ - CodeGeeX4-9B │  │ - DeepSeek-V4  │
     │ - DeepSeek     │  │ - Qwen3-14B   │  │ - GLM-5.1      │
     │ - OpenAI       │  │ - ChatGLM3-6B │  │ - Kimi-K2.6    │
     └────────────────┘  └────────────────┘  └────────────────┘
```

### 1.2 核心组件清单

| 组件 | 技术 | 版本 | 端口 | 说明 |
| ------ | ------ | ------ | ------ | ------ |
| API Gateway | FastAPI + Uvicorn | 2.0.0 | 8000 | 统一模型网关 |
| 反向代理 | Traefik | v2 | 80/443 | TLS终止 + 路由 |
| 数据库 | PostgreSQL | 15-alpine | 5432(容器内) | 模型注册/用量统计 |
| 缓存 | Redis | 7-alpine | 6379(容器内) | LLM缓存/限流/会话 |
| 监控 | Prometheus + Grafana | - | 9090/3000 | 指标采集/可视化 |
| 本地推理 | Ollama | latest | 11434 | CPU/GPU 本地模型 |
| 容器编排 | Docker Compose | 3.8 | - | 服务编排 |
| 内网穿透 | Tailscale | - | - | VPN 组网 |

### 1.3 中间件执行链

请求按以下顺序经过中间件栈（外层先执行）:

```
Request
  │
  ▼
1. VersioningMiddleware    ← API 版本控制
  │
  ▼
2. RateLimitMiddleware     ← Redis 分布式滑动窗口限流
  │
  ▼
3. AuthMiddleware          ← JWT / API Key 双重认证
  │
  ▼
4. CORSMiddleware           ← 跨域策略
  │
  ▼
5. Router Handler           ← 业务处理
```

---

## 二、设备矩阵与基础设施

### 2.1 五端设备矩阵

| 设备编号 | 主机名 | 角色 | 硬件规格 | 网络标识 | 存储职责 |
| --------- | -------- | ------ | --------- | --------- | --------- |
| **YYC3-22** | macOS 本机 | 开发机 | Apple Silicon / 外挂存储 | Tailscale: 本机 IP | `/Volumes/Max/models` — 开发测试模型 |
| **YYC3-33** | ECS | 公网入口 | Ubuntu 24.04 / 7.1GB RAM / 79GB Disk | 公网: `39.97.53.176` / Tailscale: `100.126.132.112` | Traefik 反代，不含模型数据 |
| **YYC3-45** | NAS | 存储+网关 | TerraMaster F4-423 / Celeron N5095 / 32GB DDR4 | Tailscale: `100.65.172.88` | 模型数据 + Docker 应用部署 |
| **YYC3-DGX-101** | DGX GPU-1 | GPU 推理主力 | NVIDIA DGX Spark / GB10 Blackwell / 121.7GB VRAM | Tailscale: DGX-101 | 大模型推理训练 + AI Agent 运行 |
| **YYC3-DGX-102** | DGX GPU-2 | GPU 推理+训练 | NVIDIA DGX Spark / GB10 Blackwell | Tailscale: DGX-102 | DPO 微调训练 + AI Agent 部署 |

### 2.2 NAS 存储架构 (YYC3-45)

```
┌─────────────────────────────────────────────────────────┐
│  TerraMaster F4-423                                      │
│                                                          │
│  ┌─ HDD Pool ─────────────────────────────────────────┐ │
│  │ 4 x 8TB WDC HDD (RAID6 = 14.5TB 可用)              │ │
│  │  ├─ Volume1: /Volume1/yyc3_hd/data                  │ │
│  │  │   └─ 大模型仓库 (14 个模型, 含 DeepSeek/GLM/Kimi) │ │
│  │  └─ Volume2: /Volume2/docker                        │ │
│  │       ├─ /Volume2/docker/models (8 个 Docker 挂载模型)│ │
│  │       └─ /Volume2/yyc3-33/ (Gateway 部署目录)       │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ NVMe Pool ─────────────────────────────────────────┐ │
│  │ 2 x 2TB WD_BLACK SN850X NVMe (RAID1 = 1.8TB 可用)  │ │
│  │  └─ Volume3: Docker/应用热数据                      │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Docker 网桥: 172.17.0.1                                │
│  Tailscale: 100.65.172.88                               │
└─────────────────────────────────────────────────────────┘
```

---

## 三、模型资产清单

### 3.1 模型总览

**生产实况层（2026-09-03，v1.1 新增）**：

| 层 | 模型 | 端点 | 状态 |
|----|------|------|------|
| **旗舰推理** | deepseek-v4-flash（TP=2 双机） | `http://100.65.64.49:8001/v1`（QSFP 内网 10.100.168.2:8001） | ✅ 服务中（启动/回退命令见《双机推理部署指南》§19） |
| 轻量层 | NAS Ollama 系 | `:11434` | ✅ |
| 云端兜底 | 智谱/DeepSeek/OpenAI | 公网 | ✅（注意 ZHIPU_KEY 曾过期，启动校验会拦截） |
| RAG 三件套 | Qwen3-Embedding/Reranker-8B、ChromaDB | `:8100/:8101/:8102` | ⏸ 旗舰独占期暂离（恢复=容器化，指南 §15.3） |
| 在途 | GLM-5.3-Flash（多模态旗舰候选）/ Qwen3.8-Flash-Next（轻旗舰降级位）/ MiniMax-H3-NF4（视频生成） | — | ⬇ hf-mirror 下载中（N1 projects/models） |

**注册表模型（Gateway DB 视角，历史层）**：

| 后端类型 | 模型 ID | 显示名称 | 上下文长度 | 成本/1K tokens | 部署位置 |
| --------- | --------- | --------- | ----------- | --------------- | --------- |
| **zhipu** | `glm-4-flash` | 智谱 GLM-4 Flash | 128K | $0.001 | 云端 API |
| **zhipu** | `glm-4-plus` | 智谱 GLM-4 Plus | 128K | $0.05 | 云端 API |
| **deepseek** | `deepseek-chat` | DeepSeek Chat | 64K | $0.001 | 云端 API |
| **deepseek** | `deepseek-coder` | DeepSeek Coder | 16K | $0.001 | 云端 API |
| **openai** | `gpt-4` / `gpt-4o` / `gpt-3.5-turbo` | OpenAI 系列 | - | 按量 | 云端 API |
| **ollama** | `llama3.2` | Llama 3.2 (本地) | 128K | $0 | NAS Docker |
| **ollama** | `codegeex4` | CodeGeeX4 (本地) | 128K | $0 | NAS Docker |
| **ollama** | `qwen2.5` | 通义千问 2.5 (本地) | 128K | $0 | NAS Docker |
| **ollama** | DB 动态注册 | Ollama 自定义模型 | - | $0 | NAS Docker |

### 3.2 NAS 模型路径映射

**Volume1 — 大模型仓库** (`/Volume1/yyc3_hd/data`):

| 模型 | 路径 | 说明 |
| ------ | ------ | ------ |
| DeepSeek-Base | `/Volume1/yyc3_hd/data/DeepSeek-Base` | DeepSeek 基座模型 |
| DeepSeek-V4-Flash | `/Volume1/yyc3_hd/data/DeepSeek-V4-Flash` | 284B MoE, 推理优化 |
| DeepSeek-V4-Pro | `/Volume1/yyc3_hd/data/DeepSeek-V4-Pro` | DeepSeek 旗舰版 |
| GLM-5.1 | `/Volume1/yyc3_hd/data/GLM-5.1` | 智谱最新一代 |
| GLM-5.1-FP8 | `/Volume1/yyc3_hd/data/GLM-5.1-FP8` | FP8 量化版 |
| Kimi-K2.6 | `/Volume1/yyc3_hd/data/Kimi-K2.6` | Moonshot 1T MoE |
| Ring-2.6-1T | `/Volume1/yyc3_hd/data/Ring-2.6-1T` | 1T 参数超大模型 |
| Qwen3.5-122B-A10B | `/Volume1/yyc3_hd/data/Qwen/Qwen3.5-122B-A10B` | MoE 架构 |
| Qwen3.5-397B-A17B | `/Volume1/yyc3_hd/data/Qwen/Qwen3.5-397B-A17B` | 旗舰 MoE |
| Qwen3.6-27B / FP8 | `/Volume1/yyc3_hd/data/Qwen/Qwen3.6-27B*` | 含 FP8 量化 |
| Qwen3.6-35B-A3B / FP8 | `/Volume1/yyc3_hd/data/Qwen/Qwen3.6-35B-A3B*` | MoE 架构 |
| Qwen3-8B | `/Volume1/yyc3_hd/data/Qwen/Qwen3-8B` | 轻量级 |
| Qwen3-Coder-30B-A3B | `/Volume1/yyc3_hd/data/Qwen/Qwen3-Coder-30B-A3B` | 代码专用 MoE |
| Qwen3-Embedding/Reranker-8B | `/Volume1/yyc3_hd/data/Qwen/Qwen3-*-8B` | RAG 检索增强 |
| MiniCPM-V-4.6 | `/Volume1/yyc3_hd/data/MiniCPM-V-4.6` | 多模态视觉 |
| MegaStyle-1.4M | `/Volume1/yyc3_hd/data/MegaStyle-1.4M` | 风格迁移 |

**Volume2 — Docker 挂载模型** (`/Volume2/docker/models`):

| 模型 | 路径 | Ollama 挂载 |
| ------ | ------ | ------------- |
| ChatGLM3-6B | `/Volume2/docker/models/ChatGLM3-6B` | ✅ |
| CodeGeeX4-9B / Q8 | `/Volume2/docker/models/CodeGeeX4-9B*` | ✅ |
| Cogagent-9B | `/Volume2/docker/models/Cogagent-9B` | ✅ |
| Cogvideox-5B | `/Volume2/docker/models/Cogvideox-5B` | ✅ |
| Qwen3-14B | `/Volume2/docker/models/Qwen3-14B` | ✅ |
| Qwen3-14B-YYC3-merged | `/Volume2/docker/models/Qwen3-14B-YYC3-merged` | ✅ (微调版) |
| Qwen3-14B-YYC3-merged-gguf | `/Volume2/docker/models/Qwen3-14B-YYC3-merged-gguf` | ✅ (GGUF 量化) |

### 3.3 模型路由选择逻辑

```
请求 model 字段
  │
  ├─ glm-4-flash / glm-4-plus / glm-4 / zhipu:*   → zhipu 后端
  ├─ deepseek-chat / deepseek-coder / deepseek:*    → deepseek 后端
  ├─ gpt-4 / gpt-4o / gpt-3.5-turbo / openai:*     → openai 后端
  ├─ ollama:* / local:*                              → ollama 后端 (指定模型名)
  └─ 其他                                            → ollama 后端 (默认回退)
```

> ⚠️ **v1.1 实况注记**：以上为**设计行为**。当前网关代码（chat.py:53-87）为模型名前缀**硬编码匹配**，EWMA 智能路由算法（model_router.py）完整但未接线，`/v1/router/stats` 返回硬编码数据——修复排期见《Gateway代码分析与落地方案》A 线 P1；**旗舰 :8001 接入网关依赖该线完成**（upstream pool 配置化）。

**GPU 感知路由**: 通过 `/v1/model/type` 端点可查询模型后端类型 (`local_cpu` / `local_gpu` / `zhipu` / `deepseek` / `openai`)，供 Traefik/HAProxy 做智能分流。

---

## 四、API 接口规范

### 4.1 认证方式

所有接口（除免认证端点外）支持双重认证:

**方式一: API Key（推荐）**

```
X-API-Key: sk-yyc3-prod-key-001
```

**方式二: JWT Bearer**

```
Authorization: Bearer <jwt_token>
```

**免认证端点** (SKIP_AUTH_PATHS):

| 端点 | 说明 |
| ------ | ------ |
| `/v1/ping` | 轻量存活检查 |
| `/health` | 完整健康检查（含服务依赖） |
| `/healthz` | 轻量存活探针（供 Traefik/Prometheus 高频探活） |
| `/metrics` | Prometheus 指标 |
| `/docs` / `/openapi.json` / `/redoc` | Swagger 文档 |

### 4.2 Chat Completions

**核心端点**: `POST /v1/chat/completions`

**请求体**:

```json
{
  "model": "glm-4-flash",
  "messages": [
    {"role": "system", "content": "你是一个专业的助手"},
    {"role": "user", "content": "你好"}
  ],
  "max_tokens": 4096,
  "temperature": 0.7,
  "top_p": 0.9,
  "stream": false,
  "user_id": "optional-user-id"
}
```

**字段约束**:

| 字段 | 类型 | 必填 | 约束 |
| ------ | ------ | ------ | ------ |
| `model` | string | 是 | 1-100 字符 |
| `messages` | array | 是 | 1-50 条消息，每条 content 1-100K 字符 |
| `messages[].role` | enum | 是 | `system` / `user` / `assistant` |
| `messages[].content` | string | 是 | 非空，自动 strip |
| `max_tokens` | int | 否 | 1-128000，默认由模型配置决定 |
| `temperature` | float | 否 | 0.0-2.0，默认 0.7 |
| `top_p` | float | 否 | 0.0-1.0 |
| `stream` | bool | 否 | 默认 false |
| `user_id` | string | 否 | 最多 100 字符 |

**同步响应** (`stream: false`):

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "glm-4-flash",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}
}
```

**流式响应** (`stream: true`): SSE 格式

```
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"你"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"好"},"index":0}]}

data: [DONE]
```

### 4.3 模型管理

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| GET | `/v1/models` | 需要 | 获取可用模型列表（含 DB 动态注册 + 默认模型） |
| GET | `/v1/model/type?model=xxx` | 需要 | 查询模型后端类型（GPU 感知路由用） |
| GET | `/v1/router/stats` | 需要 | 路由器节点统计（EWMA 延迟、错误率、动态权重） |
| GET | `/v1/router/health` | 需要 | 触发路由器健康检查 |

### 4.4 缓存管理

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| GET | `/v1/cache/stats` | 需要 | 缓存统计（命中率、操作计数） |
| GET | `/v1/cache/info` | 需要 | 缓存详情（条目数、LRU 状态、TTL 配置） |
| POST | `/v1/cache/invalidate/{model_name}` | 需要 | 按模型名失效缓存 |
| DELETE | `/v1/cache/all` | 需要 | 清空所有 LLM 缓存 |

### 4.5 知识库 & RAG

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| POST/GET | `/v1/knowledge-bases` | 需要 | 知识库 CRUD |
| POST | `/v1/documents/upload` | 需要 | 上传文档（支持 PDF/DOCX/TXT 等） |
| POST | `/v1/rag/search` | 需要 | RAG 语义检索 |
| POST | `/v1/rag/ask` | 需要 | 基于知识库的问答 |

### 4.6 MCP 工具

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| GET | `/v1/mcp/tools` | 需要 | 获取 MCP 工具列表 |
| POST | `/v1/mcp/execute` | 需要 | 执行 MCP 工具 |

### 4.7 WebSocket

| 端点 | 认证 | 说明 |
|------|------|------|
| `/ws/chat` | 需要 | 流式聊天 WebSocket |
| `/ws/monitor` | 需要 | 实时监控数据推送 |

### 4.8 系统 & 监控

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| GET | `/v1/ping` | **免认证** | 轻量存活检查 `{"status":"ok"}` |
| GET | `/health` | **免认证** | 完整健康检查（含 ollama/redis/pg 状态 + 系统资源 + 指标） |
| GET | `/healthz` | **免认证** | 极轻量探活 `{"status":"alive", "uptime_seconds": N}` |
| GET | `/metrics` | **免认证** | Prometheus 格式指标 |
| GET | `/v1/versions` | 需要 | API 版本状态列表 |
| GET | `/docs` | **免认证** | Swagger UI |
| GET | `/redoc` | **免认证** | ReDoc 文档 |

---

## 五、数据流转流程

### 5.1 Chat 请求完整生命周期

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Chat Request Lifecycle                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. 客户端发送 POST /v1/chat/completions                             │
│     │                                                                │
│     ▼                                                                │
│  2. Traefik (ECS) → TLS 终止 → Tailscale → NAS Gateway:8000          │
│     │                                                                │
│     ▼                                                                │
│  3. VersioningMiddleware → 版本校验                                   │
│     │                                                                │
│     ▼                                                                │
│  4. RateLimitMiddleware → Redis 滑动窗口限流 (100 req/min)            │
│     │  ├─ 超限 → 429 Too Many Requests                               │
│     │  └─ Redis 不可用 → 内存降级限流                                 │
│     ▼                                                                │
│  5. AuthMiddleware → JWT/API Key 认证                                │
│     │  ├─ 免认证路径 → 跳过                                          │
│     │  ├─ X-API-Key 头 → SHA256 哈希匹配                             │
│     │  ├─ Bearer Token → JWT 解密验证                                 │
│     │  └─ 失败 → 401/403                                             │
│     ▼                                                                │
│  6. CORSMiddleware → 跨域策略检查                                     │
│     │                                                                │
│     ▼                                                                │
│  7. Pydantic Schema Validation → 请求体校验                          │
│     │  ├─ 字段缺失/类型错误 → 422 Unprocessable Entity                │
│     │  └─ messages 为空 → 422                                        │
│     ▼                                                                │
│  8. ContentFilter → 敏感词/PII 检测                                   │
│     │  ├─ 命中敏感词 → 内容脱敏/拦截                                  │
│     │  └─ 通过 → 继续                                                │
│     ▼                                                                │
│  9. Backend Selection → 模型路由                                      │
│     │  ├─ glm-* / zhipu:* → zhipu 服务                               │
│     │  ├─ deepseek-* → deepseek 服务                                 │
│     │  ├─ gpt-* / openai:* → openai 服务                             │
│     │  └─ 其他 → ollama 本地推理                                      │
│     ▼                                                                │
│  10. Cache Lookup → Redis LLM 缓存                                   │
│      │  ├─ 命中 → 直接返回缓存结果                                   │
│      │  └─ 未命中 → 继续推理                                         │
│      ▼                                                                │
│  11. Concurrency Limiter → 并发控制                                   │
│      │                                                                │
│      ▼                                                                │
│  12. LLM Inference → 后端推理                                        │
│      │  ├─ 成功 → 写入缓存 + 记录用量                                │
│      │  └─ 失败 → ErrorHandler 重试 (网络3次/API 2次/超时2次)          │
│      ▼                                                                │
│  13. Response → 格式化返回                                           │
│      ├─ stream=false → JSON 完整响应                                 │
│      └─ stream=true  → SSE 流式响应                                  │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 缓存策略

| 维度 | 策略 |
| ------ | ------ |
| 缓存键 | `llm_cache:` + SHA256(request_payload) |
| 存储 | Redis (String 类型，JSON 序列化) |
| 失效 | 按 model_name 主动失效 或 清空全部 |
| 命中率 | 通过 `/v1/cache/stats` 实时查看 |
| 降级 | Redis 不可用时跳过缓存，不阻塞请求 |

### 5.3 限流策略

| 维度 | 策略 |
| ------ | ------ |
| 算法 | Redis 有序集合滑动窗口 (Lua 原子操作) |
| 默认配额 | 100 请求 / 60 秒 |
| 突发 | burst=10 允许短时超量 |
| 降级 | Redis 不可用 → 内存单节点限流 |
| 响应 | 429 + `Retry-After` 头 |

---

## 六、安全策略

### 6.1 认证机制

| 机制 | 实现 | 说明 |
| ------ | ------ | ------ |
| API Key | `X-API-Key` 头，SHA256 哈希比对 | 生产推荐方式，从 `.env` 的 `API_KEYS` 逗号分隔加载 |
| JWT | `Authorization: Bearer` 头，HS256 签发 | 24 小时过期，支持 `user_id` 声明 |
| 免认证路径 | `SKIP_AUTH_PATHS` 集合 | 硬编码白名单：`/v1/ping` `/health` `/healthz` `/metrics` `/docs` 等 |

### 6.2 内容安全

- **敏感词过滤**: 中英文敏感词库 + 正则模式（手机号/身份证/银行卡/API Key 格式检测）
- **PII 检测**: BASE64/SHA 编码密钥格式识别
- **输入校验**: Pydantic 严格校验（字段长度、范围、枚举值）

### 6.3 网络安全

| 层级 | 策略 |
| ------ | ------ |
| 传输层 | TLS 1.3 (Let's Encrypt) + Tailscale VPN 加密内网通信 |
| 应用层 | CORS 白名单 (`allowed_origins`) |
| 数据层 | PostgreSQL 密码认证 + Redis `requirepass` |
| 容器层 | 非 root 用户运行 (appuser:1000) + 多阶段构建最小镜像 |
| 依赖安全 | `uv pip compile --generate-hashes` 锁定 52 个安全版本 |

### 6.4 关键配置保护

启动时强制校验 4 项关键配置（`auth_enabled=true` 时缺失则拒绝启动）:

| 配置项 | 校验规则 |
| -------- | --------- |
| `JWT_SECRET_KEY` | 非空且不等于 `change_me_in_production` |
| `API_KEYS` | 非空 |
| `POSTGRES_PASSWORD` | 非空且不等于 `change_me_in_production` |
| `REDIS_PASSWORD` | 非空且不等于 `change_me_in_production` |

---

## 七、错误处理机制

### 7.1 错误分类体系

| 错误类型 | 异常类 | HTTP 状态码 | 重试策略 |
| --------- | -------- | ------------ | --------- |
| 网络错误 | `NetworkError` | 502/503 | 最多 3 次，间隔 1s |
| API 错误 | `APIError` | 4xx/5xx | 最多 2 次，间隔 2s |
| 超时错误 | `TimeoutError` | 504 | 最多 2 次，间隔 1s |
| 校验错误 | `ValidationError` | 422 | 不重试 |

### 7.2 标准错误响应格式

```json
{
  "error": "YYC3_NETWORK_ERROR",
  "message": "Connection refused to upstream model service",
  "status_code": 502,
  "details": {
    "model": "glm-4-flash",
    "backend": "zhipu",
    "retry_count": 3
  }
}
```

### 7.3 HTTP 状态码语义

| 状态码 | 场景 |
| -------- | ------ |
| 200 | 成功（同步响应/查询类） |
| 422 | 请求体校验失败 (Pydantic Validation) |
| 401 | 未认证 (缺少/无效 API Key 或 JWT) |
| 403 | 认证通过但无权限 |
| 404 | 模型不存在 / 资源未找到 |
| 429 | 限流 (Too Many Requests) |
| 500 | 内部错误 |
| 502 | 上游模型服务不可达 |
| 504 | 上游模型服务超时 |

---

## 八、性能指标与监控

### 8.1 Prometheus 指标

通过 `/metrics` 端点暴露 (prometheus_fastapi_instrumentator):

- `http_requests_total` — 总请求数 (按 method/path/status)
- `http_request_duration_seconds` — 请求延迟直方图
- `http_requests_in_progress` — 当前并发请求数

### 8.2 业务指标 (通过 `/health` 端点)

| 指标 | 来源 | 说明 |
| ------ | ------ | ------ |
| `active_requests` | metrics_manager | 当前活跃请求数 |
| `total_requests` | metrics_manager | 累计总请求数 |
| `cache_hit_rate` | metrics_manager | LLM 缓存命中率 |
| CPU / Memory / Disk | psutil | 网关宿主机系统资源 |

### 8.3 路由器指标 (通过 `/v1/router/stats`)

| 指标 | 说明 |
| ------ | ------ |
| `ewma_latency` | EWMA 平滑延迟 (ms) |
| `ewma_error_rate` | EWMA 平滑错误率 |
| `dynamic_weight` | 动态权重 (自适应路由) |
| `success_rate` | 成功率 |

### 8.4 性能基线 (实测)

| 指标 | 值 | 说明 |
| ------ | ----- | ------ |
| NAS Gateway 启动 | < 30s | Docker Compose up -d (含 PG/Redis 健康检查) |
| /healthz 响应 | < 5ms | 纯内存操作 |
| /health 响应 | < 500ms | 含外部服务并发探查 |
| 公网端到端延迟 | ~1.3s | 本机 → api.0379.world → NAS Gateway → 返回 |
| Gateway 资源占用 | CPU 2.4% / RAM 10.8% | NAS 空载基线 |

---

## 九、部署指南

### 9.1 首次部署

```bash
# 1. 在 NAS (YYC3-45) 创建部署目录
ssh yyc3-45
mkdir -p /Volume2/yyc3-33

# 2. 上传部署文件
#    - docker-compose.nas.yml → /Volume2/yyc3-33/docker-compose.yml
#    - .env (从 .env.example 复制并填写)
#    - scripts/deploy-nas-gateway.sh

# 3. 配置环境变量
scp .env yyc3-45:/Volume2/yyc3-33/.env

# 4. 执行部署脚本
bash scripts/deploy-nas-gateway.sh

# 5. 验证
curl http://100.65.172.88:8000/healthz
```

### 9.2 更新部署

```bash
# 1. 更新代码
ssh yyc3-45 "cd /Volume2/yyc3-33 && git pull"

# 2. 更新 .env (如有配置变更)
#    注意: .env 变更必须 rebuild 才能生效

# 3. 重建并启动
ssh yyc3-45 "cd /Volume2/yyc3-33 && docker compose up -d --build gateway"

# 4. 验证健康
curl http://100.65.172.88:8000/health
```

### 9.3 环境变量配置

**必填项**:

| 变量 | 说明 | 示例 |
| ------ | ------ | ------ |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | 强密码 |
| `REDIS_PASSWORD` | Redis 密码 | 强密码 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 随机 32+ 字符 |
| `API_KEYS` | API Key 列表 (逗号分隔) | `sk-key-1,sk-key-2` |

**可选项**:

| 变量 | 说明 | 默认值 |
| ------ | ------ | -------- |
| `ZHIPU_API_KEY` | 智谱 API Key | 空 (不配置则 GLM 不可用) |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 空 |
| `OPENAI_API_KEY` | OpenAI API Key | 空 |
| `DB_HOST` | PostgreSQL 主机 | `postgres` (容器网络) |
| `DB_PORT` | PostgreSQL 端口 | `5432` |
| `DB_NAME` | 数据库名 | `yyc3_gpt` |
| `REDIS_HOST` | Redis 主机 | `redis` (容器网络) |
| `API_HOST` | 监听地址 | `0.0.0.0` |
| `API_PORT` | 监听端口 | `8000` |
| `ALLOWED_ORIGINS` | CORS 白名单 | `https://api.0379.world` |
| `AUTH_ENABLED` | 是否启用认证 | `true` |
| `JWT_EXPIRATION_HOURS` | JWT 过期时间 | `24` |

### 9.4-bis 部署实况（v1.1）：GitOps 自动部署已取代手工流程

> 2026-09-02 起生效：`git push main` → CI 五段验证 → **Mac 部署桥**（~/yyc3-deploy/watch.sh，每 2 分钟对比 NAS HEAD）→ `git push ssh://YYC3@100.65.172.88:9557/Volume2/yyc3-33` → NAS `rebuild-gateway.sh` 重建+健康检查 → 公网终验。本节 9.1-9.3 的手工命令保留为**应急通道**。
> 运维红线：① NAS sshd 有防暴力惩罚机制（高频连接会被间歇拒认，自动化连接须 ≥60s 间隔）；② 旗舰 TP=2 启停按《双机推理部署指南》§19（head 先起 worker 后起；`/tmp` 会被清理，启动脚本已锚定 `/home/yyc3/dsv4_*.sh`）；③ NAS→GitHub 直连不稳定，部署一律走 Mac 桥。

### 9.4 Docker 镜像构建

```
多阶段构建:
  base (python:3.11-slim) → builder (安装依赖) → production (复制代码 + 非 root 用户)

关键点:
  - COPY core/api/ → /app/app/ (应用代码映射)
  - 非 root 用户 appuser:1000 运行
  - 健康检查: python -c urllib.request.urlopen('http://localhost:8000/docs')
```

---

## 十、维护与运维手册

### 10.1 日常巡检清单

```bash
# 1. 检查 Gateway 容器状态
ssh yyc3-45 "docker ps --filter name=0379-world"

# 2. 检查 Gateway 健康 (轻量)
curl -s http://100.65.172.88:8000/healthz | python3 -m json.tool

# 3. 检查完整健康 (含依赖)
curl -s http://100.65.172.88:8000/health | python3 -m json.tool

# 4. 检查公网可达性
curl -s -o /dev/null -w "%{http_code}" https://api.0379.world/healthz

# 5. 检查 ECS Traefik 状态
ssh yyc3-33 "docker ps --filter name=traefik"

# 6. 查看 Gateway 日志
ssh yyc3-45 "docker logs --tail 100 0379-world-gateway-1"
```

### 10.2 故障排查

| 症状 | 可能原因 | 排查步骤 |
| ------ | --------- | --------- |
| 公网 502 | ECS→NAS 链路中断 | `ssh yyc3-33 "curl http://100.65.172.88:8000/healthz"` → 检查 Tailscale 连接 |
| 401 认证失败 | API Key 错误 / .env 未同步 | `ssh yyc3-45 "docker exec 0379-world-gateway-1 printenv API_KEYS"` → 对比 .env |
| 模型不可用 | Ollama 未启动 / 云端 Key 过期 | `/health` 检查 ollama/zhipu 状态 → 检查 API Key 有效性 |
| 响应超时 | 上游模型慢 / 网络延迟 | `/v1/router/stats` 查看 EWMA 延迟 → 考虑切换后端 |
| Redis 限流失效 | Redis 服务异常 | `docker logs 0379-world-redis-1` → 确认降级到内存限流 |
| 容器启动失败 | 关键配置缺失 | `docker logs 0379-world-gateway-1` → 检查 validate_critical_config 报错 |

### 10.3 备份策略

| 数据 | 位置 | 备份方式 |
| ------ | ------ | --------- |
| PostgreSQL | `/Volume2/yyc3-33/postgres/pgdata` | `core/scripts/yyc3_db_backup.sh` |
| Redis | `/Volume2/yyc3-33/redis/` | RDB + AOF (Redis 7 默认) |
| 模型文件 | `/Volume1/yyc3_hd/data` + `/Volume2/docker/models` | RAID6/RAID1 硬件冗余 |
| 部署配置 | `/Volume2/yyc3-33/docker-compose.yml` + `.env` | Git 版本控制 |

### 10.4 扩缩容指南

**水平扩展**:

- Gateway 无状态，可通过 `docker compose up --scale gateway=N` 多实例 + Traefik 负载均衡
- Redis 共享限流状态，多实例限流一致

**垂直扩展**:

- 增加 NAS 内存 (当前 32GB) → 提升 Ollama 本地推理并发
- DGX GPU 接入更多模型 → 减轻云端 API 依赖

---

## 附录 A: 环境变量完整清单

参见 [`.env.example`](../core/config/.env.example) 和 [`.env.example`](../.env.example)。

## 附录 B: 快速命令参考

```bash
# ── 健康检查 ──
curl http://100.65.172.88:8000/healthz          # 轻量探活
curl http://100.65.172.88:8000/health             # 完整健康
curl https://api.0379.world/healthz               # 公网探活

# ── 模型操作 ──
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/models                    # 模型列表
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/model/type?model=glm-4-flash  # 模型类型

# ── Chat 请求 ──
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"你好"}]}'

# ── 流式 Chat ──
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"你好"}],"stream":true}'

# ── 缓存管理 ──
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/cache/stats   # 缓存统计
curl -X DELETE -H "X-API-Key: $KEY" https://api.0379.world/v1/cache/all  # 清空缓存

# ── 部署操作 ──
ssh yyc3-45 "cd /Volume2/yyc3-33 && docker compose up -d --build gateway"  # 重建部署
ssh yyc3-45 "docker logs --tail 50 -f 0379-world-gateway-1"                     # 实时日志
```

---

## 十一、实况落地行动清单（v1.1 · 2026-09-03，衔接全链路）

> 排序原则：每一项都让"公网用户 → DGX 旗舰"近一步；前两项是阻断项。

| # | 行动 | 现状→目标 | 依赖 | 验收 |
|---|------|-----------|------|------|
| **1** | **A 线 P0：网关上游配置化 + 测试地基** | ✅ **完成（09-03 f6dd282）**：OPENAI_COMPATIBLE_UPSTREAMS env 池 + 云基址外部化 + 死代码清零 + pytest 零网络（15 用例） | 无 | mock 上游进 `/v1/models` ✓；CI test 绿 ✓ |
| **2** | **A 线 P1：智能路由接线 + 熔断降级** | ✅ **完成（09-03）并已对公网**：分层优先级路由 + 熔断(3败摘30s半开) + 降级链 + X-YYC3-Upstream/Degraded 头；**api.0379.world → Traefik(Tailscale) → NAS 网关 → N1:8001 旗舰全链路验收通过（对话/SSE/响应头）** | #1 ✓ | 公网 chat 落 deepseek-v4-flash ✓（`x-yyc3-upstream: flagship-dsv4`）|
| 3 | RAG 三件套容器化恢复 | ✅ **完成（09-03）**：0.6B 版三容器上线（**N1 部署铁律**：N2 与 ray-worker 同节点必崩）；公网 `/v1/embeddings`(1024维) `/v1/rerank`(judge 打分排序) 全绿；8B 升级位待旗舰 KV 腾挪 | 完成 | `/v1/embeddings` 公网全链路通 ✓ |
| 4 | 4 缺失端点补齐（A 线 P2） | ✅ **完成（09-03）**：`/v1/embeddings`(透传) `/v1/rerank`(Cohere⇆Jina 转换) `/v1/audio/transcriptions` `/v1/ocr`(multipart 透传)，capability 路由复用上游池+熔断降级+X头；9 测试例 | #1 ✓ | 7 端点契约齐 ✓（asr/ocr 真机待上游服务） |
| 5 | Agents 容器化上线 | 代码模型无关（VLLM_ENDPOINT）→ compose 起 8 Agent+治理，env 指向 :8001 | #2 | :25600-07/:25700 健康 |
| 6 | ~~ECS 网关副本双活~~ → **实况修正**：ECS=Traefik 边缘反代（api.0379.world→NAS:8000），NAS 网关即唯一计算实例且已服务公网；可选增强=ECS 本地副本（需连 NAS PG/Redis，性价比待评估） | 单 NAS 网关已是公网主实例 ✓ | Traefik 双上游（可选） |
| 7 | 新模型注册 | GLM-5.3-Flash（量化后 TP=2 升级位）/ Qwen3.8-Flash-Next（轻旗舰降级位）/ MiniMax-H3-NF4（**新增视频生成端点** `/v1/videos` 候选） | 下载完成+量化 | 各自冒烟 |
| 8 | 观测真实化 | ✅ **API 侧完成（09-03）**：models/stats 真实 EWMA、models/errors 真数据、router/stats 并池快照、ws/monitor 去假数据；Grafana 面板字段对齐待做 | #2 ✓ | 面板出真数（API ✓/Grafana 待） |

**旗舰运维速查（衔接 §9.4-bis）**：
```bash
# 启动（顺序敏感）
ssh yyc3@100.65.64.49 'docker start dsv4-head'   # 等 ~80s
ssh yyc3@100.76.167.103 'docker start dsv4-worker'
# 验收
curl http://100.65.64.49:8001/v1/models          # → deepseek-v4-flash
# 停机（干净关停）
ssh yyc3@100.65.64.49 'docker stop dsv4-head' && ssh yyc3@100.76.167.103 'docker stop dsv4-worker'
# 注意：容器 /tmp 不持久——启动脚本已锚定 ~/dsv4_head.sh(脚本在 /home/yyc3)，误删脚本会导致 docker start 挂载失败（2026-09-03 实测踩坑）
# ⚠️ 镜像铁律（09-03 事故）：vllm/vllm-openai:v0.26.0(latest) 在 GB10/sm_121 上 FP8 kernel 输出乱码
#    —— 必须 docker.m.daocloud.io/vllm/vllm-openai:nightly（digest 31a59e77…），排除链见 deploy/dgx/tp2-ray-实测验证模式.md
```

> **文档维护**: YanYuCloudCube Team <admin@0379.email>
> **最后验证**: 2026-09-03（v1.3：**公网 chat/embeddings/rerank 三能力全绿**（A线P0/P1/P2+RAG上线+乱码修复）· 24 测试绿 · CI 五段绿+公网冒烟+NAS SMOKE_PASS）
> **下次审核建议**: 2026-09-30 或 A 线 P1 合入时

**YanYuCloudCube** - 言启象限 | 语枢未来
**YYC3-0379-World** - v2.0.0 Production API Gateway
