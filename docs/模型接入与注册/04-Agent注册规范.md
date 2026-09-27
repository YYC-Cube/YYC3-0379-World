---
file: 04-Agent注册规范.md
description: Agent 注册规范 - A2A 生产契约为基线，MCP 工具声明为演进层
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-09-27
updated: 2026-09-27
status: active
tags: [spec],[agent],[a2a],[mcp],[registry]
category: spec
---

# Agent 注册规范（✅ A2A 生产基线 + 📋 MCP 演进层）

> **定位警示**：原 MRS-2026 §10 设计的 `/registry/v1/agents` 10 端点**未实现且与已生产验证的 A2A 体系双轨冲突**。本文档以现有 A2A 生产契约为唯一基线，MCP 工具声明收敛为演进层，禁止平行建设第二套注册体系。

## 1. 现状基线：A2A 注册体系（✅ 生产）

> 生产契约全文见 [A2A开放API契约.md](../架构与部署/A2A开放API契约.md)；代码锚点 [a2a.py](../../core/api/api/a2a.py) / [a2a_protocol.py](../../core/api/services/a2a_protocol.py)。2026-09-27 已完成 vk 计费链生产首验。

### 1.1 现有端点（与原规划端点的对照）

| 现有生产端点 | 方法 | 作用 | 原规划对应（📋 未实现） |
| --- | --- | --- | --- |
| `/v1/a2a/agents?capability=` | GET | 能力发现：在线 Agent Card 列表（90s 心跳超时离线） | A-01 列出 / A-10 发现 |
| `/v1/admin/a2a/agents/register` | POST | 外置 Agent 注册（幂等；重注册即刷新心跳） | A-03 注册 |
| `/v1/admin/a2a/agents/{id}/heartbeat` | POST | 心跳保活（未注册 404） | A-06 心跳 |
| `/v1/agent/a2a/tasks` | POST | 异步任务投递（202 即返，消费者组认领） | A-08 调用 |
| `/v1/agent/a2a/tasks/sync` | POST | 同步闭环（投递 + 等待回执，超时不撤回） | A-08 调用 |

> 差异要点：现有体系任务传递走 **Redis Stream 信封**（`stream:agent:task:{id}` + 消费者组 XREADGROUP），非 HTTP 直调；管理面 `/v1/admin/**` 由 AuthMiddleware ADMIN_API_KEYS 保护。

### 1.2 Agent Card 字段（现状 Schema）

```json
{
  "agent_id": "yushu-wanwu-001",
  "agent_name": "语枢·万物",
  "role": "思考者",
  "capabilities": ["chat", "data_analysis"],
  "endpoint": "stream:agent:task:yushu",
  "layer": "business"
}
```

| 字段 | 说明 |
| --- | --- |
| agent_id | 全局唯一（如 yushu-wanwu-002） |
| agent_name | 人格化名称 |
| role | 角色定位 |
| capabilities | 能力标签（能力路由依据） |
| endpoint | 任务接收流或端点（如 stream:agent:request:yushu） |
| layer | 架构层级（decision/core/business） |

内置编队 5 张卡片由网关启动时自动注册（`A2A_ENABLED`，`A2A_WORKER_AGENTS` env 可覆盖编队）；心跳超时 90s 自动离线。

### 1.3 vk 计费门控（✅ 生产首验通过）

`/v1/agent/a2a/**` 端点对虚拟密钥身份执行三闸门（env 静态键/管理键直调不计费）：

| 闸门 | 语义 | 状态码 |
| --- | --- | --- |
| 模型白名单（model_whitelist，fnmatch） | task_type 作 model 语义 | 403 |
| 预算闸门（spent_usd + est ≥ monthly_budget_usd 拒绝） | 402 语义 | 402 |
| TPM 滑窗限流（Redis INCR 分钟窗口） | 429 语义 | 429 |

成本直报：`X-A2A-Cost` 响应头按任务类型定价（`pricing.task_cost`，data_analysis=0.002 USD）；spend 经 Redis 队列批量落 `spend_logs` + `virtual_keys.spent_usd` 增量同步。

## 2. Agent 元数据目标 Schema（📋 演进层）

在 Agent Card 基础上**扩展**（不另起炉灶），对齐原 MRS §10 设计意图：

```typescript
interface AgentMetadataExtended extends AgentCard {
  // ── 演进新增字段 ──
  version: string;                    // 语义化版本
  agent_type: "mcp" | "business" | "orchestrator" | "monitor" | "custom";
  tools: ToolDeclaration[];           // MCP 工具声明（§3）
  protocol: "stream" | "http" | "mcp" | "grpc" | "websocket";  // 现状 stream
  auth_type: "none" | "api_key" | "jwt" | "oauth2";
  timeout_seconds: number;
  max_concurrent: number;
  rate_limit_per_minute: number;
  owner: string;
}
```

> 字段映射决策：`endpoint` 保留（现状语义：任务流名）；`protocol` 新增区分传输形态。原设计 `family_member/domain` 并入 `layer`/`role`，不重复建模。

## 3. MCP 工具声明（📋 演进层）

```typescript
interface ToolDeclaration {
  name: string;                  // 工具名，如 "web_search"
  description: string;
  parameters: JSONSchema;        // 参数 JSON Schema
  returns: JSONSchema;           // 返回 JSON Schema
  timeout_seconds: number;
  rate_limit_per_minute: number;
}
```

**演进路径**：MCP 工具 Agent 接入时，注册为 Agent Card（capabilities 含 `tool_use`）+ tools 声明；任务投递仍走统一信封流，由具备 MCP 桥接能力的 Worker 消费转译。**不新建** `/registry/v1/agents/{id}/tools/*` 调用面——工具调用统一经 `/v1/agent/a2a/tasks`（task_type=tool_invoke，payload 携带工具名与参数），复用 vk 计费门控与审计链。

## 4. 演进层注册端点规划（📋）

| 规划端点 | 方法 | 说明 | 实现载体 |
| --- | --- | --- | --- |
| `/v1/admin/a2a/agents` | GET | 列出全部（含离线）Agent 及扩展元数据 | 扩展现有 register 路由 |
| `/v1/admin/a2a/agents/{id}` | PATCH | 更新扩展元数据（tools/限流/超时） | 新增 |
| `/v1/admin/a2a/agents/{id}` | DELETE | 注销 Agent | 新增 |
| `/v1/a2a/agents/{id}/tools` | GET | 列出声明的工具（能力发现增强） | 新增（只读） |

> 认证：统一走现有 AuthMiddleware（admin 面管理键），不引入独立 Registry Token。

## 5. 审计与计费（复用现有链）

- Agent 任务调用全量审计（a2a_audit → Loki，✅ 生产）
- vk 身份调用计费（spend_logs + spent_usd，✅ 生产）
- 演进层补充：Agent 注册/注销/更新入审计事件（agent.registered / agent.deregistered / agent.updated）

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0.0 | 2026-09-27 | 自原 MRS §10 重构：消除与 A2A 双轨冲突——现有 5 端点为基线，MCP 工具声明为演进扩展，工具调用统一走任务信封复用 vk 计费；补 Phase 7 生产首验锚点 |
