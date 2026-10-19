# Tracing — traceId 规范与全链路串联（L-05 / R7）

## 标识族谱（三锚点，各自独立但有对齐通道）

| 锚点 | 生成方 | 形态 | 载体 | 消费方 |
| --- | --- | --- | --- | --- |
| **AppError.traceId** | 前端 captureError（自动 8 位 randomUUID 短标识 / options 注入优先） | 8 位 hex 或具名串 | AppError（IDB yyc3_error_log）+ ErrorBoundary 复制报告「追踪:」行 | 错误排查 / getErrorLog 过滤 |
| **网关 request_id** | 后端为每请求生成（响应日志/流水） | 服务端格式 | /v1/logs 流水（GatewayAuditLog.request_id） | /audit 页 traceRequestId 精确检索（R7） |
| **console 审计事件** | console-server auditLog | JSONL {ts,event,ip} | console-audit.log | 登录/登出审计（无请求粒度） |

## 对齐通道（现状与边界）

1. **同侧串联**：同一 AppError 内 id+traceId+timestamp+source+userAction 天然绑定；同一请求流水内 request_id+latency+tokens 天然绑定。
2. **跨侧对齐（时间+source 近似）**：前端 fetch 失败拿不到网关侧 request_id（它在响应日志里，失败时无响应）——因此跨侧检索按 `timestamp±窗口 + source（useGatewayAudit 等具名调用点）` 近似匹配。
3. **注入预留**：网关支持 `X-Request-ID` 类头时，前端可在 lib/http.ts 请求头注入 traceId → 网关流水回显 → 双侧同键精确串联（后端验收即触发升级，见 METRICS-DICT 差距清单）。

## 复制报告串联实例（用户报障流程）

```
用户 ErrorBoundary 点「复制错误报告」→
  错误ID: err_1729...  追踪: a1b2c3d4  分类: RUNTIME  消息: ...
值守 → getErrorLog() 或 localStorage yyc3_error_log 过滤 traceId === 'a1b2c3d4'
     → 取 source（如 useGatewayAudit）+ timestamp → /audit 页按时间窗检索网关流水
```

## 生成规则

- 前端：`globalThis.crypto.randomUUID().slice(0, 8)`（jsdom/node 兼容回退 generateErrorId 尾 6 位）；
- 注入：`captureError(err, { traceId: gatewayRequestId })` 时以注入值覆盖（精确串联优先）；
- 禁止：traceId 承载用户标识（PII 红线，S6 维度 7）。
