---
file: 07-dsv4-recover使用手册.md
description: dsv4-recover.sh 完整使用手册 - 旗舰 TP2 诊断/恢复/取证/守护五模式剧本
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-10-05
updated: 2026-10-05
status: active
tags: [ops],[dsv4],[recover],[runbook],[manual]
category: manual
---

# 📘 dsv4-recover.sh 使用手册

> **一句话**：`bash deploy/dgx/dsv4-recover.sh` 一条命令完成 dsv4 旗舰（deepseek-v4-flash，TP2 跨机）的健康诊断；崩溃时用同一脚本取证与恢复。
> **工具箱索引**：[06-运维脚本工具箱](06-运维脚本工具箱.md) · **背景事故**：2026-10-05 六天心跳停滞（根因矩阵见 [YYC3-Models-资产详情 v1.4.0](../架构与部署/YYC3-Models-资产详情.md)）

## 1. 前置条件

| 项 | 要求 |
| --- | --- |
| 执行位置 | 管理机 yyc3-22（仓库根目录） |
| SSH 免密 | `~/.ssh/config` 含 `yyc3-n1` / `yyc3-n2` / `yyc3-45` 条目（BatchMode 可连） |
| 覆盖节点名 | `N1=`/`N2=`/`GW=` 环境变量可覆盖默认 |
| 网络管理 | Tailscale 在线（GW 经 100.65.172.88 查 Registry） |
| 风险分级 | `check`/`rootcause`/`logs` **全只读随时可跑**；`recover`/`watch` 会重启容器（<1min 中断，需维护窗口） |

## 2. 五模式详解

### 2.1 `check` — 只读诊断（默认；无参数等价）

```bash
bash deploy/dgx/dsv4-recover.sh            # 无参数 = check
bash deploy/dgx/dsv4-recover.sh check
```

**输出四信号**：head 容器态（RestartCount 仅为生命周期累计，不作判据）· worker 容器态与重启策略 · vLLM 8001 健康码 · Registry `state`（**权威信号**：ready = TTL 90/180/300s 内有心跳，服务端判定）。

**判定**：`8001=200 && state=ready → ✅ 健康（exit 0）`；否则 `⚠️ 异常（exit 1）`。

**实测样例**（健康态）：

```
head : running RestartCount=1（RestartCount 为容器生命周期累计，恢复操作也会 +1）
worker: running RP=unless-stopped
8001  : 200
registry: "state":"ready"（state=ready 即心跳 TTL 内，服务端权威判定）
✅ 健康
```

### 2.2 `recover` — 编排时序恢复（崩溃处置主手段）

```bash
bash deploy/dgx/dsv4-recover.sh recover          # 已健康自动跳过
FORCE=1 bash deploy/dgx/dsv4-recover.sh recover  # 强制执行（跳过健康检查）
```

**时序**（TP2 跨机死锁解法，**顺序不可乱**）：

```
① head 停 → ② worker 清态起 → ③ head 起（等 GCS/Ray 就绪）
→ ④ 50s 后 worker 重启（对准 PG 注册窗口接入）
→ ⑤ 每 60s 探测 ×20 轮（日志特征判定就绪：APIServer 200 OK / /v1/models 200）
→ ⑥ Registry 转 ready 后 e2e 真实推理验证
```

**关键语义**（实战修正）：
- 加载窗口（约 8-12 分钟）内 **8001 必为 000，不可据端口判死**；以容器日志尾部特征判定（出现 `GET /health ... 200` 即就绪）
- `unless-stopped` 自愈闭环下**中途崩 1-2 轮属正常**（自愈拉起后重加载），仅持续 RC 增长 + 8001 持续 000 超 15 分钟才升级人工
- 完成后自动执行 **e2e 推理一发**（经网关全链路由，非直连）

### 2.3 `rootcause` — 崩溃取证（只读）

```bash
bash deploy/dgx/dsv4-recover.sh rootcause
```

五段取证 + 指引：

| 段 | 内容 | 排障用途 |
| --- | --- | --- |
| ① 生命周期 | head/worker Started/RC/OOM/Exit | 判崩溃时间线与是否 OOM |
| ② 错误特征段 | 近 2000 行内致命错误（died/Engine failed/RuntimeError/CUDA/NCCL） | 定位崩溃层级 |
| ③ 显存证据 | Model loading / Free memory / Available KV cache | 验证 rank0 显存挤穿（主因） |
| ④ Ray 集群 | ray status（节点/PG/Recent failures） | 查跨机注册与残留 |
| ⑤ Registry 判定 | /health（state + **heartbeat_age_seconds**） | 心跳新鲜度数值化 |

尾部输出：Loki 历史崩溃查询串（30 天外送）+ 根因矩阵文档锚点 + 处置建议。**实测**：一条命令还原当日两次崩溃（02:40:17 Executor failed → 02:43:13 ActorDiedError）全链证据。

### 2.4 `logs` — 快捷日志

```bash
bash deploy/dgx/dsv4-recover.sh logs head 50     # head 尾 50 行（默认 30）
bash deploy/dgx/dsv4-recover.sh logs worker 100
```

### 2.5 `watch` — 守护自愈循环

```bash
nohup bash deploy/dgx/dsv4-recover.sh watch 300 >> /tmp/dsv4-watch.log 2>&1 &
```

每 N 秒（默认 300）执行 check；异常自动 recover，**累计 ≤3 次熔断转人工**（防死循环）；日志落 /tmp/dsv4-watch.log。建议夜间挂起，发现连续恢复即升级（watch 只治标，连续触发说明需 rootcause 找新根因）。

## 3. 健康判定语义（重要认知）

```
                     ┌─ Registry state=ready（TTL 内心跳，服务端权威）──┐
实例 8001=200 ───────┤                                                ├── ✅ 健康
unless-stopped 拉起 ─┴─ 单轮崩溃自愈 ≠ 事故（连续性已恢复）──────────┘

升级人工条件：持续 RC 增长 + 8001 持续 000 > 15 分钟
（recover watch 内建此逻辑：20 轮探测 / 3 次恢复熔断）
```

- **RestartCount 是生命周期累计**：手工恢复/编排重启也会 +1，禁止单独作健康判据（曾在工具箱首版造成误报，已修正）
- **state=ready 是心跳权威**：由网关 TTL 阶梯（90s degraded / 180s unreachable / 300s 摘除）判定，ready 即最近 300s 内有心跳

## 4. 典型场景剧本

### 场景 A · 日常巡检（30 秒）

```bash
bash deploy/dgx/dsv4-recover.sh check        # ✅ 即结束；⚠️ 进场景 B
```

### 场景 B · 崩溃处置（标准流程）

```bash
bash deploy/dgx/dsv4-recover.sh rootcause    # ① 取证（判层级：显存/时序/其它）
bash deploy/dgx/dsv4-recover.sh recover      # ② 编排恢复（自动等待+e2e）
bash deploy/dgx/dsv4-recover.sh check        # ③ 复测确认
# ④ 观察稳定性：10:41 复崩当日用 watch 挂夜
nohup bash deploy/dgx/dsv4-recover.sh watch 300 >> /tmp/dsv4-watch.log 2>&1 &
```

### 场景 C · 灰度发布前检查

```bash
bash deploy/dgx/dsv4-recover.sh check        # baseline 健康才允许起灰度
bash scripts/canary-manage.sh set <model> <canary> 5
```

### 场景 D · recover 无效升级路径

```bash
bash deploy/dgx/dsv4-recover.sh rootcause    # 取证定位新根因
# → 评估 max-model-len/gpu-memory-utilization 再下调，或迁移 yyc3-101 共置容器
# → 仍无解：停 recover，按 05 Runbook SOP-03 走 env 摘除
```

## 5. 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `N1` / `N2` / `GW` | `yyc3-n1` / `yyc3-n2` / `yyc3-45` | 节点与网关 ssh Host 名 |
| `FORCE` | `0` | `=1` 时 recover 跳过健康检查强制执行 |
| `NODE_ID` 等 | — | 与本脚本无关（见 setup-container-map.sh） |

## 6. 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 健康 / 恢复成功（含 e2e 验证通过） |
| 1 | 异常 / 恢复未确认 / watch 熔断 |
| 2 | 用法错误 |

## 7. FAQ

**Q：为什么 8001 是 000 但脚本说在加载？**
加载期（约 8-12 分钟，46 分片 ×2 + autotune）APIServer 未监听，端口必 000——剧本以**日志特征**（APIServer 200 OK 行）判就绪，不以端口。

**Q：RestartCount=1/2 但服务正常，要处理吗？**
不要。RC 是累计值（编排重启也 +1）；只要 8001=200 + ready 即健康。持续增长且 8001 000 才是崩溃环。

**Q：recover 跑完 e2e 显示 ⚠️？**
实例已就绪但网关链路待查——跑 `bash scripts/health-full.sh` 看 ② 推理链与 Registry 细节。

**Q：watch 会把系统搞坏吗？**
recover 本身含健康前置（健康即跳过）；watch 熔断 3 次后停止并提示 rootcause，不会无限重启。

## 8. 实测记录

见 [06-运维脚本工具箱 §四](06-运维脚本工具箱.md) 表 #3/4/4b/4c：check 抓真实复崩 → recover 编排恢复（自愈加载成功）→ rootcause 全链取证 → 修正版回归，全流程当日闭环。

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0.0 | 2026-10-05 | 初版：五模式详解/健康判定语义/四场景剧本/FAQ，实测数据引自 06 §四 |
