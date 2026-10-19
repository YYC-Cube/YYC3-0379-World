# 仪表盘清单 — YYC³ 可观测（生产实况 + 规划）

## 现役（Grafana :3000，生产实况）

| 仪表盘 | 面板要点 | 数据源 | 刷新 |
| --- | --- | --- | --- |
| 网关总览（Grafana 实例内） | http_requests_total 速率 / duration p95 / 5xx 比例 / process_* 资源 | Prometheus (yyc3-gateway) | 15s |
| 模型注册心跳 | yyc3_registry_model_ready 各 model_id 位 / heartbeat_age_seconds 时序 | 同上 | 15s |
| 依赖健康 | yyc3_redis_up / targets up（prometheus 自监控） | 同上 | 15s |
| 告警概览 | 7 条现役规则状态（inactive/pending/firing 分色） | Prometheus API /alerts | 手动 |

> 面板查询即 METRICS-DICT 示例查询；现役仪表盘为 Grafana 内手工面板，导入导出 JSON 属运维增强（backlog）。

## 前端看盘形态（B 端 Dashboard，非 Grafana）

| 页面 | 面板 | 数据通道 |
| --- | --- | --- |
| /（数据监控） | QPS/Latency/活跃节点/GPU/Token 吞吐/存储 六卡 + 吞吐面积图 + 模型饼图 + 雷达 | WS system_stats/node_status（gpuUtil 节点聚合 L-12a） |
| /patrol | 巡查健康度/统计卡 | usePatrol（IDB 历史） |
| /audit | 操作审计 + request_id 检索（R7） | /console/gw/v1/logs |
| /security | 安全监控面板 | SecurityMonitor（127 处色值已 token 化片区） |

## 规划（backlog，触发即做）

| 仪表盘 | 面板 | 依赖 |
| --- | --- | --- |
| SSE TTFT 专项 | yyc3_backend_ttft_seconds p50/p95/p99 曲线 + upstream 分组 | 无（指标在位） |
| 错误预算燃尽 | SLO 三条（网关可用性/延迟/TTFT）剩余预算 | SLO.md 定义后 |
| 熔断面板 | breaker_open_count（待服务端指标化） | METRICS-DICT 差距清单 |
