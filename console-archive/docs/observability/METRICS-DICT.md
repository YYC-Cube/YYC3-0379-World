# 指标字典 — YYC³ 网关可观测指标（生产实测口径）

> 采集源: NAS 网关 `:8000/metrics`（FastAPI + prometheus-client）· Prometheus: yyc3-prometheus（job=yyc3-gateway, 15s 抓取）
> 实测快照: 2026-10-17 · `curl :8000/metrics` 全量族清单已核对（本文件不含虚构指标）
> 命名说明: 模板口径（http_requests_total 等）与生产实况（yyc3_* 前缀）的差异在「现状差距」节逐一映射。

## 一、流量与延迟（实测在位）

### http_requests_total

- 类型：Counter · 单位：count
- 标签：method / path / status（FastAPI 中间件维度）
- 来源：job="yyc3-gateway"（app 内建 instrumentation）
- 采集间隔：15s
- 阈值：warning — 速率环比 +300%（突增排查）；danger — 配合 5xx 比例
- 消费者：Grafana 流量面板 · BackendErrorRateHigh 告警分母
- 示例：`sum by (status) (rate(http_requests_total[5m]))`

### http_request_duration_seconds / http_request_duration_highr_seconds

- 类型：Histogram（highr 为高精桶变体）· 单位：seconds
- 标签：method / path
- 阈值：warning — p95 > 1s；danger — p95 > 2s
- 消费者：延迟面板 · SLO 网关延迟 SLI
- 示例：`histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))`

### yyc3_backend_requests_total

- 类型：Counter · 单位：count
- 标签：**upstream**（后端实例）/ code
- 来源：网关转发层（模型后端请求计数）
- 阈值：warning — 单 upstream 错误率 >5%（5m）；danger — >15%
- 消费者：BackendErrorRateHigh 告警（生产规则实况）· 上游健康面板
- 示例：`sum by (upstream) (rate(yyc3_backend_requests_total{code=~"5.."}[5m])) / sum by (upstream) (rate(yyc3_backend_requests_total[5m]))`

### yyc3_backend_ttft_seconds

- 类型：Histogram · 单位：seconds
- 标签：upstream / model
- 阈值：warning — p95 > 2s（流式首 token 体验线）；danger — p95 > 5s
- 消费者：SSE TTFT 面板（模板 sse_ttft_p95 的生产实体——秒为单位）
- 示例：`histogram_quantile(0.95, sum by (le) (rate(yyc3_backend_ttft_seconds_bucket[5m])))`

## 二、模型注册与心跳（实测在位，3 条活告警锚定）

### yyc3_registry_model_heartbeat_age_seconds

- 类型：Gauge · 单位：seconds
- 标签：model_id
- 阈值：warning — >120s（RegistryModelHeartbeatStale 生产规则）；danger — 配合 ready==0
- 消费者：RegistryModelHeartbeatStale / RegistryMetricsGap(absent) · AI Family 时钟页心跳（useA2AAgents 同源语义）
- 示例：`yyc3_registry_model_heartbeat_age_seconds > 120`

### yyc3_registry_model_ready

- 类型：Gauge（0/1 per model_id）
- 阈值：danger — ==0 且心跳龄 ≥0（RegistryModelReadyLost 生产规则）
- 消费者：模型可用性面板 · /v1/models 路由决策上游
- 示例：`yyc3_registry_model_ready == 0`

### yyc3_registry_rollback_total

- 类型：Counter · 单位：count
- 阈值：danger — increase(·[5m]) > 0（RegistryRollbackTriggered 生产规则）
- 消费者：热更新回滚审计 · P1 复盘必查
- 示例：`increase(yyc3_registry_rollback_total[5m]) > 0`

## 三、依赖健康（实测在位）

### yyc3_redis_up

- 类型：Gauge（0/1）
- 阈值：danger — ==0（RedisDown）；warning — absent（RedisMetricsGap）
- 消费者：依赖健康面板 · redis-down.rules 双告警
- 示例：`yyc3_redis_up == 0`

## 四、进程标准族（prometheus-client 自带，实测在位）

python_gc_* · python_info · process_cpu_seconds_total · process_resident_memory_bytes · process_open_fds / process_max_fds
- 阈值：warning — 内存 RSS > 1GB 或 fds > 80% 上限
- 消费者：容器资源面板

## 五、模板指标 ↔ 生产实况映射（现状差距，如实登记）

| 模板口径 | 生产实况 | 差距处置 |
| --- | --- | --- |
| http_requests_total | ✅ 同名在位 | — |
| http_request_duration_seconds | ✅ 同名在位（+highr 变体） | — |
| model_backend_latency_ms | ⚠️ 实为 yyc3_backend_ttft_seconds（秒） | 文档以实况为准 |
| model_backend_error_rate | ⚠️ 非独立指标，由 yyc3_backend_requests_total{code} 派生 | 记录 PromQL 派生式 |
| active_requests | ⚠️ 未暴露独立 gauge（可由 rate 推断活跃度） | 后端增强候选 |
| gpu_utilization / gpu_memory_used | ⚠️ /metrics 未暴露（节点级 GPU 数据在前端四源链路，非网关进程） | 需网关侧 exporter 才可纳管 |
| model_instance_heartbeat_status | ⚠️ 实为 yyc3_registry_model_ready + heartbeat_age_seconds 两件 | — |
| registry_sync_lag_seconds | ⚠️ 实为 heartbeat_age_seconds 同语义 | — |
| sse_ttft_p95 | ⚠️ 实为 ttft histogram 的 p95 派生 | — |
| breaker_open_count | ⚠️ 熔断态目前在前端 gateway-adapter（客户端态），服务端未出指标 | 后端增强候选 |
| rollback_triggered_total | ⚠️ 实为 yyc3_registry_rollback_total | — |

> 处置原则：**文档锚定实况，差距进后端增强清单**（不做无中生有的告警配置）。
