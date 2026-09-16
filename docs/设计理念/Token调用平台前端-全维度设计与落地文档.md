---
file: Token调用平台前端-全维度设计与落地文档.md
description: YYC³ Console 前端设计提示词 + 后端能力审计 + 落地路线 三合一全维度文档（合并 V1/V2/衔接指导，去冗余）
author: AI Tutor
version: v3.0.0
created: 2026-09-03
updated: 2026-09-17
status: **deprecated**（已被 v4.0 取代，见同目录 `-v4闭环对齐版.md`）
tags: [frontend],[figma],[design],[api-alignment],[nextjs16],[roadmap]
category: guide
supersedes:
  - Token调用平台完整前端设计提示词.md（V1）
  - Token调用平台完整前端设计提示词-V2落地版.md（V2）
  - 落地衔接指导-Token调用平台前端.md
superseded_by: Token调用平台前端-全维度设计与落地文档-v4闭环对齐版.md
---

> ⚠️ **本文档已被 v4.0 闭环对齐版取代**。v4.0 新增：逐页后端对齐类型标注（✅直接对接/🔧轻量扩展/📋Phase 2）、真实 Schema 字段级契约（2026-09-17 OpenAPI 审计）、8 项可执行后端 Backlog。v3.0 仅作历史参考，请使用 v4.0。

# Token调用平台前端 · 全维度设计与落地文档

> **文档定位**：本文档合并并取代以下三份文档——①《Token调用平台完整前端设计提示词》(V1)、②《V2落地版》、③《落地衔接指导》。保留 V2 落地版全部设计指令（可直接提交 Figma），融入衔接指导的后端审计与分阶段路线，统一技术栈基线为 **Next.js 16（当前 LTS 16.3.x）**。数据一致性以本文档为唯一真源。

---

## 第一部分 · 后端能力审计（设计的事实基础）

### 1.1 网关真实路由清单（52 个端点，来源 core/api 代码审计）

| 类别 | 端点 | 状态 |
| ------ | ------ | ------ |
| 聊天 | `POST /v1/chat/completions`（SSE 流式）、`WS /ws/chat`、`WS /ws/monitor` | ✅ 生产 |
| 模型 | `GET /v1/models`、`/v1/models/stats`、`/v1/models/errors`、`/v1/models/summary`、`/v1/model/type` | ✅ 生产 |
| 路由 | `GET /v1/router/stats`、`/v1/router/health` | ✅ 真实 EWMA/熔断数据 |
| 缓存 | `GET /v1/cache/stats`、`/v1/cache/info`、`POST /v1/cache/invalidate/{model}`、`DELETE /v1/cache/all` | ✅ 生产 |
| 能力代理 | `POST /v1/embeddings`、`/v1/rerank`、`/v1/audio/transcriptions`、`/v1/ocr` | ✅ 生产 |
| MCP | `/v1/mcp/tools`、`/v1/mcp/execute`、`/v1/mcp/local/*`、`/v1/mcp/web/*`、`/v1/mcp/github/*`、`/v1/mcp/docker/*`、`/v1/mcp/database/*` | ✅ 生产 |
| RAG | `/v1/knowledge-bases`(CRUD)、`/v1/documents`(CRUD+upload)、`/v1/rag/search`、`/v1/rag/ask` | ✅ 生产 |
| 健康 | `/health`、`/healthz`、`/v1/ping`、`/v1/versions` | ✅ 生产 |
| 监控 | `/metrics`（Prometheus）、`/docs`、`/openapi.json` | ✅ 生产 |

### 1.2 认证与限流现状

- 认证：`X-API-Key` 头（主）+ `Authorization: Bearer JWT` 双通道；**无登录注册体系**
- API Key 本质：`.env` 中 `API_KEYS=逗号分隔`，集合精确匹配——无归属/权限/过期/白名单（Phase 2 数据库化）
- 免认证路径：`/health`、`/healthz`、`/v1/ping`、`/docs`、`/openapi.json`
- 限流：Redis 滑动窗口（Lua 原子脚本），IP + X-User-ID 双维度，Redis 故障降级内存

### 1.3 数据模型现状（UsageLog）

```
usage_log: id, model, backend_type, prompt_tokens, completion_tokens,
           total_tokens, user_id(可选), created_at
```

缺失：api_key_hash、请求ID、延迟、成本、错误码、状态、项目归属（Phase 1/2 补齐）。

### 1.4 模型矩阵现状

- 内置 Provider：zhipu（glm-4-flash/plus）、deepseek（chat/coder）、ollama（llama3.2/codegeex4/qwen2.5）
- 动态上游池：`upstream_registry`（OpenAI 兼容：vLLM/NIM/SGLang），熔断器三态 closed/open/half_open、EWMA 延迟、动态权重、故障转移、fallback_url 主备地址
- 成本：`cost_per_1k_tokens` 静态声明；`/v1/models/summary` 的 `cost_usd` 恒为 0.0（Phase 1 接真实计算）

### 1.5 协议级契约（前端必须遵循）

- SSE：`data: {OpenAI chunk}\n\n`，结束 `data: [DONE]\n\n`；首 chunk 含 `_yyc3_upstream` 字段
- 响应头：`X-YYC3-Upstream`（实际服务者）、`X-YYC3-Degraded`（降级路径）
- 错误统一结构：`{"detail": {"error": "<network|api|timeout|validation>", "message", "context", "status_code"}}`；限流 429 附 `retry_after`
- 流式错误 chunk：`data: {"error": {"message", "type": "stream_error"}}\n\n` 后接 `[DONE]`
- Token 估算口径：`len(content) // 4`
- 路由策略为内置枚举：ADAPTIVE / WEIGHTED_LATENCY / LEAST_CONNECTIONS / RANDOM / ROUND_ROBIN（规则 CRUD 属 Phase 2）

### 1.6 对齐比例结论

**40% 直接对接（现有 52 端点）· 35% 轻量扩展（Phase 1/2）· 25% 超纲分期（Phase 2/3）**。V1 设计中的登录注册、多租户、支付、路由规则 CRUD 均已从设计范围移除或转为占位。

---

## 第二部分 · Figma 设计提示词（落地版，可直接提交）

### 角色

你是资深 Figma Agent、产品设计系统架构师、前端架构师、QA 自动化专家。你精通 Figma Variables、Modes、Auto Layout、Constraints、Components、Variants、Component Properties、Prototype、Smart Animate、Interactive Components、Dev Mode、Code Connect、Figma MCP、REST API、Plugin API。你必须直接在 Figma 中创建完整设计文件，而不是只给建议。

### 项目

为「YanYuCloudCube」设计"大模型统一网关控制台"的完整前端。这是**已上线的生产级 API 网关**（单租户自用，非多租户 SaaS），面向**开发者与运维管理员**。核心价值：统一调用多模型（云端 GLM/DeepSeek + 本地 Ollama + OpenAI 兼容上游池）、SSE 流式 Playground、上游池健康可观测、Token 用量统计、知识库 RAG 管理、MCP 工具调试、缓存管理。

### 默认参数

- 平台名：YanYuCloudCube Console
- 后端基座：YYC³ 统一模型网关 v2.0（FastAPI），生产地址 `https://api.0379.world`
- 品牌主色 #6C5CE7；辅助色：青 #00D4FF（上游/流式）、绿 #22C55E（健康）、橙 #F59E0B（降级/告警）、红 #EF4444（熔断/错误）
- 风格：开发者工具、数据密集、科技感、暗色优先，支持亮色
- 字体：Inter / 思源黑体，代码 JetBrains Mono
- 语言：中文为主，保留英文技术名词
- 断点：1440（主）、1280、1024、768（375 仅侧边栏折叠示意）
- 可访问性：WCAG 2.2 AA，对比度 ≥ 4.5:1，键盘可操作，焦点态清晰

### 数据源锚点（禁止虚构，全部来自第一部分 §1.1–§1.5）

设计所有页面时，数据绑定一律引用第一部分的真实端点与字段。**禁止设计**：登录注册/SSO/MFA、API Key CRUD、账单/充值/发票、预算告警、请求级日志、路由规则 CRUD、团队成员管理——这些只在 `14_Roadmap_Phase2` 以线框占位呈现。

### 必须使用的 Figma 核心技术

1. Variables：颜色、间距、圆角、阴影、字体、密度、主题
2. Modes：Light、Dark、Density/Comfortable、Density/Compact
3. Auto Layout：所有 Frame、Card、Table、Nav、Form、Button
4. Components + Variants + Component Properties：全部组件化
5. Prototype：主链路可点击跑通，含弹窗、抽屉、Toast、表单校验、返回
6. Dev Mode：关键组件绑定 §1.5 真实端点与字段注释
7. Code Connect：组件与 Next.js 16 + shadcn/ui 命名映射（见 §第三部分）
8. Figma MCP：预留可被 MCP 读取的页面、组件、变量、注释结构

### 文件页面结构（18 页）

```
00_Cover
01_Foundations
02_Components
03_Connect          （API Key 连接页）
04_Dashboard
05_Model_Hub
06_Playground
07_Routing_Observe  （上游池可观测，只读）
08_Knowledge_RAG    （知识库+文档+检索问答）
09_MCP_Tools        （工具调试台）
10_Cache_Admin      （缓存管理）
11_Monitor_Logs     （错误记录+系统健康）
12_Settings
13_Docs_API
14_Roadmap_Phase2   （规划占位：Keys/账单/告警/团队 线框）
15_Prototype_Flows
16_QA_Self_Check
17_Handoff_DevMode
```

### 设计系统 Foundations

**颜色变量**

- color/bg/default、subtle、elevated、overlay
- color/text/primary、secondary、tertiary、inverse
- color/border/default、strong、focus
- color/brand/primary(#6C5CE7)、hover、pressed
- color/status/success(#22C55E)、warning(#F59E0B)、danger(#EF4444)、info(#00D4FF)
- color/backend/zhipu、deepseek、ollama、upstream（四个真实后端类型配色）
- color/breaker/closed(绿)、open(红)、half_open(橙)（熔断三态专用）

**间距与形状**

- space/0=0、1=4、2=8、3=12、4=16、5=20、6=24、8=32、10=40、12=48、16=64
- radius/sm=6、md=10、lg=16、xl=24、full=999
- shadow/sm、md、lg、focus

**字体**

- display/lg、display/md、h1、h2、h3、body/lg、body/md、body/sm、caption、code/md、code/sm

### 组件库（含专属组件）

通用：Button、IconButton、Input（含 Key 掩码态）、Textarea、Select、Combobox、Checkbox、Radio、Switch、Slider、DatePicker、Tabs、Breadcrumb、Pagination、Tag、Badge、StatusDot、Tooltip、Popover、Dropdown、CommandMenu、Card、Table、DataGrid、FilterBar、ColumnSettings、EmptyState、Skeleton、Sidebar（可折叠）、TopBar、NavItem、UserMenu、SearchGlobal、Modal、Drawer、Sheet、Toast、Alert、ConfirmDialog、CodeBlock（curl/Python/Node Tab）、CopyButton、KeyMask、JsonViewer、LogRow、Chart、Sparkline

控制台专属：StatCard、ModelCard、BackendBadge、UpstreamCard、BreakerBadge（三态）、LatencyBar、ErrorRateBadge、ErrorState（四类错误+429 限流态）、SSEStreamViewer（流式输出）、TraceCard（降级链路：primary → degraded → served_by）、ModelSelector、BackendSelector、KBSelector、MCPToolPicker、ParamPanel

变体覆盖：variant（primary/secondary/ghost/danger/link）× size（xs/sm/md/lg）× state（default/hover/active/focus/disabled/loading/error/success）× tone（neutral/brand/success/warning/danger/info）

### 逐页详规

**00_Cover**：平台名 "YanYuCloudCube Console"、Slogan「统一模型网关 · 可观测 · 可调试」、版本 v2.0、日期、设计系统/原型/QA 入口、后端基座 api.0379.world 标注。

**01_Foundations**：颜色（含 backend 四色、breaker 三态）、字体、间距、圆角、阴影、变量表、Light/Dark 切换说明。特别规范：SSE 流式光标动画、Token 千分位格式、延迟 ms 单位。

**02_Components**：全部组件与变体、Do/Don't。重点：ErrorState 四类错误+限流真实文案；SSEStreamViewer 四帧（首 token 前/流式中/完成/中断）；TraceCard 示例 `dgx-spark ✗ → yyc3-33 ✓ (served)`。

**03_Connect**：单屏。Logo + 平台名 + Key 掩码输入 + 「连接」按钮 + 「记住此设备」Switch + 服务预检条（自动 ping `/healthz`）。校验中→成功进 Dashboard→失败显示 401/403 真实 `detail.message`。Dev Mode 注释：`X-API-Key` 头；localStorage `yyc3_api_key`。

**04_Dashboard**：

- 6 张 StatCard：总请求（summary.total_requests）、总 Token（summary.total_tokens）、成本占位（cost_usd，标注 Phase 2）、平均延迟（stats 聚合 avg_latency_ms）、错误率（聚合 error_rate）、缓存命中率（/health.metrics.cache_hit_rate）
- 图表：模型用量 Top5（横向条形）、Token 占比环图、请求趋势 Sparkline（Phase 1 接时间序列）
- 模型健康列表（BackendBadge + StatusDot，数据 /health.services + /v1/router/stats）
- 最近错误列表（errors 前 5 条：timestamp、model、error_type Tag、message 截断）
- 系统资源条：CPU/内存/磁盘（/health.system）
- 快捷操作：Playground、路由状态、缓存管理、文档中心

**05_Model_Hub**：

- ModelCard 网格：display_name、id（code 字体）、BackendBadge、max_tokens、cost_per_1k_tokens（0 →「免费/本地」）、enabled StatusDot、「去 Playground」「复制模型 ID」
- 筛选：后端类型多选、是否免费、状态
- 顶部提示：「上游池动态注入的模型随 OPENAI_COMPATIBLE_UPSTREAMS 配置实时变化」
- 详情抽屉：全字段 + /v1/model/type + 示例 curl + stats
- 底部说明卡：「Phase 2 · 更多供应商将经由上游池接入」（不设计未接入供应商）

**06_Playground（核心，三栏）**：

- 左栏 ParamPanel：ModelSelector（云端/本地/上游池分组）、temperature Slider(0-2, 默认0.7)、top_p Slider(0-1)、max_tokens Input、stream Switch(默认开)；模式 Tab：💬 对话 / 📚 RAG（选知识库）/ 🔧 MCP / 🧩 能力（embeddings/rerank/ocr）
- 中栏：系统提示折叠、多轮气泡、SSEStreamViewer（光标动画、停止=AbortController、Token len/4 实时累加）、首 chunk 后「由 {upstream} 服务」徽章、中断/错误显示 error chunk + 重试
- 右栏：请求 JSON 预览、响应头卡（X-YYC3-Upstream、X-YYC3-Degraded 橙色降级提示）、TTFT/总耗时、TraceCard、导出 Tab（curl/Python openai SDK/Node 一键复制）、保存预设→localStorage
- 状态：默认/流式中/完成/错误/网络断开/401

**07_Routing_Observe（只读）**：

- 页头说明：路由策略为网关内置五种枚举，规则 CRUD Phase 2 开放
- UpstreamCard 卡片墙：name、base_url、models 数、capability、priority/weight、BreakerBadge 三态、EWMA 延迟（LatencyBar）、错误率、负载/容量进度条、累计请求/失败、last_error 截断悬浮
- 「刷新健康检查」→ /v1/router/health（检查中动画）
- 节点动态权重表：node、dynamic_weight、current_load、ewma_latency、ewma_error_rate
- 空态：OPENAI_COMPATIBLE_UPSTREAMS JSON 配置指引

**08_Knowledge_RAG（双 Tab）**：

- Tab1 知识库：KB 卡片（name、description、文档数、chunks、创建时间）、创建/编辑/删除（ConfirmDialog）、详情抽屉（stats + 文档列表）
- Tab2 文档与检索：拖拽上传（上传中/解析中/完成/失败 + reprocess 重试）、检索试验台（query + KB 多选 + top_k → 相似度分数条 + 片段高亮）、问答试验台（答案 + 引用来源折叠）

**09_MCP_Tools**：左侧工具树（搜索/读取/执行/本地 MCP 四组 + local/status 健康灯）；右侧参数 JSON 编辑 → POST /v1/mcp/execute → 响应 JSON + 耗时 + 错误态；常用工具一键模板。

**10_Cache_Admin**：StatCard（命中率、条目数、TTL）；按模型失效（选择器 + Toast 显示失效数）；全量清空（ConfirmDialog + 输入 "CLEAR" 确认）。

**11_Monitor_Logs**：

- 上半错误表：timestamp、model、error_type（network 蓝/api 黄/timeout 橙/validation 红）、message；筛选类型/模型/时间；行详情 Drawer（完整错误 + TraceCard）
- 下半系统健康：services 四卡（ollama 带延迟、zhipu 配置态、redis、postgresql）+ uptime + version + /healthz 呼吸灯
- 说明条：「请求级日志将于 Phase 2 开放」

**12_Settings**：连接设置（网关地址只读、Key 掩码、断开连接）、偏好（主题/语言/时区）、默认 Playground 参数、缓存入口、关于（version、/v1/versions）。

**13_Docs_API**：左侧导航（快速开始、认证、模型、聊天补全同步+SSE 双示例、知识库、MCP、错误码表、健康检查）；右侧 CodeBlock 三语言切换；底部外链卡 → `/docs`（Swagger UI）。

**14_Roadmap_Phase2**：四张线框卡：API Keys 管理（.env→数据库化）、Usage_Billing（usage_log 加 cost 列）、Alerts_Webhooks（预算/阈值）、Team_RBAC（用户/角色/项目）；标注后端改造点。

**15_Prototype_Flows**（每流程含 默认/加载/空/错误/成功 五态）：

- Flow 1：Connect → Dashboard → Playground → SSE 流式动画 → 右栏上游徽章 → 回 Dashboard
- Flow 2：Model Hub → 筛「本地免费」→ 详情抽屉 → 去 Playground → 模型自动选中
- Flow 3：RAG → 建库 → 传文档（进度）→ 检索 → 引用高亮
- Flow 4：MCP → 选 web_search → 执行 → 结果 JSON
- Flow 5：Routing → 发现 open 熔断 → 刷新健康检查 → half_open 恢复 → Dashboard 联动
- Flow 6：Cache → 查命中率 → 按模型失效 → Toast

**16_QA_Self_Check**：覆盖矩阵、测试用例、状态、证据、修复记录；执行智能自检循环：生成→检查→修复→再检查→报告。

**17_Handoff_DevMode**：路由映射 + Code Connect + API 契约全表（复制本文 §1.1–§1.5）。

### QA 自检清单（13 条）

1. 所有颜色/间距/圆角/字体绑定 Variables，无游离样式
2. 组件化覆盖 8 种 state
3. 全部 Auto Layout，支持增长/截断/换行
4. 响应式 1440/1280/1024/768；侧边栏 1024 折叠；Playground 三栏→两栏（右栏折叠为抽屉）
5. 对比度 ≥4.5:1、焦点态、键盘顺序、触控 ≥44px
6. 6 条 Flow 可点击跑通，含返回/关闭/确认/取消
7. 每页五态（默认/加载/空/错误/成功）；Playground 加流式中/中断；Connect 加 401
8. 表格：排序/筛选/分页/行悬停/行详情
9. 表单：必填/校验/错误提示/提交中
10. 数据真实性：字段与 §1.1–§1.5 完全一致（error_rate 是 0-1 小数；cost=0 显示「本地/免费」）
11. 命名符合规范
12. Dev Mode 绑定真实端点（禁止出现 /v1/keys、/v1/billing 等不存在端点）
13. 失败项立即修复重检，直到通过或标记阻塞

### QA 报告格式

表格：模块 | 检查项 | 状态 | 证据/链接 | 修复建议
结论：通过 / 有条件通过 / 失败 + 阻塞项 + 已修复项 + 待确认项

### 执行顺序

1. 18 Pages + 全部 Variables（含 backend 四色、breaker 三态）
2. Foundations（重点：ErrorState 文案库、SSE 动画规范）
3. Components + Variants
4. Connect、Dashboard、Model Hub、Playground
5. Routing_Observe、Knowledge_RAG、MCP_Tools、Cache_Admin
6. Monitor_Logs、Settings、Docs_API、Roadmap_Phase2
7. Prototype Flows（6 条）
8. QA 自检循环
9. Handoff DevMode（含全量 API 契约表）
10. 输出 QA_REPORT

---

## 第三部分 · 前端技术栈基线（2026-09 最新稳定版）

### 3.1 核心框架版本

| 技术 | 版本基线 | 说明 |
| ------ | --------- | ------ |
| **Next.js** | **16.3.x（Active LTS）** | 当前最新稳定版；2026-10-21 起为唯一 LTS 主线，EOL 2027-10；要求 Node.js ≥ 20.9；默认 Turbopack（16.3 dev 内存最高降 90%）；安全补丁跟进至 16.3.3+ |
| React | 19.x | Next.js 16 内置，shadcn/ui 全组件已适配（移除 forwardRef） |
| TypeScript | 5.9+ | strict 模式 |
| Tailwind CSS | 4.3+ | CSS-First 配置（@theme 指令）；构建快 5×、增量快 100×；Figma Variables 直接映射 @theme token |
| shadcn/ui | latest（Tailwind v4 + React 19 版） | CLI 支持新 @theme；Base UI 封装趋势 |

### 3.2 状态与数据层

| 技术 | 版本 | 职责 |
| ------ | ------ | ------ |
| TanStack Query | v5.x（5.90+） | 服务端状态：summary/stats/health 轮询、缓存失效联动 |
| Zustand | v5.x | 客户端状态：连接态、Playground 会话、主题偏好 |
| SSE 方案 | 原生 fetch + ReadableStream | **禁用 EventSource**（需 POST + 自定义头 X-API-Key） |

### 3.3 辅助库

| 用途 | 选型 | 备注 |
| ------ | ------ | ------ |
| 图表 | Recharts（或 shadcn/charts） | 与 shadcn 视觉同源 |
| 表格 | TanStack Table v8 | DataGrid 排序/筛选/分页 |
| 表单 | react-hook-form + zod | Connect/KB 创建/告警表单 |
| 图标 | lucide-react | shadcn 默认 |
| 日期 | date-fns | 时间格式统一 |

### 3.4 Code Connect 映射（写入 Figma Dev Mode）

| Figma 组件 | 代码组件 |
| ----------- | --------- |
| Button/Input/Select/Switch/Slider/Table/Tabs/Tooltip/Toast/Dialog/Drawer | shadcn/ui 同名组件 |
| ModelCard | `components/console/ModelCard.tsx` |
| SSEStreamViewer | `components/console/SSEViewer.tsx` |
| TraceCard | `components/console/UpstreamTrace.tsx` |
| BreakerBadge | `components/console/BreakerBadge.tsx` |
| JsonViewer | `components/console/JsonViewer.tsx` |
| Figma color/* Variables | Tailwind `@theme` token（globals.css 单一真源） |

### 3.5 前端路由映射（Next.js 16 App Router）

```
/                → Connect（未连接全局重定向至此）
/dashboard       → 04
/models          → 05
/playground      → 06
/routing         → 07
/knowledge       → 08
/mcp             → 09
/cache           → 10
/monitor         → 11
/settings        → 12
/docs            → 13
/roadmap         → 14
```

---

## 第四部分 · 分阶段落地路线图

### Phase 0：纯前端可交付（后端零改动）

- `create-next-app@latest`（Next.js 16.3 + TS + Tailwind v4）+ shadcn/ui init
- 页面：Connect、Dashboard（summary/stats/health）、Model Hub、Playground（SSE）、Routing 只读、Cache、Docs 外链
- 认证：Key 输入 → localStorage → 请求头注入；`/healthz` 预检
- **验收**：连 `https://api.0379.world` 全链路可操作

### Phase 1：计费闭环（后端小改）

- 后端：api_keys 表、usage_log 加 cost/api_key_hash/request_id/latency/status 列、`GET /v1/logs`、`/v1/keys` CRUD、`GET /v1/usage/timeline`
- 前端：API Keys 管理页、Usage_Billing 页、Logs 完整版
- **验收**：创建 Key → Playground 调用 → 账单页真实成本

### Phase 2：团队与策略

- 后端：users/roles/projects、routing_rules、alerts/webhooks、SSO 预研
- 前端：Team_RBAC、Routing 策略 CRUD+模拟器、Alerts_Webhooks
- **验收**：邀成员→分角色→按 Key 权限调用→预算告警收 Webhook

### Phase 3：生态扩展（按需）

支付（Stripe/支付宝）、SSO/SCIM（OIDC）、多供应商上游（改 OPENAI_COMPATIBLE_UPSTREAMS 配置即生效）

---

## 第五部分 · 工程决策记录

| 决策点 | 结论 | 理由 |
| -------- | ------ | ------ |
| 前端仓库位置 | `apps/console/`（pnpm workspace） | 与 core 解耦，CI 独立 |
| Next.js 版本 | 16.3.x LTS（禁用 14/15 新建项目） | 16 为当前唯一 Active LTS；Turbopack 默认；性能与安全补丁窗口最长 |
| Node.js | 22 LTS | Next.js 16 要求 ≥20.9 |
| 状态管理 | TanStack Query v5 + Zustand v5 | SSE 流式 + 服务端缓存最优解 |
| 图表 | Recharts | shadcn 生态一致 |
| 是否等后端再设计 | 否 | 40% 页面无后端依赖，设计并行 |
| SSE 实现 | fetch 流式解析 | EventSource 不支持 POST/自定义头 |

---

## 附录 · 历史文档处置记录

| 原文档 | 处置 |
| -------- | ------ |
| docs/Token调用平台完整前端设计提示词.md（V1） | 合并后删除（多租户假设已修正） |
| docs/Token调用平台完整前端设计提示词-V2落地版.md（V2） | 合并后删除（内容全部并入 §第二部分） |
| docs/设计理念/落地衔接指导-Token调用平台前端.md | 合并后删除（内容全部并入 §第一/四/五部分） |

**本文档为唯一真源，后续修订直接更新本文档并递增 version。**
