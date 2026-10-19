# 告警规则 — YYC³ 可观测（P0-P3 分级）

> 现役 7 条生产规则（Prometheus /api/v1/rules 实测）全部收录并补分级/路由/Runbook 映射；
> 客户端面告警（console-audit / 门禁）作为 C 级补充。路由通道：Alertmanager :9093（容器内网）→ webhook。

## 分级定义

| 级别 | 语义 | 响应 | 复盘 |
| --- | --- | --- | --- |
| P0 | 安全事件 / 数据损坏 / 全量不可用 | 立即（含夜间） | 必须复盘 |
| P1 | 核心功能不可用（网关全挂/模型全失联） | ≤30min | 必须复盘 |
| P2 | 降级/单点（单模型失联/RedisDown/依赖抖动） | 工作时间 | 建议记录 |
| P3 | 趋势预警（心跳龄增长/容量） | 值守巡检 | 可选 |

## 生产现役规则（7 条）

### RegistryRollbackTriggered — **P0**

- 触发：`increase(yyc3_registry_rollback_total[5m]) > 0`
- 语义：模型热更新触发自动回滚（配置/权重回退已发生）
- 路由：critical · 自动动作：无（回滚已由网关执行）· 处置：Runbook T4 + 后端 registry 日志核对回滚原因
- 抑制：无 · 复盘：必须（P0）

### RegistryModelReadyLost — **P1**

- 触发：`yyc3_registry_model_ready == 0 and on(model_id) yyc3_registry_model_heartbeat_age_seconds >= 0`
- 语义：某 model_id ready 位清零（实例失联且心跳存在过）
- 路由：critical · 处置：FAULT-TREE T4 + 后端模型实例重启 · 复盘：必须（P1）

### RegistryModelHeartbeatStale — **P2**

- 触发：`heartbeat_age_seconds > 120`
- 语义：模型心跳超时（120s 阈值，生产规则实况）
- 路由：alerts · 处置：模型实例健康（T4）· 抑制：RegistryModelReadyLost（失联升级版优先）
- 复盘：建议

### BackendErrorRateHigh — **P1**

- 触发：`sum by (upstream) (rate(yyc3_backend_requests_total{code=~"5.."}[5m])) / sum by (upstream) (rate(yyc3_backend_requests_total[5m])) > 0.05`（5m 错误率 >5%）
- 路由：critical（>15% 升 P0：全 upstream 不可用）· 处置：Runbook T3/T4（上游实例/网络/配额）
- 复盘：P0 级必须

### RedisDown — **P1**

- 触发：`yyc3_redis_up == 0`
- 路由：critical · 处置：FAULT-TREE T4（redis 容器/依赖）· 影响：网关降级路径（缓存miss 直连 PG）
- 复盘：必须（P1）

### RedisMetricsGap / RegistryMetricsGap — **P2**

- 触发：`absent(yyc3_redis_up)` / `absent(yyc3_registry_model_heartbeat_age_seconds)`
- 语义：指标消失（exporter 挂/抓取断）——比 0 更糟（观测盲区）
- 路由：alerts · 处置：容器/抓取链路（prometheus targets 页）· 抑制：对应 Down 类（先见 Down 不重复报 Gap）

## 客户端面告警（C 级补充，非 Prometheus 通道）

| 信号 | 级别 | 通道 | 处置 |
| --- | --- | --- | --- |
| console-audit.log login_fail 密度（>20/5min） | P2 | SSH 巡检 / ops.mjs | T2 + 考虑封禁 IP |
| AppError.traceId 新增 critical | P2 | getErrorLog() / ErrorBoundary 报告 | T9 |
| guardrail-probe 失败 | P1 | CI 红 | T7（门禁失效=假绿风险） |
| color/dup/size/knip 基线 FAIL | P2 | CI 红 | ADR-012 处置 |

## 增强候选（后端清单）

active_requests gauge · breaker_open_count（服务端熔断指标化）· gpu_utilization/gpu_memory_used（节点 exporter）——见 METRICS-DICT 现状差距节。
