---
file: 05-监控告警与Runbook.md
description: 模型接入监控告警与运维 Runbook - 指标矩阵 / 告警规则 / SOP / 故障排查
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-09-27
updated: 2026-09-27
status: active
tags: [spec],[observability],[runbook],[sop],[alerting]
category: spec
---

# 监控告警与运维 Runbook

> 现状监控（✅）：网关 `/metrics`（prometheus-fastapi-instrumentator）+ `/healthz` 探活 + Grafana/Prometheus/Loki 监控栈（NAS 生产已部署，A2A 审计已入 Loki）。
> Registry/模型实例级指标与告警规则（📋）依赖 [02](02-Registry目标架构.md) 落地。

## 1. 三层健康检查

| 层 | 端点/机制 | 状态 | 周期 |
| --- | --- | --- | --- |
| 网关层 | `/healthz` 轻量探活 + `/health` 完整检查 | ✅ 生产 | auto-deploy 部署后轮询 |
| 模型实例层 | 上游 `health_path`（默认 `/health`）主动验活 | ✅ 生产（降级权重×0.5） | 网关内置周期 |
| 注册中心层 | 心跳 TTL 三级阶梯（90s/180s/300s） | 📋 规划 | 30s 上报 |

## 2. 核心监控指标

### 2.1 现有网关指标（✅，instrumentator 自动暴露）

`http_request_duration_seconds` / `http_requests_total` 等标准指标；A2A 面已有 `x-a2a-cost` 直报与 spend_logs 落库。

### 2.2 规划指标（📋 Registry 落地后接入 Prometheus）

| 指标 | 说明 | 告警阈值参考 |
| --- | --- | --- |
| `model_backend_latency_ms` | 模型推理延迟 p95 | >2000ms 告警 |
| `model_backend_error_rate` | 模型后端错误率 | >10% 告警 |
| `active_requests` | 实例并发 | 超 max_batch_size 告警 |
| `gpu_utilization` / `gpu_memory_used` | GPU 利用率/显存 | >95% 持续 5min / >90% 告警 |
| `model_instance_heartbeat_status` | 心跳状态（📋） | 丢失告警 |
| `registry_sync_lag_seconds` | 网关-Registry 同步延迟（📋） | >60s P1 |
| `sse_ttft_p95` | 流式首字节 | >3000ms P1 |
| `breaker_open_count` | 熔断数（📋 事件回写） | >3 P2 |
| `rollback_triggered_total` | 回滚触发（📋） | >0 P0 |

### 2.3 告警渠道

Grafana 告警（✅ 栈已部署）→ webhook 通知（A2A 死信/孤儿/回收停滞 3 条规则已配置）；规划接入分级路由：

```
P0 → critical 渠道（服务不可用：立即响应）
P1 → alerts 渠道（性能退化）
P2 → alerts 渠道（观察）
P3 → info 渠道（记录）
```

> 原 MRS 的「8 位家人视角告警规则」全文见归档件 §9.2，落地时按 owner 域取用，规则阈值并入上表。

## 3. SOP-01 · 新模型接入（现状通道版）

**负责人**：模型部署工程师 · 预计 4-8 小时

```
Step 1 · 资产入库（30min）
  □ 权重放入 NAS 仓库（/Volume1/yyc3_hd/data/家族/模型/snapshots/版本）
  □ 完整性校验三项（分片对账/头部 magic/配置存在）——校验失败禁止上线

Step 2 · 同步到算力节点（30min-2h，视体积）
  □ rsync 至节点本地 NVMe SSD（📋 model_sync_to_node.py 落地后替换）
  □ 校验同步后分片数一致

Step 3 · 启动推理服务（30min）
  □ vllm serve <本地SSD路径> --served-model-name <model_id> --port <独立端口>
  □ 本地验证 /v1/models /health

Step 4 · 配置网关上游（15min）
  □ .env OPENAI_COMPATIBLE_UPSTREAMS 追加条目（models 模式含新 model_id）
  □ 重启/热载网关；确认解析无告警（解析失败静默空池）

Step 5 · 冒烟验收（30min）
  □ 01 文档 §5 八项用例全过

Step 6 · 开放公网 + 归档
  □ 更新《YYC3-Models-资产详情.md》
  □ 记录上线日志
```

**回滚预案**：env 移除该上游条目 + 重启网关（现状通道秒级生效）。

## 4. SOP-02 · 模型热切换（📋 Registry 落地后启用）

```
前置：新版本已过影子验证 + 质量门禁（03 文档 §6）
模式选择：小版本→Canary（2-4h）；大版本→蓝绿（≤10min）
执行：03 文档 §3.5 别名切换五步
验收：切换期 0 请求失败 / P95 ≤ baseline×1.15 / 错误率 <0.5%
```

## 5. SOP-03 · 紧急回滚

```
现状通道（✅）：
  1. .env 注释/移除问题上游条目（或切 fallback_url）
  2. 重启网关 → 路由摘除
  3. 验证 /healthz + 冒烟
  4. 记录事件日志

规划通道（📋 Registry）：
  POST /registry/v1/models/{id}/rollback {"auto": true}
  → 别名切回上一稳定版本 ≤30s，P0 场景自动触发
```

## 6. 故障排查清单（合并两源）

| 现象 | 排查点 | 状态 |
| --- | --- | --- |
| 新模型公网 /v1/models 不可见 | ① env JSON 合法性（解析失败静默空池）② 网关是否重载 ③ base_url 连通性 | ✅ 现状 |
| 调用 503 上游不可用 | ① 上游 /health ② 熔断摘除（30s 半开自愈）③ fnmatch 匹配 ④ 网络 | ✅ 现状 |
| 冷启动加载极慢 | 是否 NFS 直挂；切换本地 SSD | ✅ 现状 |
| safetensors invalid header | 分片损坏，NAS 重同步该分片 | ✅ 现状 |
| Registry 不可达 | 网关 fallback env 是否生效；检查 Registry 服务 | 📋 规划 |
| 心跳丢失标 degraded | 检查模型节点网络；心跳上报进程 | 📋 规划 |
| 别名切换后流量未更新 | Registry 事件推送；网关订阅状态；手动刷新路由缓存 | 📋 规划 |
| 熔断频繁 | 上游稳定性；阈值调优（现状固定 3 次/30s） | ✅ 现状 |

## 7. 安全基线（引用）

- 三级认证：公网 API Key（sk-/vk- vk 链）/ 内部 mTLS（📋）/ 管理 JWT+RBAC（现状 ADMIN_API_KEYS）——对齐 [02](02-Registry目标架构.md) §3.2 认证说明
- 审计必记事件：model.registered/updated/deregistered/switched/rolled_back、agent.*/auth.failed（📋 落库；A2A 审计已 ✅ 入 Loki）
- 合规映射（ISO 27001/SOC 2/GDPR 控制项对照表）见归档件 §11.4

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0.0 | 2026-09-27 | 两源监控/SOP/排查表合并去重，逐条标注 ✅/📋；SOP-01 重写为现状通道可执行版（原版依赖未实现端点） |
