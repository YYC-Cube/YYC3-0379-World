---
file: 05-监控告警与Runbook.md
description: 模型接入监控告警与运维 Runbook - 指标矩阵 / 告警规则 / SOP / 故障排查
author: YanYuCloudCube Team <admin@0379.email>
version: v1.4.0
created: 2026-09-27
updated: 2026-10-05
status: active
tags: [spec],[observability],[runbook],[sop],[alerting]
category: spec
---

# 监控告警与运维 Runbook

> 现状监控（✅）：网关 `/metrics`（prometheus-fastapi-instrumentator）+ `/healthz` 探活 + Grafana/Prometheus/Loki 监控栈（NAS 生产已部署，A2A 审计已入 Loki）。
> Registry 心跳指标与断流告警已落地（✅ 09-28：心跳年龄指标 + 120s 断流翻转告警，规则文件 [registry-heartbeat.rules.yml](../../deploy/nas/prometheus-rules/registry-heartbeat.rules.yml)）；GPU/延迟/同步滞后等实例级指标仍为 📋。

## 1. 三层健康检查

| 层 | 端点/机制 | 状态 | 周期 |
| --- | --- | --- | --- |
| 网关层 | `/healthz` 轻量探活 + `/health` 完整检查 | ✅ 生产 | auto-deploy 部署后轮询 |
| 模型实例层 | 上游 `health_path`（默认 `/health`）主动验活 | ✅ 生产（降级权重×0.5） | 网关内置周期 |
| 注册中心层 | 心跳 TTL 三级阶梯（90s/180s/300s） | ✅ 已落地（09-28） | 30s 上报（注册 Agent `DEFAULT_INTERVAL=30`） |

## 2. 核心监控指标

### 2.1 现有网关指标（✅，instrumentator 自动暴露）

`http_request_duration_seconds` / `http_requests_total` 等标准指标；A2A 面已有 `x-a2a-cost` 直报与 spend_logs 落库。

### 2.2 规划指标（📋；✅ 心跳状态已接入）

| 指标 | 说明 | 告警阈值参考 |
| --- | --- | --- |
| `model_backend_latency_ms` | 模型推理延迟 p95 | >2000ms 告警 |
| `model_backend_error_rate` | 模型后端错误率 | >10% 告警 |
| `active_requests` | 实例并发 | 超 max_batch_size 告警 |
| `gpu_utilization` / `gpu_memory_used` | GPU 利用率/显存 | >95% 持续 5min / >90% 告警 |
| `model_instance_heartbeat_status` | 心跳状态（✅ 已落地：心跳年龄指标 + 120s 断流翻转告警，registry-heartbeat.rules.yml） | 丢失告警 |
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

### 2.4 容器日志外送（✅ 双节点试点已通，2026-10-05 当日落地）

> 背景：dsv4 旗舰启动崩溃环排障（2026-10-05，六天心跳停滞）中，原始崩溃日志随容器重建丢失，根因还原只能依赖排障现场实抓——生产容器日志无外送是已暴露的观测盲区。

| 项 | 现状（✅ 试点） |
| --- | --- |
| 链路 | docker 日志 → fluent-bit 3.1 **tail + Path_Key + lua**（[docker-compose.logging.yml](../../deploy/dgx/docker-compose.logging.yml) + [fluent-bit.conf](../../deploy/dgx/fluent-bit.conf) + [cn.lua](../../deploy/dgx/cn.lua)）→ Tailscale → NAS Loki `100.65.172.88:3100` |
| 部署 | ✅ **管理机一键** [deploy-container-map-remote.sh](../../deploy/dgx/deploy-container-map-remote.sh)（批量同步七件套 + 远程执行 + 汇总；默认 yyc3-n1/n2，可传节点名；管理机 bash 3.2 兼容）→ 节点侧自包含 [setup-container-map.sh](../../deploy/dgx/setup-container-map.sh)（幂等五步：文件校验/Loki 探测/timer 安装/compose 部署/映射注入+三重验证；NODE_ID 自动探测）；yyc3-101/102 已用一键脚本部署；镜像源 `docker.1ms.run`（daocloud 该镜像拉取停滞） |
| 保留 | ✅ Loki 30 天保留（[loki-config.yaml](../../deploy/nas/loki-config.yaml)：retention 744h + compactor retention_enabled；loki 以 root 运行——NAS ACL 拒 UID10001 读 bind-mount 配置的权衡，仅 Tailscale 暴露） |
| 看板/告警 | ✅ **已灌入**（10-05，一键脚本 [import-grafana-dashboards.sh](../../deploy/nas/import-grafana-dashboards.sh)：Loki 数据源幂等补建 + 看板 API 导入 overwrite 幂等，密码经 SSH 读取不落盘；实测 uid=`yyc3-dgx-logs` v2）；全量流 + 崩溃关键字（`died unexpectedly\|Traceback\|RuntimeError`）双 panel；告警在 Grafana Alerting 按崩溃查询创建规则即可 |
| 标签 | ✅ **container_name 真名已上线**：tail + `Path_Key` + [cn.lua](../../deploy/dgx/cn.lua) v2（12 位短 ID + id→name 映射表 300s 自刷新，[container-map.timer](../../deploy/dgx/container-map.timer) 每 5 分钟 docker cp 注入）；series 实证 `container_name:"yyc3-embedding"` 等真名 |

## 3. SOP-01 · 新模型接入（现状通道版）

**负责人**：模型部署工程师 · 预计 4-8 小时

```
Step 1 · 资产入库（30min）
  □ 权重放入 NAS 仓库（/Volume1/yyc3_hd/data/家族/模型/snapshots/版本）
  □ 完整性校验：core/scripts/model_asset_verify.py <模型目录>（✅ 三项自动检查 + model_checksum.report，失败禁止上线）

Step 2 · 同步到算力节点（30min-2h，视体积）
  □ core/scripts/model_sync_to_node.py --dry-run 预检 → 执行同步至节点本地 NVMe SSD（✅ 09-28 落地）
  □ 校验同步后分片数一致（--plan 输出 already_synced/待传/续传清单）

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

## 3.5 SOP-04 · 归档模型上线触发卡（P1-2 常态化通道，✅ 2026-10-05）

> 前提：模型已在 Registry 归档态（`tags: nas-archive`，`weights_path` 已挂接，28 条任选）。
> 本卡把 SOP-01 压缩为 Registry 侧五命令触发路径；资产同步与 vLLM 拉起沿用 §3 Step1-3。

```bash
# 0. 预检（可选）：确认归档记录与权重路径
curl -s -H "X-API-Key: $KEY" .../registry/v1/models/<model_id> | jq '{state,enabled,weights_path}'

# 1. 资产校验（NAS/节点本地）
python3 core/scripts/model_asset_verify.py <weights_path>            # 退出码 0 = 门禁通过

# 2. 同步节点 + 启动 vLLM（§3 Step2-3；注册 Agent systemd 拉起自动注册+心跳）
#    deploy/nodes/yyc3-registry-agent@.service + --contract-port

# 3. 上线置位（Agent 自动 ready 则跳过；手动兜底）
curl -X PATCH .../registry/v1/models/<model_id> -H "X-API-Key: $KEY" \
  -d '{"enabled": true, "state": "ready"}'

# 4. 冒烟（§5 九用例）→ 核对 X-YYC3-Upstream 指向新实例

# 5.（可选）别名接管公网名，旧模型退为备份（回滚 = PUT 切回）
curl -X PUT .../registry/v1/aliases/<公网名> -H "X-API-Key: $KEY" \
  -d '{"model_id": "<model_id>", "reason": "归档模型上线"}'
```

**回滚**：drain 新实例 → 别名 PUT 切回旧 model_id（≤30s）→ PATCH 新实例 `enabled=false, state=offline` 归档。

## 4. SOP-02 · 模型热切换（✅ Canary 半自动闭环可用，脚本封装 [canary-manage.sh](../../scripts/canary-manage.sh)）

```
灰度：scripts/canary-manage.sh set <model> <canary_id> 5        # 起步 5%
扩量：scripts/canary-manage.sh promote <model> 10|30|50|100     # 观察 P0 指标逐步
回退：scripts/canary-manage.sh rollback <model>                 # 紧急 weight=0（另：2min 内失败≥5 次自动回退）
定版：scripts/canary-manage.sh finalize <model>                 # alias 正式切换 + DELETE canary
Shadow 采样：set 时附第 4 参 shadow_model（复制流量仅记指标）
```

## 5. SOP-03 · 紧急回滚

```
现状通道（✅）：
  1. .env 注释/移除问题上游条目（或切 fallback_url）
  2. 重启网关 → 路由摘除
  3. 验证 /healthz + 冒烟
  4. 记录事件日志

Registry 通道（✅ 端点已落地：rollback + 别名切回）：
  POST /registry/v1/models/{id}/rollback {"auto": true}
  → 切回上一稳定版本；P0 硬条件自动触发（错误率/延迟）仍为 📋，当前人工触发
```

## 6. 故障排查清单（合并两源）

| 现象 | 排查点 | 状态 |
| --- | --- | --- |
| 新模型公网 /v1/models 不可见 | ① env JSON 合法性（解析失败静默空池）② 网关是否重载 ③ base_url 连通性 | ✅ 现状 |
| 调用 503 上游不可用 | ① 上游 /health ② 熔断摘除（30s 半开自愈）③ fnmatch 匹配 ④ 网络 | ✅ 现状 |
| 冷启动加载极慢 | 是否 NFS 直挂；切换本地 SSD | ✅ 现状 |
| safetensors invalid header | 分片损坏，NAS 重同步该分片 | ✅ 现状 |
| Registry 不可达 | env 池恒为兜底（merge 失败不影响 env 通道）；检查 Registry 服务与 REGISTRY_ENABLED | ✅ 现状 |
| 心跳丢失标 degraded | 检查模型节点网络；注册 Agent 心跳进程（TTL 90/180/300 阶梯，断流告警 120s） | ✅ 现状 |
| 别名切换后流量未更新 | `alias_switched` 事件（SSE + Redis stream）；网关订阅状态；`resolve_alias` 内存路由表事件刷新 | ✅ 现状 |
| 熔断频繁 | 上游稳定性；阈值调优（现状固定 3 次/30s） | ✅ 现状 |

## 7. 安全基线（引用）

- 三级认证：公网 API Key（sk-/vk- vk 链）/ 内部 mTLS（📋）/ 管理 JWT+RBAC（现状 ADMIN_API_KEYS）——对齐 [02](02-Registry目标架构.md) §3.2 认证说明
- 审计必记事件：model.registered/updated/deregistered/switched/rolled_back、agent.*/auth.failed（📋 落库；A2A 审计已 ✅ 入 Loki）
- 合规映射（ISO 27001/SOC 2/GDPR 控制项对照表）见归档件 §11.4

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0.0 | 2026-09-27 | 两源监控/SOP/排查表合并去重，逐条标注 ✅/📋；SOP-01 重写为现状通道可执行版（原版依赖未实现端点） |
| v1.1.0 | 2026-10-05 | 状态刷新对齐 09-28 落地实况：§1 注册中心层心跳 / §2.2 心跳指标 + 断流告警 📋→✅；§3 SOP-01 Step1/2 脚本化；§4 SOP-02 别名通道可用（Shadow/Canary 仍 📋）；§5 SOP-03 Registry 通道端点已落地；§6 排查表三行 📋→✅ |
| v1.2.0 | 2026-10-05 | 新增 §2.4 容器日志外送规划（dsv4 崩溃环排障中原始日志随容器重建丢失的教训）：fluent-bit → NAS Loki 方案/覆盖面/保留策略 |
| v1.3.0 | 2026-10-05 | §2.4 转已落地：DGX 双节点 fluent-bit 3.1 部署（docker json 日志 tail → Tailscale → NAS Loki 3100），双流验证入库；部署物 [deploy/dgx/fluent-bit.conf](../../deploy/dgx/fluent-bit.conf) + [docker-compose.logging.yml](../../deploy/dgx/docker-compose.logging.yml)；待增强项标注 |
| v1.4.0 | 2026-10-05 | §2.4 增强：fluent-bit 切 docker input（sock 挂载，双节点零错误）；Loki 30 天保留 + compactor（loki-config.yaml，root 运行权衡）；Grafana 看板 dgx-container-logs.json + 崩溃关键字查询/告警指引；容器名标签实证受阻降级待增强（两候选路径）。新增 §3.5 SOP-04 归档模型上线触发卡（P1-2 常态化通道五命令 + 回滚） |
