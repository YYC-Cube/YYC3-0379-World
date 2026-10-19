# 结构化日志规范 — YYC³ 可观测

## 三端日志现状（实测形态）

| 端 | 载体 | 形态 | 保留 |
| --- | --- | --- | --- |
| NAS/ECS console-server | console-audit.log（部署目录旁） | **JSONL** `{ts, event, ip}` | 运维轮转（建议按月切，当前无自动轮转——backlog T13） |
| NAS 网关容器 | docker logs 0379-world-gateway-1 | 文本行（FastAPI/uvicorn 格式） | docker 轮转策略 |
| Loki | yyc3-loki :3100（Tailscale 面） | 30 天保留，job 标签形态（含 dgx-containers） | 30 天 |
| 浏览器 | localStorage `yyc3_error_log`（≤200 条 AppError） | 结构化对象（id/category/severity/message/traceId/…） | 容量淘汰 |
| pm2 | ~/.pm2/logs | 文本 | pm2 内建 |

## JSONL 事件字典（console-audit.log 实况）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| ts | ISO8601 | 事件时间（UTC） |
| event | 枚举 | login_ok / login_fail / logout（L-06 扩展点） |
| ip | string | 客户端地址（对公网为反代透传值时需 Traefik 配 X-Forwarded-For 透传） |

**PII 红线**：不承载用户标识/密码/token（S6 维度 7 实证零 PII）；traceId 类追踪标识允许。

## 级别语义（前端 AppError.severity 侧）

| 级别 | 语义 | 处置预期 |
| --- | --- | --- |
| info | 观测性事件 | 无需动作 |
| warning | 降级/兜底生效 | 巡检关注 |
| error | 功能失败但已兜底 | 按 traceId 排查 |
| critical | 未捕获/全局级（RUNTIME 全局监听默认值） | 立即排查 |

## 规范约定

1. **新增服务端事件** = 扩 event 枚举 + 本表登记（禁自由字符串事件名）；
2. **前端禁裸 console.***（App.tsx 噪声过滤块为唯一例外，S6 甄别）——错误一律 captureError（自带结构化字段 + traceId）；
3. **敏感零落盘**：密码/token/Cookie 值永不入日志（constantTimeEqual 比对不产生日志；审计只记事件与 ip）；
4. **网关侧文本日志**向 Loki 结构化收敛属后端增强候选（当前以 docker logs + Grafana Loki 数据源浏览）。
