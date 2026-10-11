---
file: 08-旗舰恢复与注册Agent实拉起总结报告.md
description: 0379-World 下轮 TOP3 执行——dsv4 重启恢复 + 冒烟脚本落地 + 五服务 Agent 实拉起 - 2026-09-28
author: AI Tutor <yyc3-expert>
version: v1.0.0
created: 2026-09-28
updated: 2026-09-28
status: stable
tags: [summary],[recovery],[smoke],[register-agent],[production]
category: report
---

# 📋 旗舰恢复 + 冒烟脚本 + 注册 Agent 实拉起总结报告

## 一、TOP1：dsv4-head 重启恢复 + OOM 实勘（✅ 已恢复）

### 1.1 恢复执行

| 步骤 | 结果 |
| ---- | ---- |
| `docker restart dsv4-head`（yyc3-101） | ✅ 冷加载数分钟 |
| :8001 /health | ✅ 200（引擎复活，日志 APIServer 正常服务） |
| 网关旗舰 chat（deepseek-v4-flash） | ✅ **502 → 200**（Phase 7 以来 SMOKE_FAIL 旗舰项闭环） |
| 熔断/路由 | 无需干预（半开自愈；env flagship-dsv4 优先层恢复服务） |

### 1.2 OOM 实勘与缓解建议（根因面未动，待窗口执行）

实勘 `docker inspect`：**mem_limit=0 / mem_reservation=0（完全无限制）+ restart=unless-stopped（引擎死容器不退 = 僵尸成因）**；宿主 121G（available 104G，权重靠 page cache）。

缓解建议（下次容器 recreate 窗口执行，本轮未动生产配置）：
1. env 加 `RAY_memory_usage_threshold=0.95`（Ray 内存监控阈值放宽，默认过敏感）
2. `mem_reservation` 预留 + 谨慎 mem_limit（**不可低于模型权重+KV cache**，否则 cgroup OOM 反而杀引擎；建议 reservation 100G、limit 不设或 ≥110G）
3. 中期：`dsv4-head-canary`（Up 10 天）去留评估——宿主内存压力源之一
4. **已落地的自愈面**：注册 Agent 心跳（本轮 TOP3）——此类「容器活引擎死」故障现 300s 自动摘除 + Agent 探活自动回归（本次 dsv4 agent 即全程自动跟随恢复，零人工）

## 二、TOP2：model_smoke_test.py（附录 A 末项落地，规范 01 §5 九用例）

**文件**：[core/scripts/model_smoke_test.py](../../core/scripts/model_smoke_test.py)（stdlib 零依赖）。用例：资产校验（复用 verify）/ 服务健康 / 网关可见 / chat+上游头 / SSE 流式 / 超长边界 / Registry 就绪（`--registry`）/ 能力面（embedding 自动，asr/ocr 人工提示）。

**生产首验（NAS 实跑）**：

| 模型 | 结果 | 亮点 |
| ---- | ---- | ---- |
| deepseek-v4-flash | **8/8 通过** | `X-YYC3-Upstream: flagship-dsv4` 披露 / SSE chunks=19+DONE / 边界 422 合规 / registry ready |
| qwen3-embedding-0.6b | **9/9 通过** | capability dim=1024；**能力面感知**（首跑逮出脚本适用面 bug：非 chat 模型 chat 系用例误测 → 修为适用面跳过，4c1e649） |

## 三、TOP3：五服务注册 Agent 实拉起（心跳接管手动模式 ✅）

### 3.1 部署实况

| 节点 | Agent | 状态 |
| ---- | ---- | ---- |
| yyc3-101 | dsv4 / embed / rerank ×3（nohup，~/yyc3-registry-agent/） | ✅ 3 进程常驻 |
| yyc3-102 | asr / ocr ×2 | ✅ 2 进程常驻 |

部署物：`model_register_agent.py`（scp 分发）+ 每服务 `meta-{model}.json` + `.env.agent`（admin key，600 权限）。**网关走 Tailscale 面 100.65.172.88:8000**（101/102 → NAS LAN 192.168.3.45 不通，实测修正）。

### 3.2 心跳接管验证（Registry 侧）

| 模型 | state | hb_age（实测） |
| ---- | ----- | -------------- |
| qwen3-embedding-0.6b / reranker | ready | 2.7 / 2.8s |
| qwen3-asr-1.7b / minicpm-v-4.6 | ready | 3.4 / 3.4s |
| deepseek-v4-flash | ready | 4.0s（**全程自动跟随引擎恢复**：等待冷加载→就绪→注册→心跳，零人工） |

**语义切换生效**：五服务自 `last_heartbeat=NULL`（手动模式不衰减）转为 30s 心跳态——**TTL 衰减语义激活**（停跳 90s degraded / 180s unreachable / 300s 摘除 + Phase B 事件清池），生产自愈闭环成型。

## 四、部署过程中的三连修（实勘教训）

1. **节点无 ADMIN_API_KEYS**：agent 秒退 exit 2 → `.env.agent`（600）下发
2. **跨网段网关地址**：101→`192.168.3.45` 不通（HTTP 0）→ 改 Tailscale `100.65.172.88`（端口契约双绑面）
3. **冒烟适用面**：非 chat 模型 chat 系用例误判 → 能力面感知跳过（4c1e649）

## 五、门禁与统计

| 门禁 | 结果 |
| ---- | ---- |
| 快层全量 | ✅ **148 passed**（+6 smoke） |
| lint（black/flake8）+ AST | ✅ 通过 |
| 生产 | 冒烟双模型 8/8+9/9；五 agent 心跳 2.7~4.0s；旗舰 502→200 |

提交：`513aab7`（smoke 落地）→ `4c1e649`（能力面感知修复），均已推 main（中途 GitHub 双端网络抖动重试通过）。

## 六、遗留与下轮建议

1. **[P2] Agent 常驻加固**：nohup 节点重启即失——systemd unit 模板化（`yyc3-registry-agent@.service`，5 实例）或容器 sidecar 化
2. **[P2] OOM recreate 窗口**：RAY_memory_usage_threshold + mem_reservation（§1.2，需短暂停服）
3. **[P3] canary 容器去留**（N1 内存压力源）
4. **[P3] Agent 观测接入**：agent 日志轮转 + 心跳断流告警（Grafana 规则 `heartbeat_missed`，规范 05 §9.1 已列阈值）

---

**报告状态**: ✅ TOP3 全闭环
**生产终态**: NAS @4c1e649；旗舰通道恢复；五服务 Agent 心跳常驻（TTL 自愈激活）
