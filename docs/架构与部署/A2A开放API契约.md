# A2A 开放 API 契约

> **YanYuCloudCube · 0379-World 智能体协同事务面**
> 版本 v1.0.0 · 2026-09-27 · 状态：灰度（NAS 生产栈已开闸）
> 面向外部调用方 / 内部编排方的稳定契约；破坏性变更需升 major 并公告。

---

## 1. 概述

A2A（Agent-to-Agent）面提供**单 Agent 任务投递**、**同步闭环**、**多 Agent 扇出编排**三类协同事务端点。任务经 Redis Stream 消费者组投递至业务 Agent Worker（语枢/预见/创想/格物/演启五编队），结果经结果流回执聚合。

**基址**：`https://api.0379.world`（生产）· `http://localhost:8000`（本地）

---

## 2. 认证

| 方式 | 头部 | 计费 |
| ---- | ---- | ---- |
| 虚拟密钥 vk（推荐） | `X-API-Key: vk-...` | ✅ 白名单/预算/TPM 三闸门 + spend 记账 |
| 静态 API Key | `X-API-Key: sk-...` | ❌ 不计费不门控 |

vk 语义：
- **模型白名单**：`task_type` 作 model 语义（fnmatch 通配，如 `data_*`），未命中 → `403 model_not_allowed`
- **月度预算**：`spent_usd >= monthly_budget_usd`（budget>0 时）→ `402 budget_exceeded`
- **TPM 限流**：Redis 滑窗 `count + est - 1 > limit`（limit>0 时）→ `429 rate_limit_exceeded`

---

## 3. 端点

### 3.1 能力发现

```http
GET /v1/a2a/agents?capability=data_analysis
```

返回在线 Agent Card 列表（心跳 90s 超时即离线）。`capability` 可选过滤。

```json
{ "agents": [ { "agent_id": "yushu-wanwu-001", "agent_name": "语枢·万物", "capabilities": ["data_analysis"], "status": "online" } ], "count": 1 }
```

### 3.2 异步任务投递

```http
POST /v1/agent/a2a/tasks
X-API-Key: vk-...
```

```json
{ "receiver_agent_id": "yushu-wanwu-001", "task_type": "data_analysis", "payload": { "input": "分析文本", "knowledge_context": [] }, "priority": 5 }
```

- 路由：`receiver_agent_id` 直投优先；缺省按 `capability` 在线发现（取首个）；两者均空 → `400`
- 响应 `202`：`{ msg_id, trace_id, receiver, stream, status: "queued" }`
- 响应头 `X-A2A-Cost`：本任务计费成本（USD，6 位小数）

### 3.3 同步闭环

```http
POST /v1/agent/a2a/tasks/sync
```

`3.2` 字段 + `trace_id`（可选，调用方关联用）+ `timeout_seconds`（1-120，缺省 30）。

- 响应 `200`：`{ trace_id, receiver, status: "succeeded" | "failed", result }`
- 超时：`status: "timeout"`（任务不撤回，Worker 照常消费，结果不丢）
- 成本语义：**超时也计费**（任务已入队消耗执行位）

### 3.4 多 Agent 扇出编排

```http
POST /v1/agent/a2a/orchestrate
```

```json
{ "capability": "data_analysis", "task_type": "data_analysis", "payload": { "input": "..." }, "priority": 5, "timeout_seconds": 60, "model": null }
```

- 按 `capability` 在线 Agent **全量扇出**（无在线 → `404 no_online_agent`）
- `wait_all` 等齐：`status: "completed"`（全成）| `"partial"`（有败）| `"timeout"`（响应含已完成部分 `results`）
- `X-A2A-Cost` = 任务单价 × 扇出数
- 响应：`{ trace_id, receivers, status, progress: "2/5", results: { "<agent_id>": {...} } }`

---

## 4. 计费契约

| 项 | 语义 |
| ---- | ---- |
| 计费对象 | 仅 vk 身份；静态/管理键零计费 |
| 成本直报 | 响应头 `X-A2A-Cost`（端点按任务类型定价回填） |
| 定价源 | PG `task_prices` 表（启动加载）> 内置 `TASK_TYPE_PRICES` > 兜底常量 0.001 USD |
| 记账链路 | 中间件双探针（`X-A2A-Cost` > `X-Total-Cost`）→ spend 队列 → `spend_logs` |
| 价格管理 | `GET/PUT /v1/admin/pricing/task-types`（ADMIN_API_KEYS；内存即时生效 + PG 持久） |

内置价目（USD/任务）：

| task_type | 单价 | Agent |
| --------- | ---- | ----- |
| data_analysis | 0.002 | 语枢·万物 |
| trend_forecast | 0.003 | 预见·先知 |
| qualitative_analysis | 0.002 | 预见·先知 |
| report_polish | 0.001 | 创想·灵韵 |
| creative_brainstorm | 0.001 | 创想·灵韵 |
| content_validation | 0.001 | 格物·宗师 |
| code_review | 0.002 | 格物·宗师 |
| content_formatting | 0.0005 | 演启·乾行 |

---

## 5. 错误码

| HTTP | `detail.error.type` | 场景 |
| ---- | ------------------- | ---- |
| 400 | `missing_route_target` | receiver 与 capability 均空 |
| 401 | — | 缺失认证凭证 |
| 402 | `budget_exceeded` | vk 月度预算耗尽 |
| 403 | `model_not_allowed` | task_type 不在白名单 |
| 403 | `admin privileges required` | 管理端点非管理密钥 |
| 404 | `no_online_agent` | capability 无在线 Agent |
| 404 | `agent_not_registered` | 心跳未知 agent_id |
| 422 | — | 请求体校验失败（Pydantic） |
| 429 | `rate_limit_exceeded` | vk TPM 滑窗超限 |

错误体统一形态：

```json
{ "detail": { "error": { "type": "budget_exceeded", "message": "..." } } }
```

---

## 6. 可靠性语义

| 保障 | 机制 |
| ---- | ---- |
| 至少一次投递 | Redis Stream 消费者组；Worker 成功才 XACK |
| 失败重试 | 3 次（INCR 计数）→ 死信流 `stream:agent:dlq` |
| 宕机恢复 | XAUTOCLAIM 认领空闲 >60s 挂起消息（结果流/任务流/审计流三面） |
| 结果幂等 | sender 覆盖式聚合（重放回执不重复计数） |
| 超时不丢 | 同步超时任务留任务流照常消费 |

---

## 7. 可观测

- Prometheus `/metrics`：`a2a_dlq_enqueued_total` / `a2a_result_orphan_total` / `a2a_result_reclaimed_total` / `a2a_dlq_depth` / `a2a_result_stream_len` / `a2a_result_stream_pending` / `a2a_task_stream_pending`
- Loki（`job=a2a-audit`，labels `event`/`agent`）：孤儿回执 / 死信 / 重试审计可检索
- Grafana：`a2a-observability` 仪表盘（七面板）+ 告警三条（死信/孤儿/回收停滞）

---

## 8. 变更记录

| 版本 | 日期 | 变更 |
| ---- | ---- | ---- |
| v1.0.0 | 2026-09-27 | 首版：三端点 + 计费契约 + 错误码 + 可靠性/可观测语义 |
