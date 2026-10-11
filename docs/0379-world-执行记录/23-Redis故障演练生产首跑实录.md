---
file: 23-Redis故障演练生产首跑实录.md
description: chaos-redis.sh 生产首跑全程实录——脚本三 bug 修复、规则装载事故复盘、演练验收结论、上游 502 外部发现
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-10-12
status: archived
tags: [chaos-drill],[redis],[production],[postmortem],[runbook]
---

# Redis 故障演练生产首跑实录（2026-10-12 00:24-00:55）

## 一、结论先行

**Redis 韧性链路五项验收口径全部通过**（存活探针无污染 / 故障识别 / 告警触发 / 恢复回切）；
chat/rerank 的 20 项 FAIL 与 Redis 无关——是**上游容量现状**（旗舰 dsv4 停机 27h、reranker 不在上游池），
属演练范围外发现，已在 §五单列。生产状态全程受控，演练后全恢复。

## 二、首跑前排除的四个真 bug（按发现顺序）

| # |  bug | 症状 | 修复 |
|---|---|---|---|
| 1 | chaos-redis.sh 远端命令未经登录 shell | 非交互 SSH 下 `docker: command not found` 静默落空，前置检查误报「Redis 未运行」 | `ssh_nas()` 统一 `bash -lc` 包装（与 load-prom-rule.sh 同坑） |
| 2 | 同上通道的字面双引号 | `tr -d '"'` 会提前闭合 ssh 远端双引号层 | 改八进制 `tr -d '\042'` |
| 3 | load-prom-rule.sh `>> EOF` 追加 | repo 版 prometheus.yml 尾段已是 scrape_configs，规则路径被追加成**非法 YAML**；reload 静默失败、规则未生效、脚本却误报 ✅（组名正则 `[a-z0-9-]+` 吃不掉点号，`yyc3.redis` 被截成 `yyc3` 恰好匹配旧组） | 改为「插在最后一个既有 rules 条目后」；正则放宽 `[a-z0-9.-]+`；本地判定改为「无 `verified:` 即失败」 |
| 4 | chaos-redis.sh 能力探测复用 `code()` | `code()` 签名是 `code URL TIMEOUT`，探测函数 flag 前置传参 → `curl: option -m requires parameter`，全部能力项假 FAIL | POST 场景直写 curl |
| 5 | 安全网 trap 时序 | 信号在 `sleep` 内到达时 bash 延迟处理 trap，极端情况跳过 cleanup（首跑 kill 实测 Redis 未被自动拉起） | `pause()` = `sleep & wait`（信号即刻打断）+ TERM/INT 显式 trap |

修复后全部回归：bash -n 通过、规则幂等装载三 ✅（含 `verified: yyc3.redis`）、演练第二跑机械全通。

## 三、生产动作执行记录（简报三步走）

1. **装载规则** ✅ 00:24 — 暴露 bug #3；全量替换 prometheus.yml（repo 版为准）+ 热加载后三规则组生效。
2. **rebuild 网关** ✅ 00:40 — 白名单 7 代码文件 + requirements.lock(148 行) + Dockerfile 直 scp 至 `/Volume2/yyc3-33`（不走 git：工作区含非本次变更且未提交），`compose --project-directory . -f deploy/nas/docker-compose.nas.yml up -d --build gateway`。踩坑：`-f` 相对路径按 cwd 解析、build context 按 project-directory 解析，两者缺一不可。
3. **首跑演练** ✅ 00:47 — 汇总 PASS=21 FAIL=20，FAIL 全部为 chat/rerank 502（见 §五）。

**首跑后生产状态**：gateway Up healthy（新镜像，yyc3_redis_up 已露出）、redis Up healthy、pg healthy、/health redis=healthy、限流四 worker 均现「Redis 限流后端已恢复」。

## 四、演练验收明细（第二跑，00:47-00:52）

| 口径 | 结果 | 证据 |
|---|---|---|
| 前置门禁 | ✅ | 容器/healthz/health 基线全绿才注入（首跑曾在此正确拦停） |
| 存活探针 | ✅ | 宕机后 /healthz 仍 200（全程 2 项 PASS） |
| 故障识别 | ✅ | /health redis=unreachable；恢复后 0s 转 healthy（/health 事件驱动即时更新） |
| 三能力降级 | embeddings ✅ 全程 200；chat/rerank ❌ 502——**基线即 502**（注入前），与 Redis 无关 | 见 §五 |
| 告警触发 | ✅ | **RedisDown 注入后约 120s firing**（探活轮询 60s + 抓取 15s + eval 30s + for 60s，符合预期时序） |
| 恢复回切 | ✅ | 容器 10s healthy；限流日志「Redis 限流后端已恢复」×4（4 worker 各回切一次，多实例语义符合设计） |

## 五、范围外发现：上游 502（与 Redis 无关，建议另行处理）

- **chat 502**：`flagship-dsv4 @ 100.65.64.49:8001` 连接失败。N1 `dsv4-head` Exited(0) **27 小时前**（主动停止），N2 `dsv4-worker` Exited(137 SIGKILL) 同时段——旗舰自昨晚停机。N2 当前正被其他实验占用（`glm-nim` Up 45s、`emb8b-eval` Up 2min、冒烟容器 25min 前退出），**不宜在此时重启旗舰**（TP=2 跨机，VRAM 会挤占进行中的实验）。
- **rerank 502**：网关上游池 **无任何 rerank 能力上游**（降级链为空串），0.6B reranker 容器已不在 N2 容器列表——容量整改后未恢复入池。
- **建议**：上游恢复后重跑 `bash scripts/chaos-redis.sh` 补齐三能力口径（告警/回切项已验证，二次跑预计全绿）；reranker 入池需先做容量核算。

## 六、遗留与提醒

1. **部署树与 git 源漂移**：本次直 scp 使 `/Volume2/yyc3-33` 领先 git 提交；下次 auto-deploy 若从旧 commit 重建会回退本次修复——**请尽快按简报白名单拣选提交并推送**。
2. worker 容器（0379-world-worker-1）仍跑旧镜像，canary 恢复探测只部署在网关侧，无影响；下次 worker 重建自然带上。
3. load-prom-rule.sh 的修复建议同步进 git 提交（它在 deploy/nas/ 下，属白名单外但同批改动，建议一并提交）。
