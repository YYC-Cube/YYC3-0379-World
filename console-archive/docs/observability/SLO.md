# SLO / SLI / 错误预算 — YYC³ 可观测

> 基线原则：目标值取**当前实测水位+合理余量**（非空想）；预算耗尽动作 = 冻结非修复类发布（特性暂停，修复/回滚不受限）。

## SLO-1 · 网关可用性

- **SLI**：`1 - (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))`（按 5m 窗口滚动求占比）
- **目标**：≥ 99.5%（本地闭环形态；公网经 Traefik 单链，不含终端网络）
- **窗口**：30 天滚动
- **错误预算**：月度 0.5% ≈ 3.6h 5xx 当量
- **熔断策略**：预算耗尽 → P1/P2 特性发布冻结 + FAULT-TREE T4 专项
- **关联告警**：BackendErrorRateHigh（P1/P0 通道）

## SLO-2 · 网关延迟

- **SLI**：`histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))`
- **目标**：p95 < 1s（非流式 API；当前基线均值域远低于此，首周校准后固化为正式值）
- **窗口**：30 天滚动
- **错误预算**：p95 超标请求占比 < 5%（半小时颗粒观测）
- **熔断策略**：预算耗尽 → 性能回归专项（bundle-stats + Lighthouse 联查）
- **关联告警**：延迟阈值 warning/danger（METRICS-DICT）

## SLO-3 · 流式首 Token（SSE TTFT）

- **SLI**：`histogram_quantile(0.95, sum by (le) (rate(yyc3_backend_ttft_seconds_bucket[5m])))`
- **目标**：p95 < 2s（体验线；上游模型冷启动容忍单次超）
- **窗口**：30 天滚动
- **错误预算**：超标请求占比 < 5%
- **熔断策略**：预算耗尽 → 上游实例/配额专项（T3/T4）
- **关联告警**：TTFT warning/danger 阈值

## SLO-4 · 模型注册可用性

- **SLI**：`avg_over_time(yyc3_registry_model_ready[30d])`（全模型按位平均）
- **目标**：≥ 99%
- **窗口**：30 天滚动
- **错误预算**：单模型失联月累计 < 7.2h
- **熔断策略**：预算耗尽 → 模型实例稳定性专项（心跳/重启策略）
- **关联告警**：RegistryModelReadyLost(P1) / HeartbeatStale(P2)

## 客户端面 SLO-C（console 服务，无 Prometheus 自动 SLI——人工巡检承载）

| 项 | SLI | 目标 | 检测 |
| --- | --- | --- | --- |
| NAS console 可用 | ops.mjs verify 七项 | 7/7 | 值守清单每日 |
| ECS console 可用 | auth/status + 审计流 | enabled + 事件在写 | 值守清单每日 |
| 登录成功率 | audit login_ok/(ok+fail) | ≥95%（排除自测错误密码） | 周Inspect |

> 升级路径：接入 Prometheus blackbox/mtail 后 SLO-C 转自动 SLI（backlog）。
