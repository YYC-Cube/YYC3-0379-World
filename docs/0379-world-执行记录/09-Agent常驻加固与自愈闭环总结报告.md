---
file: 09-Agent常驻加固与自愈闭环总结报告.md
description: 0379-World 稳态期 TOP3——systemd 常驻 + OOM recreate + canary 退役 + 心跳观测 + 自愈回升 - 2026-09-28
author: AI Tutor <yyc3-expert>
version: v1.0.0
created: 2026-09-28
updated: 2026-09-28
status: stable
tags: [summary],[systemd],[oom-mitigation],[heartbeat-watch],[self-healing]
category: report
---

# 📋 Agent 常驻加固 + OOM 缓解落地 + 心跳观测与自愈闭环总结报告

## 一、TOP1：systemd 常驻加固 ✅

双模板入库 [deploy/nodes/](../../deploy/nodes/)：root 版（`/opt` + system 单元）/ user 版（`%h` + linger，免 sudo 节点）。两者均 `Restart=always` + `TimeoutStopSec=45`（留优雅 offline 窗口，TTL 300s 兜底）。

| 节点 | 接管方式 | 状态 |
| ---- | -------- | ---- |
| yyc3-101（免密 sudo） | system 单元 ×3 | ✅ active + **enabled（开机自启）** |
| yyc3-102（无免密 sudo） | user 单元 ×2 | ✅ active；**Linger=no**——待用户执行一条：`sudo loginctl enable-linger <user>` |

## 二、TOP2：dsv4-head OOM recreate ✅（停服窗口 ~5 分钟）

原容器全参数勘定（host 网络/`--gpus all`/shm 16g/NCCL env×3/model+脚本 bind/`bash /h.sh`）→ 同参数重建 + 两项新增：`RAY_memory_usage_threshold=0.95` + `--memory-reservation 100g`（原 **mem_limit=0 全无限制** = OOM 根因面；不设低 limit——权重靠 page cache，cgroup 限低反杀引擎）。重建后 :8001 200，agent 自动跟随回归。

## 三、TOP3a：canary 定论与退役 ✅

实勘颠覆预判：`dsv4-head-canary` = **alpine + `while true; do sleep 60; done` 纯空壳**（零流量/零端口/零 GPU）——非内存压力源（~4MB），名不副实的占位容器。处置：`docker stop` + rename `z-retired-canary-0928`（保守可逆；确认无用后可 rm）。

## 四、TOP3b：心跳断流观测 ✅

[model_registry_svc.py](../../core/api/services/model_registry_svc.py) 新增观测循环（30s）：
- **Gauge×2**（`yyc3_registry_model_heartbeat_age_seconds` / `_ready`，按 model_id/node_id）→ 默认 registry → instrumentator `/metrics` 自动暴露 → **NAS Prometheus（job=yyc3-gateway，15s 抓取）自动采集**（20 series 实证）
- **断流翻转告警**（stale↔healthy 各一次，去抖）→ logger.warning → **Loki 既有链** → Grafana 可查可挂通道；阈值 120s（4 心跳周期，早于 TTL 300s 摘除）
- Prometheus 告警规则文件留候选（NAS prometheus-conf 为 named volume，规则手术需另开窗口——指标已可查，Grafana Explore 即用）

## 五、事故复盘 → 自愈能力固化（本轮最有价值产出）🚨

**事故**：TOP1 部署时 `pkill` 旧 nohup agents → 旧 agent 的 SIGTERM 优雅 offline PATCH **晚于**新 agent 的 set ready 到达 → 五模型 state 固化 `offline`；心跳照常（仅表健康）但 `registry_upstreams` 要求 ready → **startup merge 0 / 池空**（误诊两轮：hb_age 字段误读 + 以为心跳断，最终网关日志实证心跳一直 200）。

**根因**：心跳语义只覆盖「健康」，不覆盖「在线承接」的状态回升——竞态写入无人纠正。

**修复（5d412fd）**：`heartbeat()` SQL CASE 自愈回升 `offline→ready`（**draining 排空态除外**——运维意图不被心跳覆盖）+ `was_offline` 时发 updated 事件 → **Phase B 重合并入池**。

**生产实证（全链自动，零人工）**：部署后五模型心跳到达 → state 逐个回升 → 日志 `重合并 3→4→5 上游` → 池内 5 registry 条目回填 → 旗舰 chat 200。**本事故本身被新能力自愈**——此类状态固化自此永久免疫。

## 六、门禁与统计

| 门禁 | 结果 |
| ---- | ---- |
| 快层全量 | ✅ 148 passed |
| integration（registry 系） | ✅ 26+8 passed（含自愈回升×3/观测×2 新用例） |
| 生产 | 五心跳 ready / 池 5 条 / 指标 20 series / chat 200 |

提交：`7946f76`（TOP3 三件）→ `5d412fd`（自愈回升修复），均已推 main 并 NAS 部署验证（NAS→GitHub 间歇抖动均重试成功）。

## 七、遗留与下轮建议

1. **[P2→用户一条命令]** 102 linger：`sudo loginctl enable-linger <user>`（开机自启收尾）
2. **[P3]** Prometheus 告警规则文件（heartbeat_age>120 → alert；需 prometheus-conf volume 手术窗口）
3. **[P3]** z-retired-canary-0928 确认后 `docker rm`
4. **[P3]** Agent 日志轮转（logrotate 或 systemd journal 转发）

---

**报告状态**: ✅ 稳态期 TOP3 全闭环 + 自愈能力固化
**生产终态**: NAS @5d412fd；五服务 systemd 心跳常驻；池 5+7；指标/告警链就绪
