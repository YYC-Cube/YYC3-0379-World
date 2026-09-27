---
file: 02-Registry目标架构.md
description: Model Registry 目标架构规范 - 注册中心 DB Schema / API / 双通道发现 / 演进路径（规划稿）
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-09-27
updated: 2026-09-27
status: draft
tags: [spec],[registry],[target-architecture],[planning]
category: spec
---

# Model Registry 目标架构规范（📋 规划稿）

> **状态警示**：本文档为**未实现的目标架构**（原 YYC3-MRS-2026-v1.0.0 收敛）。所有 `/registry/v1/*` 端点、契约端点、心跳机制均未落地。现状接入通道见 [01](01-接入现状规范-v2.3.md)。

## 1. 设计目标与原则

**五项目标**：标准化接入契约 / 动态注册与发现 / 零停机热切换（→[03](03-热切换与版本管理.md)）/ 自动配置同步 / 版本控制与回滚。

**八条原则**：

1. 契约优先：所有模型必须自证能力，网关不猜测。
2. 幂等注册：同一模型重复注册 = 覆盖，不产生副本。
3. 声明式收敛：模型声明期望状态，网关自动收敛。
4. 不可变版本：Manifest 一旦发布永不修改，新版本 = 新 Manifest。
5. 渐进式切换：上线必经 canary → 扩量 → 全量。
6. 秒级回滚：切换失败 ≤30s 回滚到上一稳定版本。
7. 全程可观测：注册/切换/回滚每步有指标、日志、追踪。
8. 家族化治理：8 位家人各守其域（见原归档件 RBAC 矩阵）。

**兼容承诺**：100% 兼容现有 `OPENAI_COMPATIBLE_UPSTREAMS`（env 作为 fallback 双通道共存）；现有生产服务无需改造即可纳入。

## 2. 模型服务标准接口契约（12 端点）

任何模型服务接入 Registry 前必须实现：

| # | 端点 | 方法 | 必需 | 说明 |
| :-: | --- | :-: | :-: | --- |
| 1 | `/v1/models` | GET | ✅ | OpenAI 兼容，列出模型 |
| 2 | `/v1/chat/completions` | POST | ✅（chat） | OpenAI 兼容（含 SSE） |
| 3 | `/v1/embeddings` | POST | 🔧 按需 | 文本嵌入 |
| 4 | `/v1/rerank` | POST | 🔧 按需 | 重排序 |
| 5 | `/v1/audio/transcriptions` | POST | 🔧 按需 | 语音转写 |
| 6 | `/v1/ocr` | POST | 🔧 按需 | YYC³ 扩展 |
| 7 | `/health` | GET | ✅ | 完整健康 |
| 8 | `/healthz` | GET | ✅ | 轻量探活（<100ms） |
| 9 | `/v1/model/metadata` | GET | ✅ | **YYC³ 新增**：模型元数据 |
| 10 | `/v1/model/capabilities` | GET | ✅ | **YYC³ 新增**：能力声明 |
| 11 | `/v1/model/manifest` | GET | ✅ | **YYC³ 新增**：版本清单 |
| 12 | `/metrics` | GET | ✅ | Prometheus 指标 |

### 2.1 元数据 Schema（端点 9 响应）

```typescript
interface ModelMetadata {
  // 必填
  model_id: string;              // 全局唯一，如 "deepseek-v4-flash"
  display_name: string;
  version: string;               // 语义化版本
  backend: "vllm" | "nim" | "ollama" | "openai" | "zhipu" | "deepseek" | "upstream";
  capabilities: Capability[];    // chat/completion/embedding/rerank/vision/tool_use/json_mode/asr/ocr/video/image_gen
  enabled: boolean;
  // 运行时
  max_tokens: number;
  context_window: number;
  temperature_default: number;
  top_p_default: number;
  // 性能声明（网关实测校准）
  cost_per_1k_tokens: number;
  avg_latency_ms: number;
  throughput_tps: number;
  max_concurrency: number;
  // 资源
  node_id: string;               // yyc3-101 / yyc3-102（统一命名，见 README 决策表）
  node_role: "primary" | "secondary" | "fallback";
  weights_path: string;
  weights_size_gb: number;
  quantization?: string;         // fp16/bf16/fp8/nvfp4/awq/gptq/q4_k_m
  // 元信息
  registered_at: string;
  updated_at: string;
  manifest_hash: string;
  owner: string;
  tags: string[];
}
```

> **元数据载体统一决策**：以端点契约为主（契约优先）；原 A 规范的 `model-meta.json` 文件形态仅作注册 Agent 的本地缓存源，不作为网关读取通道。

### 2.2 Manifest Schema（端点 11 响应，不可变）

```typescript
interface ModelManifest {
  manifest_version: "1.0";
  model_id: string;
  version: string;
  weights: { path: string; size_gb: number; file_count: number; sha256: string;
             quantization: string; format: "safetensors" | "gguf" | "bin" | "pytorch" };
  runtime: { engine: string; engine_version: string; tensor_parallel: number;
             pipeline_parallel: number; dtype: string; kv_cache_dtype?: string;
             max_model_len: number; gpu_memory_utilization: number };
  dependencies: { cuda: string; driver: string; python: string; system_deps: string[] };
  published_at: string; published_by: string; build_pipeline: string;
  git_commit?: string; changelog: string;
  manifest_hash: string;         // 本清单 sha256（不含此字段自身）
}
```

### 2.3 能力声明（端点 10 响应）

按能力声明端点、支持参数、流式、长度限制、语言、特殊功能——网关按能力路由（如 `/v1/embeddings` → 只找 embedding 能力服务）。完整 TypeScript Schema 见归档件 §3.3。

### 2.4 合规检查清单

```
□ /v1/models 返回 OpenAI 兼容格式
□ /v1/chat/completions 支持同步 + SSE
□ /healthz < 100ms
□ /health 返回完整健康
□ /v1/model/metadata 必填字段完整
□ /v1/model/capabilities 声明全部已实现能力
□ /v1/model/manifest 含权重哈希
□ /metrics 暴露必需指标
□ SSE 首 chunk 含 _yyc3_upstream / _yyc3_request_id
□ 响应头含 X-YYC3-Upstream / X-YYC3-Request-Id
```

## 3. Registry 架构

```
                ┌─────────────────────────────────────┐
                │   Model Registry（🧠 元启·天枢主控） │
                │  Metadata DB(PG) │ Manifest Store   │
                │  Event Bus(Redis)│ Versioning       │
                └──────────┬──────────────────────────┘
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
    网关:8000 自动发现   上游池(vLLM/NIM)  运维工具(CLI/UI)
```

### 3.1 PostgreSQL Schema（规划迁移 005）

五张表（完整 DDL 见归档件 §4.2，此处摘要）：

| 表 | 用途 | 关键点 |
| --- | --- | --- |
| `model_registry` | 模型主表（当前状态） | capabilities JSONB + GIN 索引；health_status/breaker_state CHECK 约束；**与现有 db.py 6 字段表合并扩展** |
| `model_versions` | 版本历史（不可变） | UNIQUE(model_id, version)；action: register/update/rollback/deprecate |
| `model_heartbeats` | 心跳 TTL 检测 | last_beat_at + consecutive_miss |
| `model_events` | 事件流（网关 Watch） | event_type: registered/updated/deprecated/deregistered/breaker_* |
| `model_audit_log` | 审计（保留 365 天） | before/after_state JSONB |

> 落地注意：现有 `model_registry` 表已有生产数据（NAS 网关栈在用），扩展列走增量迁移，禁止 DROP 重建。

### 3.2 Registry API（12 模型端点）

```
GET    /registry/v1/models                      列出（只读）
GET    /registry/v1/models/{id}                 详情（只读）
POST   /registry/v1/models                      注册（🎯/🧠）
PATCH  /registry/v1/models/{id}                 更新元数据（🎯/🧠）
DELETE /registry/v1/models/{id}                 注销（🎯/🧠）
GET    /registry/v1/models/{id}/versions        版本历史（只读）
POST   /registry/v1/models/{id}/rollback        回滚（🧠/📚）
POST   /registry/v1/models/{id}/heartbeat       心跳上报（模型服务）
GET    /registry/v1/models/{id}/health          实时健康（只读）
GET    /registry/v1/events                      事件流 SSE（只读）
GET    /registry/v1/manifests/{hash}            获取 Manifest（只读）
GET    /registry/v1/audit                       审计日志（只读）
```

> 认证：模型服务心跳用 `X-YYC3-Registry-Token`；管理端点用 `X-API-Key`（admin 面，对齐现有 AuthMiddleware ADMIN_API_KEYS）。

## 4. 动态注册与发现

### 4.1 演进三阶段

```
Phase A（当前 → 3 个月）：双通道
  REGISTRY_ENABLED=true + REGISTRY_FALLBACK_TO_ENV=true
  Registry 优先，env fallback；所有新模型只走 Registry

Phase B（3 → 6 个月）：Registry 主导
  env 仅保留 1-2 个紧急 fallback；监控面板标注 env 通道使用率

Phase C（6 个月后）：纯 Registry 唯一真源，移除 env 通道
```

### 4.2 双通道发现协议（Pull + Push）

- **Push（实时）**：网关 SSE 长连接订阅 `GET /registry/v1/events`，收到事件增量更新上游池（无需重启）；断连自动重连（最大退避 60s）。
- **Pull（兜底）**：每 5 分钟 `GET /registry/v1/models` 全量对账。
- **合并策略**：Push 优先，Pull 兜底。

### 4.3 网关启动流程

```
1. 读配置（REGISTRY_ENABLED / FALLBACK_TO_ENV）
2. 连 Registry：成功 → 拉全量 + 订阅事件
              失败 → fallback env；无 fallback 则 fail-fast
3. 构建上游池：按 capabilities 分组 → 按 node_role 分层 → 按 priority+weight 定权重
4. 健康探测：每 30s 调上游 /healthz；失败 3 次摘除
5. 事件监听：增量更新路由表
```

### 4.4 心跳与 TTL（统一口径）

> 整合决策：采用三级 TTL 阶梯（弃原 A 规范 5s/30s 单级——现状无心跳，本节全为规划）。

```
心跳上报周期：30s（模型服务 → POST /registry/v1/models/{id}/heartbeat）
连续 3 次丢失（90s）  → Registry 标记 degraded
连续 6 次丢失（180s） → Registry 标记 unreachable
连续 10 次丢失（300s）→ 自动从上游池摘除
恢复心跳 → 自动重新纳入（先半开探测 30s）
```

### 4.5 配置同步三通道

| 通道 | 方向 | 延迟 | 可靠性 |
| --- | --- | --- | --- |
| Webhook（Registry → 网关） | 推 | ≤1s | 中（指数退避重试 5 次） |
| SSE 事件流（网关 ← Registry） | 订 | ≤5s | 高（自动重连） |
| Pull 全量对账（网关 → Registry） | 拉 | ≤5min | 最高（无状态） |

**冲突解决**：Registry vs env → Registry 优先；熔断状态 → **网关权威**；性能指标 → Prometheus 实测 > 声明。

## 5. 落地路线（建议）

| 阶段 | 交付 | 依赖 |
| --- | --- | --- |
| 短期（1 个月） | Registry 后端（§3 Schema+API）/ 网关集成双通道 / 现有 4 生产服务纳入 | 迁移 005；model_register_agent.py |
| 中期（3 个月） | 热切换（→[03](03-热切换与版本管理.md)）/ 自动同步 / 监控告警（→[05](05-监控告警与Runbook.md)） | Registry 稳定运行 |
| 长期（6 个月） | Agent 注册演进层（→[04](04-Agent注册规范.md) §4）/ 审计合规 / env 通道退役 | 全链路回归 |

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0.0 | 2026-09-27 | 自原 MRS-2026 §3-§7 收敛为目标架构稿；心跳统一三级 TTL；元数据载体统一端点契约；Agent 注册移至 04 |
