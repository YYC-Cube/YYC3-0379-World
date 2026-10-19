# 术语表 — GLOSSARY（与代码一致口径）

## 六业务域（导航分类）

| 术语 | 定义 | 关联 |
| --- | --- | --- |
| 监控中心 Monitoring | `/` 数据监控 / 跟进 / 巡查 / 告警规则 | routes.ts · Dashboard.tsx |
| 运维管理 Ops | `/operations` 操作中心 / `/files` / `/database` / `/reports` | OperationCenter 等 |
| AI 智能 AI | `/models` 提供商矩阵 / `/gateway-keys` / `/ai` / `/ai-diagnosis` | ModelProviderPanel 等 |
| AI Family | `/ai-family*` 家族域（路由树 16+ 分支） | AIFamilyPage/AIFamilyRouter |
| 开发规范 DevStd | `/design-system` / `/dev-guide` | DesignSystemPage |
| 系统管理 Admin | `/audit` / `/users`(→settings) / `/settings` / `/security` / `/pwa` / `/env-config` | SystemSettings 等 |

## AI Family · 8 Agent（id 与代码一致）

| id | 名 | 定位（代码 role 摘录） | 关联 |
| --- | --- | --- | --- |
| navigator | 言启·千行 | 意图路由，「耳朵与翻译官」 | shared.ts FAMILY_MEMBERS |
| thinker | 语枢·万物 | 经营分析「洞察引擎」 | 同上 |
| prophet | 预见·先知 | 风险雷达/趋势预测 | 同上 |
| bolero | 千里·伯乐 | 商机/人才推荐官 | 同上 |
| meta-oracle | 元启·天枢 | 总指挥/决策中枢（五步决策法） | 同上 |
| sentinel | 智云·守护 | 安全官/合规审计 | 同上 |
| master | 格物·宗师 | 质量官/进化导师 | 同上 |
| creative | 创想·灵韵 | 创意/内容/架构师 | 同上 |

心跳消费：`useA2AAgents`（30s 轮询网关 /v1/admin/a2a/agents，ADR-002 硬约束②）。

## 12 小时钟盘

AI Family 中心的**时段可视化**（FamilyHome 按小时问候/时钟环视图，getGreeting 六时段：夜/晨/上午/午/下午/晚）。术语「12 小时」指全天时段盘面，非 12 个组件。

## 引擎与基础设施

| 术语 | 定义 | 关联 |
| --- | --- | --- |
| 智能补全引擎 | 五维协同源（静态表/节点/env/路由/历史频率）+ 频率闭环的终端补全 | ADR-010 |
| 四源设备清单 | 网关上游池/Ollama 节点/NAS 网关本体/A2A Agent 容器的归一化节点 | device-inventory.ts · ADR-002 硬约束① |
| gw 代理 | `/console/gw/*` 服务端转发（GW_ADMIN_KEY 注入，浏览器零密钥） | CONTRACTS §7 |
| WS 中继 | `/console/ws/monitor` 手写 RFC 6455 帧（metrics 翻译） | ADR-005/007 |
| 真实化铁则 | 无数据源 KPI 显「—」禁造数；gpuUtil 由节点聚合推导例外 | gateway-adapter |
| 熔断态机 | closed→open→half-open（前端 breaker 展示） | gateway-adapter |
| AppError / traceId | 结构化错误 + 全局追踪 8 位标识 | TRACING.md |
| 降级契约 | 无 IDB 时 yyc3-storage 读→[] 写静默（hooks 依赖此工作） | ADR-011 |
| 双旗标 | noUncheckedIndexedAccess + exactOptionalPropertyTypes | ADR-013 |
| 四基线棘轮 | size/knip/color/dup 只减不增 | ADR-012 |
| 元门禁 | guardrail-probe 植入违规断言拦截（20 探针） | ADR-004 |
| 双形态 | LAN(server.mjs:3118) + 公网(console-server+HMAC) | ADR-005/006 |
| 同源形态 | VITE_BASE=/console/ 子路径单服务（Pages 之外的自托管） | ADR-001/S11 |
| bundle 双产物 | dist（根）+ dist-console（子路径）+ SW 90 项预缓存 | S12 |
| supply-chain 策略 | pnpm catalog 锁版本/provenance 守卫/overrides 注释纪律 | 红线④ |
