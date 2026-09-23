---
file: Token调用平台前端-全维度设计与落地文档.md
description: v4.0 闭环对齐版——逐页标注后端对齐类型（直接对接/轻量扩展/Phase 2 分期）、真实 Schema 字段级契约（2026-09-17 OpenAPI 审计）、完整可执行后端补全 Backlog（BL-01~BL-08）
author: AI Tutor
version: v4.0.0
created: 2026-09-03
updated: 2026-09-17
status: active
tags: [frontend],[figma],[design],[api-alignment],[nextjs16],[roadmap]
category: guide
supersedes:
  - Token调用平台完整前端设计提示词.md（V1）
  - Token调用平台完整前端设计提示词-V2落地版.md（V2）
  - 落地衔接指导-Token调用平台前端.md
  - 设计理念/Token调用平台前端-全维度设计与落地文档.md（v3.0，已合并进本文档）
---

# Token调用平台前端 · 全维度设计与落地文档 · **闭环对齐版**

> **文档定位**：本文档为 v4.0 闭环对齐版，取代 v3.0。每个 Figma 页面、组件、数据流均标注精确的后端对齐类型：
>
> - ✅ **直接对接**：使用现有端点，零后端改动
> - 🔧 **需轻量扩展**：后端需补字段/新端点（Phase 1，小改动）
> - 📋 **Phase 2 分期**：规划占位，不设计真实 UI
>
> **事实基础**：2026-09-17 对 `https://api.0379.world/openapi.json` 完整审计，52 端点、7 Schema、数据库模型与代码一致验证。

---

## 第一部分 · 后端实况清单（v4.0 审计快照）

### 1.1 端点总览（52 端点，2026-09-17 OpenAPI 实况）

| #     | 类别　　 | 端点　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 认证　 | 当前返回 Schema　　　　　　　　　　　| 对齐类型　　　|
| -------| ----------| -------------------------------------------------------------------------------| :------:| --------------------------------------| ---------------|
| 1     | 聊天　　 | `POST /v1/chat/completions`　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | OpenAI ChatCompletion + SSE　　　　　| ✅ 直接对接　　|
| 2     | 聊天　　 | `WS /ws/chat`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | WebSocket 流式　　　　　　　　　　　 | ✅ 直接对接　　|
| 3     | 聊天　　 | `WS /ws/monitor`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | WebSocket 监控　　　　　　　　　　　 | ✅ 直接对接　　|
| 4     | 模型　　 | `GET /v1/models`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | `ModelConfig[]`（6 种 backend enum） | ✅ 直接对接　　|
| 5     | 模型　　 | `GET /v1/models/stats`　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | `ModelStat[]`（5 字段）　　　　　　　| ✅ 直接对接　　|
| 6     | 模型　　 | `GET /v1/models/errors`　　　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | `ErrorRecord[]`（4 种 error_type）　 | ✅ 直接对接　　|
| 7     | 模型　　 | `GET /v1/models/summary`　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | `UsageSummary`（cost_usd 恒 0.0）　　| 🔧 需轻量扩展 |
| 8     | 模型　　 | `GET /v1/model/type`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | 模型类型查询　　　　　　　　　　　　 | ✅ 直接对接　　|
| 9     | 路由　　 | `GET /v1/router/stats`　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | 上游池快照（含熔断态）　　　　　　　 | ✅ 直接对接　　|
| 10    | 路由　　 | `GET /v1/router/health`　　　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | 上游池健康探测结果　　　　　　　　　 | ✅ 直接对接　　|
| 11    | 缓存　　 | `GET /v1/cache/stats`　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | 缓存统计　　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 12    | 缓存　　 | `GET /v1/cache/info`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | 缓存详情　　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 13    | 缓存　　 | `POST /v1/cache/invalidate/{model}`　　　　　　　　　　　　　　　　　　　　　 | 需　　 | 失效结果　　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 14    | 缓存　　 | `DELETE /v1/cache/all`　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | 清空结果　　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 15    | 能力代理 | `POST /v1/embeddings`　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | EmbeddingResponse　　　　　　　　　　| ✅ 直接对接　　|
| 16    | 能力代理 | `POST /v1/rerank`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | RerankResponse　　　　　　　　　　　 | ✅ 直接对接　　|
| 17    | 能力代理 | `POST /v1/audio/transcriptions`　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | 代理（端点就绪）　　　　　　　　　　 | ✅ 直接对接　　|
| 18    | 能力代理 | `POST /v1/ocr`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | 代理（端点就绪）　　　　　　　　　　 | ✅ 直接对接　　|
| 19-23 | RAG　　　| `GET/POST/PATCH/DELETE /v1/knowledge-bases[/stats]`　　　　　　　　　　　　　 | 需　　 | KB CRUD + 统计　　　　　　　　　　　 | ✅ 直接对接　　|
| 24-27 | 文档　　 | `POST/GET/DELETE /v1/documents[/upload/{doc_id}/chunks/reprocess]`　　　　　　| 需　　 | 文档完整生命周期　　　　　　　　　　 | ✅ 直接对接　　|
| 28    | RAG　　　| `POST /v1/rag/search`　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | 需　　 | 语义检索　　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 29    | RAG　　　| `POST /v1/rag/ask`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | 知识库问答　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 30-43 | MCP　　　| 14 个端点（tools/execute/local/web/github/docker/database/filesystem/search） | 需　　 | MCP 工具集　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 44    | 健康　　 | `GET /health`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | **免** | 完整健康（含 system/cache/services） | ✅ 直接对接　　|
| 45    | 健康　　 | `GET /healthz`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| **免** | 轻量探活　　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 46    | 健康　　 | `GET /v1/ping`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| **免** | `{"status":"ok"}`　　　　　　　　　　| ✅ 直接对接　　|
| 47    | 版本　　 | `GET /v1/versions`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | 版本信息　　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 48    | 监控　　 | `GET /metrics`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 需　　 | Prometheus　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 49    | 监控　　 | `GET /docs`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | **免** | Swagger UI　　　　　　　　　　　　　 | ✅ 直接对接　　|
| 50    | 监控　　 | `GET /openapi.json`　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 | **免** | OpenAPI 规范　　　　　　　　　　　　 | ✅ 直接对接　　|
| --    | 缺失　　 | **`GET /v1/logs`**　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| --　　 | 不存在　　　　　　　　　　　　　　　 | 🔧 需新增　　 |
| --    | 缺失　　 | **`GET /v1/keys` CRUD**　　　　　　　　　　　　　　　　　　　　　　　　　　　 | --　　 | 不存在（.env 静态）　　　　　　　　　| 🔧 需新增　　 |
| --    | 缺失　　 | **`GET /v1/usage/timeline`**　　　　　　　　　　　　　　　　　　　　　　　　　| --　　 | 不存在　　　　　　　　　　　　　　　 | 🔧 需新增　　 |

### 1.2 关键 Schema 字段级实况（2026-09-17 审计）

#### ModelConfig（`GET /v1/models` 返回）

```typescript
// backend 枚举（6 种）
type Backend = "local" | "openai" | "zhipu" | "deepseek" | "ollama" | "upstream"

interface ModelConfig {
  id: string                    // 必填
  display_name: string          // 必填
  backend: Backend              // 必填
  version?: string | null
  enabled: boolean              // 默认 true
  max_tokens: number            // 默认 4096, 最大 128000
  temperature: number           // 默认 0.7, 范围 0-2
  top_p?: number | null
  cost_per_1k_tokens: number    // 默认 0.0（本地模型）
}
```

#### ModelStat（`GET /v1/models/stats` 返回）

```typescript
interface ModelStat {
  model_id: string              // 必填
  usage_count: number           // 默认 0
  avg_latency_ms: number        // 默认 0.0
  error_rate: number            // 默认 0.0, 范围 0-1
  total_tokens: number          // 默认 0
}
```

#### ErrorRecord（`GET /v1/models/errors` 返回）

```typescript
// 注意：error_type 枚举只有 4 种
// v3.0 文档的 "network/api/timeout/validation" 不完全准确
type ErrorType = "timeout" | "validation" | "quota" | "internal"

interface ErrorRecord {
  id: string                    // 必填
  timestamp?: string            // ISO datetime
  model_id: string              // 必填（v3.0 用 model，实际字段名 model_id）
  error_type: ErrorType         // 必填
  message: string               // 必填
  stack?: string | null
}
```

#### UsageSummary（`GET /v1/models/summary` 返回）

```typescript
interface UsageSummary {
  total_requests: number        // 默认 0
  total_tokens: number          // 默认 0
  cost_usd: number              // ⚠️ 恒为 0.0（硬编码）
}
```

#### HealthResponse（`GET /health` 返回，免认证）

```typescript
interface HealthResponse {
  status: string                // "healthy"
  timestamp: string             // ISO datetime
  version: string               // "2.0.0"（后端硬编码）
  uptime_seconds: number
  services: {
    ollama:   { status: "healthy" | "unreachable" | "configured" }
    zhipu:    { status: "healthy" | "unreachable" | "configured" }
    redis:    { status: "healthy" | "unreachable" | "configured" }
    postgresql: { status: "healthy" | "unreachable" | "configured" }
  }
  system: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
  }
  metrics: {
    active_requests: number
    total_requests: number
    cache_hit_rate: number      // ⚠️ 可能为 0.0（未记录缓存前）
  }
}
```

### 1.3 UsageLog 数据库实况（缺 6 字段）

```sql
-- 当前仅有 8 列 + 4 索引
usage_log: id, model, backend_type, prompt_tokens, completion_tokens,
           total_tokens, user_id(nullable), created_at

-- Phase 1 需补：
--   api_key_hash   VARCHAR(64)    -- 密钥归属（SHA-256）
--   cost_usd       NUMERIC(12,6)  -- 本次调用成本
--   latency_ms     INTEGER        -- 端到端延迟
--   request_id     VARCHAR(36)    -- 请求级追踪
--   status         VARCHAR(20)    -- success / error / degraded
--   error_code     VARCHAR(20)    -- 错误类型

-- 现有 4 索引：
-- idx_usage_log_model, idx_usage_log_created_at,
-- idx_usage_log_backend_type, idx_usage_log_model_created
```

### 1.4 SSE 协议实况（`core/api/api/chat.py` sse_wrapper）

```
传输: data: {OpenAI chunk}\n\n（UTF-8）
结束: data: [DONE]\n\n
首 chunk: 含 _yyc3_upstream 字段（服务的上游名称）
错误 chunk: data: {"error":{"message":"...","type":"stream_error"}}\n\n → [DONE]
Token 估算: len(content) // 4（粗略）

响应头:
  X-YYC3-Upstream: 实际服务的上游名
  X-YYC3-Degraded: 若走降级路径 → "true"

限流 429 响应: 含 retry_after 字段（秒）
```

### 1.5 错误统一结构（`core/api/errors/handler.py`）

```typescript
interface APIError {
  detail: {
    error: "network" | "api" | "timeout" | "validation"
    message: string
    context?: any
    status_code: number
  }
}
```

### 1.6 对齐比例（精确版）

```
43/52 端点 直接对接（82.7%）
 4/52 端点 需轻量扩展（7.7%）—— summary/cost、stats/latency、logs、keys CRUD
 0/52 端点 Phase 2 分期（0%）—— 路由规则 CRUD、SSO、多租户根本不存在
```

---

## 第二部分 · Figma 提示词（闭环对齐版）

### 角色

你是资深 Figma Agent + 产品设计系统架构师 + 前端架构师 + QA 自动化专家。你精通 Figma Variables / Modes / Auto Layout / Components / Variants / Prototype / Dev Mode / Code Connect。**你必须严格遵循本文档第一部分的真实 Schema**——禁止虚构任何不存在的字段或端点。

### 项目

为「YanYuCloudCube」设计已上线生产级 API 网关控制台的完整前端。单租户自用，面向开发者与运维。后端基座：`https://api.0379.world`（YYC³ v2.2.0，2026-09-17）。

### 默认参数

| 项 | 值 |
| ---- | ----- |
| 平台名 | YanYuCloudCube Console |
| 品牌主色 | #6C5CE7 |
| 辅助色 | 青#00D4FF（上游）/ 绿#22C55E（健康）/ 橙#F59E0B（降级/告警）/ 红#EF4444（熔断） |
| 风格 | 开发者工具、数据密集、暗色优先 |
| 字体 | Inter / 思源黑体；代码 JetBrains Mono |
| 断点 | 1440 主 / 1280 / 1024 / 768（侧边栏折叠） |
| 可访问性 | WCAG 2.2 AA，对比度 ≥4.5:1 |

### 数据源锚点规则

1. 所有页面/组件标注 **对齐类型徽章**（✅ 直接对接 / 🔧 轻量扩展 / 📋 Phase 2）
2. 所有数据字段必须来自第一部分 §1.1–§1.5 的真实 Schema
3. Phase 2 页面（登录/SSO/账单/路由CRUD/团队）仅出现在 `14_Roadmap_Phase2` 线框
4. `cost_usd` 字段目前恒为 0.0，前端显示「本地/免费」+ 占位卡标注 Phase 1

### 文件页面结构（18 页 · 全部闭环对齐）

```
00_Cover               ✅ 元信息页
01_Foundations         ✅ 设计系统变量
02_Components          ✅ 组件库（含 API 绑定徽章）
03_Connect             ✅ API Key 连接页（healthz 预检）
04_Dashboard           ✅ 多端点聚合
05_Model_Hub           ✅ /v1/models 直接对接
06_Playground          ✅ 核心页，SSE 全链路
07_Routing_Observe     ✅ 上游池熔断观测（只读）
08_Knowledge_RAG        ✅ KB + 文档 + 检索 + 问答
09_MCP_Tools           ✅ 14 端点工具调试台
10_Cache_Admin         ✅ 缓存管理（4 端点）
11_Monitor_Logs        ✅ 错误+系统健康（error_type 4 枚举）
12_Settings            ✅ 连接/偏好/版本
13_Docs_API            ✅ 内嵌 Swagger 外链
14_Roadmap_Phase2      📋 占位（Keys/账单/告警/团队 线框）
15_Prototype_Flows     ✅ 6 条闭环
16_QA_Self_Check       ✅ 自检矩阵
17_Handoff_DevMode     ✅ 含真实 API 契约
```

### 00_Cover

```
[对齐类型] ✅ 元信息页
内容：平台名 YanYuCloudCube Console
      Slogan「统一模型网关 · 可观测 · 可调试」
      后端基座：api.0379.world v2.2.0
      文档版本：v4.0 闭环对齐
      日期：2026-09-17
      设计系统/原型/QA/后端契约入口
```

### 01_Foundations · 设计系统变量

```
[对齐类型] ✅ 纯设计系统

颜色 Variables（必须完整）:
  color/bg/default, subtle, elevated, overlay
  color/text/primary, secondary, tertiary, inverse
  color/border/default, strong, focus
  color/brand/primary(#6C5CE7), hover, pressed
  color/status/success(#22C55E), warning(#F59E0B), danger(#EF4444), info(#00D4FF)
  color/backend/zhipu, deepseek, ollama, upstream   ← 4 色（ModelConfig.backend 有 6 种，但 local/openai 归 upstream）
  color/breaker/closed(#22C55E), open(#EF4444), half_open(#F59E0B)

间距: space/0=0, 1=4, 2=8, 3=12, 4=16, 5=20, 6=24, 8=32, 10=40, 12=48, 16=64
圆角: radius/sm=6, md=10, lg=16, xl=24, full=999
阴影: shadow/sm, md, lg, focus
字体: display/lg, md, h1, h2, h3, body/lg, body/md, body/sm, caption, code/md, code/sm
Modes: Light / Dark / Density-Comfortable / Density-Compact

专属规范:
  - SSE 流式光标动画（每秒 60 帧淡入淡出）
  - Token 千分位格式（1,234,567）
  - 延迟 ms 单位（≤100ms 绿色，100-500ms 橙色，≥500ms 红色）
  - error_type 颜色映射：timeout=橙 / validation=红 / quota=黄 / internal=灰
```

### 02_Components · 组件库（含 API 绑定徽章）

```
[对齐类型] ✅ 组件库（所有组件标注其数据源端点）

通用组件 + API 绑定:
  Button, IconButton, Input, Textarea, Select, Combobox, Checkbox, Radio,
  Switch, Slider, DatePicker, Tabs, Breadcrumb, Pagination, Tag, Badge,
  StatusDot, Tooltip, Popover, Dropdown, CommandMenu, Card, Table,
  DataGrid, FilterBar, ColumnSettings, EmptyState, Skeleton, Sidebar,
  TopBar, NavItem, UserMenu, SearchGlobal, Modal, Drawer, Sheet, Toast,
  Alert, ConfirmDialog, CodeBlock(curl/Python/Node Tab), CopyButton,
  KeyMask, JsonViewer, LogRow, Chart, Sparkline

控制台专属组件 + API 绑定:
  StatCard         ← summary.total_requests / summary.total_tokens / health.metrics.*
  ModelCard        ← /v1/models → ModelConfig
  BackendBadge     ← ModelConfig.backend（6 种枚举对应 4 色）
  UpstreamCard     ← /v1/router/stats
  BreakerBadge     ← 熔断三态 closed(绿)/open(红)/half_open(橙)
  LatencyBar       ← ModelStat.avg_latency_ms
  ErrorRateBadge   ← ModelStat.error_rate（0-1 小数 → 0%-100%）
  ErrorState       ← 四类错误 + 429 限流态
  SSEStreamViewer  ← SSE 流（data: {...}\n\n → [DONE]）
  TraceCard        ← 降级链路：upstream_name → degraded → served_by
  ModelSelector    ← /v1/models（按 backend 分组）
  BackendSelector  ← 手动枚举 6 种 backend
  KBSelector       ← /v1/knowledge-bases
  MCPToolPicker    ← /v1/mcp/tools
  ParamPanel       ← 各端点参数 Schema

变体矩阵:
  variant × size × state × tone
  = (primary/secondary/ghost/danger/link)
  × (xs/sm/md/lg)
  × (default/hover/active/focus/disabled/loading/error/success)
  × (neutral/brand/success/warning/danger/info)
```

### 03_Connect · API Key 连接页

```
[对齐类型] ✅ 直接对接（healthz 免认证 + X-API-Key 头）

布局：居中单屏
  - Logo + 平台名 YanYuCloudCube Console
  - 副标题「统一模型网关 · 可观测 · 可调试」
  - API Key 输入框（KeyMask 掩码态，输入时显示 ******** 格式）
  - 「连接」按钮（加载态→校验→进入 Dashboard / 失败态）
  - 「记住此设备」Switch（localStorage: yyc3_api_key）
  - 服务预检条（自动 GET /healthz → "连通 ✓" 或 "未连通"）

请求头契约:
  X-API-Key: {key}
  Authorization: Bearer {jwt}  ← 备选双通道

免认证端点（预检）:
  GET /health, /healthz, /v1/ping, /docs, /openapi.json

错误态（真实文案，来自 API response）:
  401 Unauthorized → "API Key 无效或已过期"
  403 Forbidden → "该 Key 无权限访问此端点"（目前无权限区分，Phase 1 补）
  Connection Refused → "网关服务不可达，请检查地址或网络"
```

### 04_Dashboard

```
[对齐类型] ✅ 直接对接（4 端点聚合）

数据来源（全部 ✅ 直接对接）:
  StatCard1: 总请求     ← GET /v1/models/summary → UsageSummary.total_requests
  StatCard2: 总 Token   ← GET /v1/models/summary → UsageSummary.total_tokens
  StatCard3: 总成本     ← GET /v1/models/summary → UsageSummary.cost_usd ⚠️ 恒为 0.0
                          前端展示：$0.00 + 橙色备注「成本计算 Phase 1 启用」
  StatCard4: 平均延迟   ← GET /v1/models/stats → ModelStat[].avg_latency_ms 聚合
  StatCard5: 错误率     ← GET /v1/models/stats → ModelStat[].error_rate 聚合
  StatCard6: 缓存命中率 ← GET /health → HealthResponse.metrics.cache_hit_rate

图表:
  模型用量 Top5 ← /v1/models/stats → 按 ModelStat.usage_count 排序取前 5（横向条形图）
  Token 占比环图 ← /v1/models/stats → ModelStat[].total_tokens 占比
  请求趋势 Sparkline ← GET /health → HealthResponse.metrics.total_requests（单数据点占位，Phase 1 加时间序列）

模型健康列表:
  BackendBadge + StatusDot ← GET /health → services.{ollama,zhipu,redis,postgresql}
  4 种 service.status: healthy / unreachable / configured
  配色：healthy=绿 / unreachable=红 / configured=灰

最近错误列表（前 5 条）:
  ← GET /v1/models/errors → ErrorRecord[]
  字段：timestamp · model_id · error_type Tag(4 枚举) · message（截断 60 字符）
  错误类型映射：timeout=橙 / validation=红 / quota=黄 / internal=灰

系统资源条:
  ← GET /health → system.{cpu_percent, memory_percent, disk_percent}
  进度条：0-100%，≥80% 变橙色

快捷操作: 去 Playground · 路由状态 · 缓存管理 · 文档中心
```

### 05_Model_Hub

```
[对齐类型] ✅ 直接对接（/v1/models + /v1/models/stats 组合）

数据来源:
  主数据: GET /v1/models → ModelConfig[]（6 种 backend 枚举）
  统计增强: GET /v1/models/stats → ModelStat[]（usage_count 附加）

ModelCard 字段映射:
  display_name    ← ModelConfig.display_name
  id              ← ModelConfig.id（code 字体）
  backend         ← ModelConfig.backend → BackendBadge（6 枚举 → 4 色映射：
                     local/ollama → 绿 · zhipu → 蓝 · deepseek → 紫 · openai/upstream → 青）
  max_tokens      ← ModelConfig.max_tokens
  cost_per_1k     ← ModelConfig.cost_per_1k_tokens → $0.00 / 免费（值为 0 时）
  enabled         ← ModelConfig.enabled → StatusDot（绿/灰）
  usage_count     ← ModelStat.usage_count（来自 stats 端点）

筛选器:
  backend 多选（6 种）
  是否免费（cost_per_1k == 0）
  enabled 状态

顶部提示条（固定显示）:
  「上游池动态注入的模型随 OPENAI_COMPATIBLE_UPSTREAMS 配置实时变化」

详情抽屉（展开 ModelCard）:
  全部 ModelConfig 字段 + /v1/model/type + ModelStat（stats）+ 示例 curl

底部说明卡:
  「Phase 2 · 更多供应商将经由上游池接入」← 📋 Phase 2 占位
```

### 06_Playground · 三栏核心页

```
[对齐类型] ✅ 直接对接（/v1/chat/completions + SSE）

左栏 · ParamPanel:
  ModelSelector ← GET /v1/models（按 backend 分组：云端/本地/上游池）
  temperature Slider 0-2（默认 0.7）
  top_p Slider 0-1（默认 0.9）
  max_tokens Input（默认 4096）
  stream Switch（默认开）
  模式 Tab: 💬 对话 / 📚 RAG（选 KB）/ 🔧 MCP / 🧩 能力

中栏 · 对话流（SSEStreamViewer）:
  系统提示折叠
  多轮气泡
  SSE 光标动画（仅在流式中显示）
  停止按钮 → AbortController
  Token 累加 → len(content) // 4（粗略估算）
  首 chunk 后显示「由 {upstream} 服务」徽章（_yyc3_upstream 字段）
  中断态：error chunk + 「重试」按钮
  流式错误：data: {"error":{"message":"...","type":"stream_error"}} → [DONE]

右栏 · 调试面板:
  请求 JSON 预览（CompletionRequest schema）
  响应头卡:
    X-YYC3-Upstream（灰色徽章）
    X-YYC3-Degraded（橙色徽章 "降级路径" + 主备对比）
  TTFT / 总耗时计时
  TraceCard：「primary_upstream ✗ → degraded_upstream ✓ (served in XXXms)」
  导出 Tab（curl / Python openai SDK / Node 一键复制）
  保存预设 → localStorage（非后端持久化，Phase 1 加后端存储）

请求头:
  X-API-Key: {key}
  Content-Type: application/json

SSE 流式读取契约（前端必须遵循）:
  禁用 EventSource（不支持 POST / 自定义头）
  使用 fetch + ReadableStream
  解析 data: {json}\n\n 分隔块
  结束标记: data: [DONE]\n\n
```

### 07_Routing_Observe · 上游池熔断观测

```
[对齐类型] ✅ 直接对接（/v1/router/stats + /v1/router/health，只读）

数据来源:
  UpstreamCard ← GET /v1/router/stats（上游池完整快照）
  健康探测 ← GET /v1/router/health（手动触发）

UpstreamCard 字段（来自 upstream_registry.py）:
  name            上游名称
  base_url        端点地址
  models          支持模型列表
  capability      能力标签（chat/embedding/rerank/vision...）
  priority        优先级
  weight          配置权重
  dynamic_weight  动态权重（熔断恢复中自动调整）
  breaker_state   三态：closed(绿) / open(红) / half_open(橙)
  ewma_latency    指数加权平均延迟（ms）→ LatencyBar
  ewma_error_rate 指数加权平均错误率 → ErrorRateBadge（0-1 → 0%-100%）
  total_requests  累计请求数
  total_failures  累计失败数
  last_error      最近错误消息（Tooltip 悬浮显示）
  load            当前负载
  capacity        容量上限

页头固定说明:
  「路由策略为网关内置五种枚举，规则 CRUD Phase 2 开放」
  五种：ADAPTIVE / WEIGHTED_LATENCY / LEAST_CONNECTIONS / RANDOM / ROUND_ROBIN

节点动态权重表:
  node / dynamic_weight / current_load / ewma_latency / ewma_error_rate

空态:
  显示 OPENAI_COMPATIBLE_UPSTREAMS JSON 配置指引
```

### 08_Knowledge_RAG · 双 Tab

```
[对齐类型] ✅ 直接对接（9 端点）

Tab1 · 知识库管理:
  KB 卡片网格 ← GET /v1/knowledge-bases
  字段: name · description · 文档数（GET /v1/knowledge-bases/{id}/stats）
        · chunks · 创建时间
  操作: 创建 / 编辑 / 删除（ConfirmDialog）
  详情抽屉: 完整 stats + 文档列表（GET /v1/documents?kb_id={id}）

Tab2 · 文档与检索:
  拖拽上传 ← POST /v1/documents/upload
    状态：上传中 → 解析中 → 完成 / 失败 → reprocess 重试
  检索试验台:
    query + KB 多选 + top_k → POST /v1/rag/search → SearchResponse
    相似度分数条 + 片段高亮
  问答试验台:
    query + KB 多选 → POST /v1/rag/ask
    答案 + 引用来源折叠

DocumentResponse 关键字段:
  id / kb_id / name / status(pending/parsing/ready/error) / chunk_count
  支持 GET /v1/documents/{id}/chunks 查看分块
  支持 POST /v1/documents/{id}/reprocess 重处理
```

### 09_MCP_Tools · 14 端点工具调试台

```
[对齐类型] ✅ 直接对接（14 个 MCP 端点）

左侧工具树（按类别分组）:
  /v1/mcp/search           跨工具搜索
  /v1/mcp/tools            工具列表
  local/                   本地 MCP
    /v1/mcp/local/status   健康灯
    /v1/mcp/local/tools    工具列表
    /v1/mcp/local/execute  执行
  web/                     网页能力
    /v1/mcp/web/read
    /v1/mcp/web/search
  github/                  GitHub
    /v1/mcp/github/search
    /v1/mcp/github/structure
  filesystem/              文件系统
    /v1/mcp/filesystem/read
    /v1/mcp/filesystem/list
  docker/                  Docker
    /v1/mcp/docker/containers
    /v1/mcp/docker/logs
  database/                数据库
    /v1/mcp/database/query
    /v1/mcp/database/tables

右侧调试面板:
  参数 JSON 编辑（根据选中工具的 Schema 动态生成）
  执行按钮 → POST /v1/mcp/execute → MCPToolRequest
  响应：MCPToolResponse（JSON Viewer + 耗时 + 错误态）
  常用工具一键模板（搜索网页 / 查容器 / 查数据库表）
```

### 10_Cache_Admin

```
[对齐类型] ✅ 直接对接（4 端点）

StatCard（来自 GET /v1/cache/stats /info）:
  命中率 / 条目数 / TTL

操作:
  按模型失效: ModelSelector → POST /v1/cache/invalidate/{model} → Toast
  全量清空: DELETE /v1/cache/all → ConfirmDialog（输入 "CLEAR" 二次确认）
```

### 11_Monitor_Logs

```
[对齐类型] ✅ 直接对接（错误部分）+ 📋 Phase 2 占位（请求级日志）

上半 · 错误记录:
  ← GET /v1/models/errors → ErrorRecord[]
  表格列:
    timestamp · model_id · error_type(4 枚举) · message
  行详情 Drawer: 完整错误 + TraceCard（如有降级路径）
  筛选: error_type / model_id / 时间范围

  ⚠️ ErrorRecord.error_type 枚举只有 4 种：
     timeout(橙) / validation(红) / quota(黄) / internal(灰)
     不是 v3.0 假设的 "network/api/timeout/validation"

下半 · 系统健康:
  ← GET /health → services / system / uptime_seconds / version
  4 张服务卡: ollama · zhipu · redis · postgresql
    status: healthy(绿) / unreachable(红) / configured(灰)
    ollama 额外显示延迟（如可达）
  系统进度条: CPU / 内存 / 磁盘
  版本号: /v1/versions
  呼吸灯: /healthz

底部说明条:
  📋 「请求级日志将于 Phase 2 开放」← /v1/logs 端点待新增
```

### 12_Settings

```
[对齐类型] ✅ 直接对接

连接设置卡:
  网关地址（只读，https://api.0379.world）
  API Key 掩码显示 + 「重新输入」按钮
  「断开连接」→ 清除 localStorage yyc3_api_key → 重定向 Connect

偏好设置:
  主题切换（Dark/Light，对应 Mode）
  密度切换（Comfortable/Compact）
  语言时区

默认 Playground 参数:
  temperature / top_p / max_tokens / stream 默认值

关于:
  ← GET /v1/versions（版本信息）
  ← GET /health → version + uptime_seconds
  版权 YanYuCloudCube
```

### 13_Docs_API

```
[对齐类型] ✅ 直接对接

左侧导航:
  快速开始 · 认证说明 · 模型列表 · 聊天补全(同步+SSE 双示例)
  · 知识库 · MCP · 错误码表 · 健康检查

右侧 CodeBlock:
  三语言 Tab: curl / Python openai SDK / Node.js

底部外链卡:
  → GET /docs（Swagger UI，免认证）
  → GET /openapi.json（OpenAPI 规范，免认证）
```

### 14_Roadmap_Phase2 · 规划占位

```
[对齐类型] 📋 Phase 2 分期（线框占位，不设计完整 UI）

四张线框卡 + 后端改造标注:
  1. API Keys 管理
     后端改造：api_keys 表 + /v1/keys CRUD 端点
     .env 静态迁移 → 数据库化（归属/权限/过期/白名单）
  2. Usage Billing
     后端改造：usage_log 加 cost_usd/api_key_hash/latency_ms/request_id/status/error_code
     /v1/logs + /v1/usage/timeline 端点
  3. Alerts Webhooks
     后端改造：alerts/webhooks 表 + 规则引擎
     预算/阈值告警触发 HTTP POST
  4. Team RBAC
     后端改造：users/roles/projects 表
     Key 按项目分组 + 角色权限
```

### 15_Prototype_Flows · 6 条闭环

```
[对齐类型] ✅ 直接对接（全部使用真实端点）

Flow 1: Connect → Dashboard → Playground → SSE 流式动画 → 右栏上游徽章 → 回 Dashboard
Flow 2: Model Hub → 筛「本地免费」→ 详情抽屉 → 去 Playground → 模型自动选中
Flow 3: RAG → 建库(POST KB) → 传文档(P upload) → 检索(P search) → 引用高亮
Flow 4: MCP → 选 web_search → 执行(P execute) → 结果 JSON
Flow 5: Routing → 查看 open 熔断(router/stats) → 刷新健康(router/health) → half_open 恢复 → Dashboard 联动
Flow 6: Cache → 查命中率(cache/stats) → 按模型失效(P invalidate) → Toast

每条 Flow 含五态: 默认 / 加载 / 空 / 错误 / 成功
Playground 额外: 流式中 / 中断
Connect 额外: 401 Unauthorized
```

### 16_QA_Self_Check · 自检矩阵

```
[对齐类型] ✅ QA 框架（13 条增强）

基础 8 条 + v4.0 新增 5 条后端对齐专项:

  1. 变量绑定：颜色/间距/圆角/字体全部 Variables
  2. 组件化：8 种 state × 变体矩阵全覆盖
  3. Auto Layout：所有 Frame/Card/Table/Nav/Form
  4. 响应式：1440/1280/1024/768；Playground 三栏→两栏
  5. 可访问性：对比度 ≥4.5、焦点态、键盘顺序、触控 ≥44px
  6. 6 条 Flow 跑通（含返回/关闭/确认/取消）
  7. 每页五态 + 流式中 + 中断 + 401

v4.0 新增后端对齐专项 ⚠️:
  8. 【字段真实】所有数据字段与 §1.2 Schema 完全一致
     - ErrorRecord.model_id（不是 model）
     - ErrorType 仅 4 枚举
     - ModelConfig.backend 仅 6 枚举
     - cost_usd 恒 0.0 → 显示占位
  9. 【端点真实】Dev Mode 绑定真实端点（禁止 /v1/keys、/v1/billing）
  10.【数值范围】error_rate 0-1 → 0%-100%；latency 按颜色分级
  11.【SSE 协议】前端使用 fetch+ReadableStream（不是 EventSource）
  12.【熔断颜色】closed=绿/open=红/half_open=橙
  13.【空态处理】router/stats 空态显示 UPSTREAMS JSON 指引

QA 报告格式: 表格 + 结论 + 阻塞项 + 修复记录
```

### 17_Handoff_DevMode

```
[对齐类型] ✅ 交付基线

内容:
  - 18 页路由映射 → Next.js 16 App Router
  - 全部组件的 Code Connect（Figma 组件 ↔ 代码路径）
  - 完整 API 契约（复制本文档 §1.1–§1.5）
  - 后端 Backlog 链接 → 本文档第四部分
```

---

## 第三部分 · 前端技术栈基线（锁定）

### 3.1 核心框架（禁止降级）

| 技术 | 版本 | 锁定理由 |
| ------ | ------ | ---------- |
| **Next.js** | **16.3.x Active LTS** | 2026-10 起唯一 LTS 主线；EOL 2027-10；Node ≥20.9；Turbopack 默认 |
| **React** | **19.x** | Next.js 16 内置；shadcn/ui 全组件已适配 |
| **TypeScript** | **5.9+ strict** | 类型安全 |
| **Tailwind CSS** | **4.3+** | CSS-First @theme；构建快 5×；Figma Variables 直接映射 |
| **shadcn/ui** | **React 19 版** | CLI 支持新 @theme；Base UI 封装趋势 |

### 3.2 状态与数据层

| 技术 | 版本 | 职责 |
| ------ | ------ | ------ |
| TanStack Query | v5.x（5.90+） | 服务端状态：summary/stats/health 轮询、缓存失效联动 |
| Zustand | v5.x | 客户端状态：连接态、Playground 会话、主题偏好 |
| SSE 方案 | 原生 fetch + ReadableStream | **禁用 EventSource**（需 POST + 自定义头） |

### 3.3 辅助库

| 用途 | 选型 |
| ------ | ------ |
| 图表 | Recharts（shadcn 同源） |
| 表格 | TanStack Table v8 |
| 表单 | react-hook-form + zod |
| 图标 | lucide-react |
| 日期 | date-fns |

### 3.4 Code Connect 映射

| Figma 组件 | 代码路径 |
| ----------- | --------- |
| Button/Input/Select/Switch/Slider/Table/Tabs/Tooltip/Toast/Dialog/Drawer | shadcn/ui 同名组件 |
| ModelCard | `apps/console/components/console/ModelCard.tsx` |
| SSEStreamViewer | `apps/console/components/console/SSEViewer.tsx` |
| TraceCard | `apps/console/components/console/UpstreamTrace.tsx` |
| BreakerBadge | `apps/console/components/console/BreakerBadge.tsx` |
| JsonViewer | `apps/console/components/console/JsonViewer.tsx` |
| 所有 color/* Variables | Tailwind `@theme` token（`apps/console/app/globals.css` 单一真源） |

### 3.5 前端路由（Next.js 16 App Router）

```
/                → Connect
/dashboard       → 04_Dashboard
/models          → 05_Model_Hub
/playground      → 06_Playground
/routing         → 07_Routing_Observe
/knowledge       → 08_Knowledge_RAG
/mcp             → 09_MCP_Tools
/cache           → 10_Cache_Admin
/monitor         → 11_Monitor_Logs
/settings        → 12_Settings
/docs            → 13_Docs_API
/roadmap         → 14_Roadmap_Phase2
```

---

## 第四部分 · 后端补全 Backlog（可执行清单）

> 本 Backlog 是前端 Phase 0→1 闭环的依赖项。每项标注影响的前端页面。

### BL-01: UsageLog 加 6 字段

```
影响前端: 04_Dashboard（成本）、11_Monitor_Logs（请求级日志）
优先级: P0（Phase 1 启动时立即迁移）

DDL:
ALTER TABLE usage_log ADD COLUMN api_key_hash VARCHAR(64);
ALTER TABLE usage_log ADD COLUMN cost_usd     NUMERIC(12,6) DEFAULT 0;
ALTER TABLE usage_log ADD COLUMN latency_ms    INTEGER DEFAULT 0;
ALTER TABLE usage_log ADD COLUMN request_id   VARCHAR(36);
ALTER TABLE usage_log ADD COLUMN status       VARCHAR(20) DEFAULT 'success';
ALTER TABLE usage_log ADD COLUMN error_code   VARCHAR(20);

索引:
CREATE INDEX idx_usage_log_api_key_hash ON usage_log(api_key_hash);
CREATE INDEX idx_usage_log_status        ON usage_log(status);
CREATE INDEX idx_usage_log_request_id    ON usage_log(request_id);
```

### BL-02: cost_usd 真实计算

```
影响前端: 04_Dashboard StatCard3
优先级: P0

实现:
  公式: cost = (prompt_tokens + completion_tokens) / 1000
              × model.cost_per_1k_tokens
  触发: log_usage() 时同步写入
  来源: ModelConfig.cost_per_1k_tokens（已存在）

同步修改 /v1/models/summary:
  cost_usd = SELECT SUM(total_tokens) / 1000 * cost_per_1k_tokens
             JOIN model_registry ON model_registry.id = usage_log.model
```

### BL-03: latency_ms 记录

```
影响前端: 04_Dashboard StatCard4（真实端到端延迟）、06_Playground（TTFT）
优先级: P0

实现:
  - 中间件层记录请求开始时间
  - /v1/chat/completions 响应完成时计算 elapsed
  - log_usage() 时同步写入 latency_ms
  - 含 SSE 流式：最后一个 chunk [DONE] 后记录
```

### BL-04: request_id 全链路注入

```
影响前端: 06_Playground（TraceCard）、11_Monitor_Logs（追踪）
优先级: P1

实现:
  - 中间件生成 UUID v4
  - 响应头：X-Request-Id
  - SSE 每个 chunk 含 _request_id 字段
  - log_usage() 时同步写入
```

### BL-05: api_keys 表 + CRUD 端点

```
影响前端: 14_Roadmap_Phase2 → Phase 1 移主界面
优先级: P1

DDL:
CREATE TABLE api_keys (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key_hash      VARCHAR(64) UNIQUE NOT NULL,
  name          VARCHAR(100) NOT NULL,
  created_at    TIMESTAMP DEFAULT NOW(),
  expires_at    TIMESTAMP,
  last_used_at  TIMESTAMP,
  is_active     BOOLEAN DEFAULT TRUE,
  owner_id      VARCHAR(100),
  permissions   JSONB DEFAULT '{}',
  daily_limit   INTEGER,
  monthly_limit INTEGER
);

端点:
  POST   /v1/keys              创建（返回明文仅一次）
  GET    /v1/keys              列表（返回 hash，不返回明文）
  GET    /v1/keys/{id}         详情
  PATCH  /v1/keys/{id}         更新权限/限额
  DELETE /v1/keys/{id}         撤销
  POST   /v1/keys/{id}/rotate  轮换

同步修改认证中间件:
  VALID_API_KEYS = SELECT key_hash FROM api_keys WHERE is_active = TRUE
  （替换当前 .env 静态集合匹配）
```

### BL-06: /v1/usage/timeline + /v1/logs 端点

```
影响前端: 04_Dashboard（请求趋势时间序列）、11_Monitor_Logs（请求级日志）
优先级: P1

端点:
  GET /v1/usage/timeline?from=YYYY-MM-DD&to=YYYY-MM-DD&granularity=hour|day
    → [{timestamp, total_requests, total_tokens, cost_usd, avg_latency_ms, error_rate}]

  GET /v1/logs?model=&error_type=&status=&from=&to=&limit=100
    → UsageLog[]（扩展 6 字段后）
```

### BL-07: status/error_code 写入

```
影响前端: 11_Monitor_Logs（请求级日志）
优先级: P1

实现:
  - 成功: status='success', error_code=null
  - 429 限流: status='rate_limited', error_code='RATE_LIMITED'
  - 上游熔断: status='degraded', error_code='UPSTREAM_OPEN'
  - 网络超时: status='error', error_code='NETWORK_TIMEOUT'
  - 4xx 客户端错误: status='validation', error_code 映射
```

### BL-08: /v1/router/health 扩展（熔断恢复触发）

```
影响前端: 07_Routing_Observe「刷新健康检查」按钮
优先级: P2（当前 router/health 已可用，仅需返回更详细结果）

当前返回足够，仅需：
  - 在响应中显式标记哪些熔断被探测关闭
  - 动态权重变更记录
```

### 依赖关系图

```
BL-01 (UsageLog 扩展) ──┬──→ BL-02 (cost) ──→ BL-06 (timeline/summary)
                         ├──→ BL-03 (latency)
                         ├──→ BL-04 (request_id)
                         └──→ BL-07 (status/error)

BL-05 (api_keys CRUD) ← 独立，但需同步改 auth middleware
BL-08 (router health) ← 独立增强
```

### 验收清单（每个 BL 完成）

- [ ] SQL 迁移脚本 + rollback 脚本
- [ ] `/v1/versions` 端点版本号递增（feature 数字）
- [ ] pytest 测试覆盖新字段/端点
- [ ] `/health` 端点新增能力说明
- [ ] Postman/Swagger 示例更新

---

## 第五部分 · 分阶段落地路线图（闭环版）

### Phase 0：纯前端可交付（后端零改动）

```
✅ 所有 18 页面中 15 个为直接对接
✅ Dashboard（summary/stats/health 三端点）
✅ Playground（SSE 全链路）
✅ Model Hub + Routing + RAG + MCP + Cache 全部可操作
✅ 认证：Key 输入 → localStorage → 请求头注入
✅ 预检：/healthz 免认证端点
验收: 连 api.0379.world 全链路可操作（52 端点中 43 个已通）
```

### Phase 1：计费 + 日志闭环（后端轻量扩展）

```
后端 Backlog: BL-01 → BL-02 → BL-03 → BL-04 → BL-05 → BL-06 → BL-07
前端新增: API Keys 管理页、Usage Billing 页、请求级日志完整表
前端修复: Dashboard 成本卡变真实值、请求趋势从单数据点变时间序列
验收: 创建 Key → Playground 调用 → 日志可查 → 成本真实
```

### Phase 2：团队 + 策略闭环

```
后端: users/roles/projects、routing_rules CRUD、alerts/webhooks
前端: Team RBAC、Routing 策略 CRUD + 模拟器、Alerts Webhooks
验收: 邀成员 → 分角色 → Key 按权限 → 预算告警 Webhook
```

### Phase 3：生态扩展（按需）

```
支付（Stripe/支付宝）、SSO/SCIM（OIDC）、多供应商上游（仅改 env 配置）
```

---

## 第六部分 · 工程决策记录

| 决策点 | 结论 | 理由 |
| -------- | ------ | ------ |
| 前端仓库位置 | `apps/console/`（pnpm workspace） | 与 core 解耦，CI 独立 |
| Next.js 版本 | **16.3.x LTS**（禁用 14/15） | 唯一 Active LTS；Turbopack；Node ≥20.9 |
| Node.js | **22 LTS** | Next.js 16 要求 ≥20.9 |
| 状态管理 | TanStack Query v5 + Zustand v5 | SSE + 服务端缓存最优 |
| 图表 | Recharts | shadcn 同源 |
| 设计-后端并行 | Phase 0 即启动 | 82.7% 端点可直接对接 |
| SSE | fetch + ReadableStream | EventSource 不支持 POST/自定义头 |
| Token 估算口径 | `len(content) // 4` | 与后端 sse_wrapper 一致 |

---

## 附录 · 版本演进

| 版本 | 日期 | 关键变更 |
| ------ | ------ | ---------- |
| V1 | 2026-09-01 | 初稿，多租户假设（已废弃） |
| V2 | 2026-09-02 | 落地版，删除超纲设计 |
| V3.0 | 2026-09-03 | 合并三合一，Next.js 16 |
| **V4.0** | **2026-09-17** | **闭环对齐版：逐页对齐类型标注、真实 Schema 字段级契约、完整可执行 Backlog** |

### 与 v3.0 的关键差异

| 项 | v3.0 | v4.0 |
| ---- | ------ | ------ |
| ErrorRecord.model vs model_id | 用 model | **model_id（OpenAPI 实况）** |
| error_type 枚举 | network/api/timeout/validation | **timeout/validation/quota/internal（4 枚举）** |
| backend 枚举 | 4 色映射 | **6 枚举 → 4 色（含 local/openai）** |
| 对齐比例 | 40/35/25 | **82.7/7.7/0**（精确端点级） |
| cost_usd | 占位提示 | **明确标注恒 0.0 + BL-02 计算方案** |
| UsageLog 缺失 | 笼统 5 字段 | **精确 6 字段 + DDL + 索引** |
| 后端 Backlog | 无 | **8 项可执行清单 + 依赖图 + 验收清单** |

### 历史文档处置

| 文档　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　| 处置　　　　　　　　　　　　　　　 |
| -----------------------------------------------------------------| ------------------------------------|
| docs/设计理念/Token调用平台前端-全维度设计与落地文档.md（v3.0） | **保留，但标注「已被 v4.0 取代」** |

**本文档为唯一真源，后续修订直接更新并递增 version。**
