---
file: YYC3-Models-资产详情.md
description: 模型资产总览 - 多设备模型清单与上线状态跟踪（SOP-01 Step 6 归档载体）
author: YanYuCloudCube Team <admin@0379.email>
version: v1.1.0
created: 2026-09-02
updated: 2026-10-05
status: active
tags: [assets],[model-inventory],[nas],[onboarding]
category: inventory
---

# 模型资产总览

> **定位**：本文件是 [模型接入 SOP-01](../模型接入与注册/05-监控告警与Runbook.md) Step 6 指定的上线归档载体——新模型上线后须回写「上线状态总览」表；下方原始目录清单为 NAS/本机快照，上线状态以上表为准。
> **状态口径**（禁止盲填，须有佐证）：
>
> | 标记 | 语义 | 佐证要求 |
> | --- | --- | --- |
> | ✅ 已上线 | 生产承接流量（Registry/env 双写或 env 单写） | 网关配置或 Registry 记录 |
> | 🔶 部署物就绪 | 节点侧部署脚本/编排已备，运行态待确认 | deploy/ 部署物 |
> | 📦 仅存档 | NAS 仓库留存，未接入网关 | 本文档清单 |
> | ⚠️ 异常 | 疑似空目录/损坏，禁止入库范例 | 现场核实命令输出 |

## 上线状态总览（2026-10-05 审核基线）

> 佐证锚点：`deploy/dgx/`（dsv4 编排 + emb8b/rerank8b entry 脚本）、`core/config/.env.example` L106 生产开闸注释（2026-09-28 五生产上游 dsv4/embedding/rerank/asr/ocr 双写入中心）。

| 模型资产 | 位置 | 上线状态 | 佐证 |
| --- | --- | --- | --- |
| DeepSeek-V4-Flash | NAS `/Volume1/yyc3_hd/data/DeepSeek/` | ✅ 已上线（dsv4 旗舰）· ⚠️ 10-05 巡检：Registry `state=offline`，心跳停于 09-29，需检查 yyc3-101 dsv4 实例/注册 Agent | Registry 记录（chat/tool_use/json_mode）+ [docker-compose-n2.yml](../../deploy/dgx/docker-compose-n2.yml) |
| Qwen3-ASR-1.7B | NAS `/Volume1/yyc3_hd/data/Qwen/` | ✅ 已上线（`qwen3-asr-1.7b`，Registry ready，yyc3-102；**型号归属闭环**） | Registry 记录 + [docker-compose-asr.yml](../../deploy/dgx/docker-compose-asr.yml) |
| MiniCPM-V-4.6（OCR/Vision 承载） | NAS `/Volume1/yyc3_hd/data/` | ✅ 已上线（`minicpm-v-4.6`，Registry ready，yyc3-102，ocr/vision） | Registry 记录（OCR 上游承载模型） |
| Qwen3-Embedding-8B | NAS `/Volume1/yyc3_hd/data/Qwen/` | 📦 仅存档（生产实跑 **0.6b 版** `qwen3-embedding-0.6b`，Registry ready yyc3-101；8B 为备用部署物） | Registry 记录 + [emb8b_entry.sh](../../deploy/dgx/emb8b_entry.sh) |
| Qwen3-Reranker-8B | NAS `/Volume1/yyc3_hd/data/Qwen/` | 📦 仅存档（生产实跑 **0.6b 版** `qwen3-reranker-0.6b`，Registry ready yyc3-101；8B 为备用部署物） | Registry 记录 + [rerank8b_entry.sh](../../deploy/dgx/rerank8b_entry.sh) |
| RAG 三件套 0.6B（embedding/reranker） | 节点本地 SSD | ✅ 已上线（Registry ready） | Registry 记录 + [docker-compose-rag.yml](../../deploy/dgx/docker-compose-rag.yml) |
| Qwen3.8-Flash-Next | NAS `/Volume1/yyc3_hd/data/Qwen/` | 📦 仅存档（**已现场核实为完整资产**：HF cache 布局，`snapshots/master` 含 131-of-00131 分片 + 全套 config/tokenizer，未接入网关） | 现场核实记录（见下节） |
| 其余 NAS 模型（28 项，见下方注册记录） | NAS `/Volume1/yyc3_hd/data/` 各家族 | 📦 已注册归档（Registry `offline` + `enabled=false`，`tags: nas-archive`，`weights_path` 已挂接 NAS 绝对路径；上线时走 SOP-01 + 置 ready） | Registry 批量注册记录（下节） |
| yyc3-22 本机模型 | `/Users/yanyu/models/`、`/Volumes/Max/models/` | 本机开发用（不适用上线状态） | 本文档清单 |

## Registry 批量规范注册记录（2026-10-05）

> 执行通道：Tailscale SSH `yyc3-45` → 网关 `POST/PATCH /registry/v1/models`（admin 键）；试点单条 201 验证后批量，全量 28×201 + 3×200，审计链逐条入 `model_audit_log`（action: `model.registered`）。

**注册口径**：归档态（`state=offline` 由服务端落、`enabled=false` 双保险不进路由池）+ `backend=vllm` + `weights_path` 挂 NAS 绝对路径 + 能力面按模型类型保守标注（`capabilities` 以冒烟为准）+ `tags: ["nas-archive","batch-20261005"]`；上下文/精度不盲猜（FP8/Q4 仅依据目录名）。**幂等**：重复注册 = 覆盖，无副本。

**新增 28 条**：Qwen 家族 19（qwen3-0.6b/8b/14b、asr-0.6b、coder-30b-a3b(+q4)、embedding-8b、reranker-8b、qwen3.5-0.8b/4b/9b/122b-a10b/397b-a17b、qwen3.6-27b(+fp8)/35b-a3b(+fp8)、qwen3.8-27b、qwen3.8-flash-next）· DeepSeek 2（base、v4-pro）· GLM 3（5.1、5.1-fp8、5.3-flash）· 其他 4（kimi-k2.6、ring-2.6-1t、megastyle-1.4m、nemotron-3.5-content-safety）

**PATCH 补挂 3 条**（存量记录补 `weights_path`）：deepseek-v4-flash、qwen3-asr-1.7b、minicpm-v-4.6（`tags: nas-linked-20261005`）

**注册后全景**：total 18→46 · nas-archive 28 · ready 4（生产无扰）· weights_path 挂接 31

**未注册（现场核定）**：GLM/ChatGLM3-6B、CodeGeeX4-9B、CodeGeex4-9B_Q8（0 条目空目录）——待补齐资产后再注册

**遗留治理已处置（2026-10-05 第二批）**：
- ✅ **zhipu 云通道 9 条**（glm-4/4-flash/4-flash-250414/4-plus/4.6/4.6v-flash/4.7/4.7-flash/glm-5）——**溯源闭环**：非 NAS 资产，系 [model_router.py L128](../../core/api/services/model_router.py#L128) zhipu 云直连通道 + [main.py L454-489](../../core/api/main.py#L454) 启动 seed 写表 + `free_model_combinations.json` 免费组合清单的历史沉淀（created_at 2026-03 与该时代吻合）。处置：补 capabilities（chat；glm-4.6v-flash 为 chat+vision）+ `tags: cloud-zhipu/annotated-20261005`，维持 disabled（云模型经 zhipu provider 直连路由，不经 Registry 上游池）
- ✅ **local 旧记录 4 条**（nemotron-nano、qwen3.6:35b-a3b、yyc3-coder-v1、yyc3-manager-v1）——仓库与生产 env 均无来源引用（早期手动/ollama 命名风格残留，永无心跳）。处置：置 `enabled=false` + `tags: legacy-disabled-20261005`，消除 `/v1/models` 假在线误导
- ✅ **治理后全景**：total 46 · `enabled=true` 仅 5 条（4 ready + deepseek-v4-flash 旗舰待心跳恢复）· zhipu 标注 9 · legacy 禁用 4
- ✅ **deepseek-v4-flash 旗舰恢复（2026-10-05 当日闭环，公网推理冒烟通过）**：六天心跳停滞（09-29→10-05）根因为**三层叠加**——① 本质：`RayWorkerProc rank[0] died unexpectedly`，TP0 本机空闲 84.12G vs util 0.66 预算 80.31G，权重 73.84G + KV/激活后仅 3.8G 缓冲，启动末段 profile 峰值挤穿显存（n1 常驻 embedding/reranker 抬高基线）；② 放大器：dsv4-worker（n2）被 head 崩溃连带 SIGTERM（退出码 0）而 RestartPolicy 不自动拉起 → PG 永远凑不齐 2×GPU 的启动死锁环；③ 干扰项：vLLM 0.28.1rc1 nightly 跨机 TP graph/autotune 竞态噪音。处置四步（宿主 `/home/yyc3/dsv4_head.sh` 备份 `.bak.20261005`，仓库 [dsv4_head.sh](../../deploy/dgx/dsv4_head.sh) 已同步）：`max-model-len 65536→32768`（峰值减半，主修复）+ `VLLM_USE_BREAKABLE_CUDAGRAPH=0`（eager，消竞态）+ worker `--restart unless-stopped`（破死锁闭环）+ head/worker 编排时序重启（GCS 就绪后 worker 接入）。验证：8001→200、Registry `state=ready` 心跳恢复（00:29:30Z）、ready 4→5、`context_window` PATCH 对齐 32768、公网 chat 真实生成 ✓

**ECS yyc3-33 定位核定（2026-10-05 实查）**：仅运行 `docker-traefik-1`（traefik:v3.0.4，`/root/0379-world/`），本机 :8000 无服务；ECS 侧 `traefik/dynamic.yml` 将 `api.0379.world / grafana.0379.world / prometheus.0379.world` 全部转发至 `http://100.65.172.88:8000`（NAS yyc3-45）。**定位 = 公网边缘反代（Traefik TLS + fail2ban 边界）**，生产网关/数据/推理全在 Tailscale 内网；NAS 部署目录 `/Volume2/yyc3-33` 即网关栈自 ECS 迁往 NAS 的命名遗迹（[deploy-nas-gateway.sh](../../scripts/deploy-nas-gateway.sh) L19）。注意：仓库 `pg-setup-*.sh / pg-failover.sh / verify-load-balancer.sh` 等曾以 yyc3-33 为主库/主 LB 目标——已于同日加退役守卫处置（见变更记录 v1.4.0）。

## 现场核实记录（2026-10-05）

> 通道：Tailscale SSH `yyc3-45`（`100.65.172.88:9557`，用户 YYC3）；开发机 NFS 未挂载故走 SSH。

| 核实项 | 结果 | 关键证据 |
| --- | --- | --- |
| `Qwen/Qwen3.8-Flash-Next` | ✅ 完整资产（HF cache 布局）；外层目录 18 字节仅为目录元数据，**此前清单快照「疑似空目录」系误读，勘误** | `snapshots/master` 含 `model-00001-of-00131.safetensors` 起 131 分片 + 132 个 safetensors 相关文件 + config/tokenizer/chat_template 全套 |
| `DeepSeek/DeepSeek-V4-Flash` | ✅ 完整资产（扁平布局，生产已上线） | 47 个 safetensors 分片（`model-00001-of-00046` 起）+ config/generation_config |
| 目录布局规范 | NAS 两种布局并存：扁平型（DeepSeek 家族）/ HF cache 型（Qwen3.8-Flash-Next） | 抽查 `DeepSeek-V4-Flash/snapshots` 与 `Qwen3-Embedding-8B/snapshots` 均不存在 → 扁平；Flash-Next 存在 `snapshots/master` → HF cache |

## 原始目录清单（快照）

### yyc3-22 （本机 macOS M4 Max 128G）主开发机

#### 模型路径详情（本地盘）

- /Users/yanyu/models/YYC3-Family-Coder-14B-F16.gguf
- /Users/yanyu/models/YYC3-Family-Coder-14B-Q4_K_M.gguf
- /Users/yanyu/models/YYC3-Family-Coder
- /Users/yanyu/models/MiniMax-H3-NF4

#### 模型路径详情（本机拓展高速盘）

- /Volumes/Max/models/HiDream-O1-Image
- /Volumes/Max/models/Z-Image-Turbo
- /Volumes/Max/models/lingbot-map
- /Volumes/Max/models/MiniMax-H3-NF4
- /Volumes/Max/models/MiniCPM-V-4.6

#### GLM 模型路径及详情（本机拓展高速盘）

- /Volumes/Max/models/GLM/GLM-5.3-Flash

#### NVIDIA 模型路径及详情（本机拓展高速盘）

- /Volumes/Max/models/NVIDIA/Nemotron-3.5-Content-Safety

#### Qwen 模型路径及详情（本机拓展高速盘）

- /Volumes/Max/models/Qwen

drwxr-xr-x@ 15 yanyu  staff    480 May 30 16:30 Qwen3-0.6Bd
drwxr-xr-x@ 20 yanyu  staff    640 May 15 02:02 Qwen3-8B
drwxr-xr-x@ 15 yanyu  staff    480 May 30 16:36 Qwen3-ASR-0.6B
drwxr-xr-x@ 17 yanyu  staff    544 May 30 16:35 Qwen3-ASR-1.7B
drwxr-xr-x@  4 yanyu  staff    128 May 27 17:57 Qwen3-Coder-30B-A3B-Q4
drwxr-xr-x@ 22 yanyu  staff    704 Jul 18 10:28 Qwen3-Embedding-8B
drwxr-xr-x@ 19 yanyu  staff    608 May  1 22:23 Qwen3-Reranker-8B
drwxr-xr-x@ 18 yanyu  staff    576 May 30 16:23 Qwen3.5-0.8B
drwxr-xr-x@ 19 yanyu  staff    608 May 30 16:25 Qwen3.5-4B
drwxr-xr-x@ 21 yanyu  staff    672 May 30 16:34 Qwen3.5-9B
drwxr-xr-x@ 32 yanyu  staff   1024 Jul 18 10:28 Qwen3.6-27B
drwxr-xr-x@ 84 yanyu  staff   2688 May 15 03:55 Qwen3.6-27B-FP8
drwxr-xr-x@ 44 yanyu  staff   1408 May  1 23:03 Qwen3.6-35B-A3B
drwxr-xr-x@ 60 yanyu  staff   1920 May 15 03:54 Qwen3.6-35B-A3B-FP8
drwxr-xr-x@ 37 yanyu  staff   1184 Sep  2 20:51 Qwen3.8-27B

---

### yyc3-45 NAS 模型路径及详情

- /Volume1/yyc3_hd/data

#### Qwen 模型路径及详情

- /Volume1/yyc3_hd/data/Qwen

drwxrwx---+ 1 YYC3     YYC3      300 May 30 16:30 Qwen3-0.6B
drwxrwx---+ 1 YYC3     YYC3      776 Sep 20  2023 Qwen3-14B
drwxrwx---+ 1 YYC3     YYC3      642 May 15 02:14 Qwen3-8B
drwxrwx---+ 1 YYC3     YYC3      342 Jun  5 00:42 Qwen3-ASR-0.6B
drwxrwx---+ 1 YYC3     YYC3      492 Jun  5 00:42 Qwen3-ASR-1.7B
drwxrwx---+ 1 YYC3     YYC3     1412 Mar 16 16:45 Qwen3-Coder-30B-A3B
drwxrwx---+ 1 YYC3     YYC3       80 May 16 00:06 Qwen3-Coder-30B-A3B-Q4
drwxrwx---+ 1 YYC3     YYC3      686 Apr 30 14:57 Qwen3-Embedding-8B
drwxrwx---+ 1 YYC3     YYC3      628 May  1 22:23 Qwen3-Reranker-8B
drwxrwx---+ 1 YYC3     YYC3      512 May 30 16:23 Qwen3.5-0.8B
drwxrwx---+ 1 YYC3     YYC3     3900 May 15 13:46 Qwen3.5-122B-A10B
drwxrwx---+ 1 YYC3     YYC3     8732 May 15 22:05 Qwen3.5-397B-A17B
drwxrwx---+ 1 YYC3     YYC3      600 May 30 16:25 Qwen3.5-4B
drwxrwx---+ 1 YYC3     YYC3      776 May 30 16:34 Qwen3.5-9B
drwxrwx---+ 1 YYC3     YYC3     1420 Sep 20  2023 Qwen3.6-27B
drwxrwx---+ 1 YYC3     YYC3     3204 May 15 03:55 Qwen3.6-27B-FP8
drwxrwx---+ 1 YYC3     YYC3     2132 May  1 23:03 Qwen3.6-35B-A3B
drwxrwx---+ 1 YYC3     YYC3     2196 May 15 04:10 Qwen3.6-35B-A3B-FP8
drwxr-xr-x+ 1 YYC      allusers 1638 Sep  2 20:51 Qwen3.8-27B
drwxr-xr-x+ 1 YYC3     YYC3       18 Sep  2 23:10 Qwen3.8-Flash-Next

#### DeepSeek 模型路径及详情

- /Volume1/yyc3_hd/data/DeepSeek

drwxrwx---+ 1 YYC3     YYC3   84 Sep 20  2023 DeepSeek-Base
drwxrwx---+ 1 YYC3     YYC3 3302 Sep 20  2023 DeepSeek-V4-Flash
drwxrwx---+ 1 YYC3     YYC3 4454 Sep 20  2023 DeepSeek-V4-Pro

#### GLM 模型路径及详情

- /Volume1/yyc3_hd/data/GLM

drwxrwx---+ 1 YYC3     YYC3     0 Jun 14 11:07 ChatGLM3-6B
drwxrwx---+ 1 YYC3     YYC3     0 Jun 14 11:07 CodeGeeX4-9B
drwxrwx---+ 1 YYC3     YYC3     0 Jun 14 11:07 CodeGeex4-9B_Q8
drwxrwx---+ 1 YYC3     YYC3   824 Mar 15  2026 Cogagent-9B
drwxrwx---+ 1 YYC3     YYC3   252 Sep 20  2023 Cogvideox-5B
drwxrwx---+ 1 YYC3     YYC3 18406 May 16 22:02 GLM-5.1
drwxrwx---+ 1 YYC3     YYC3  9408 May 15 13:03 GLM-5.1-FP8
drwxrwx---+ 1 YYC3     YYC3  4336 Sep  2 22:15 GLM-5.3-Flash

#### NVIDIA 模型路径及详情

- /Volume1/yyc3_hd/data/NVIDIA/Nemotron-3.5-Content-Safety

#### Kimi-K2.6 模型路径及详情

- /Volume1/yyc3_hd/data/Kimi-K2.6

#### Ring-2.6-1T 模型路径及详情

- /Volume1/yyc3_hd/data/Ring-2.6-1T

#### MiniCPM-V-4.6 模型路径及详情

- /Volume1/yyc3_hd/data/MiniCPM-V-4.6

#### MegaStyle-1.4M 模型路径及详情

- /Volume1/yyc3_hd/data/MegaStyle-1.4M

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0.0 | 2026-09-02 | 初版清单（三设备目录快照） |
| v1.1.0 | 2026-10-05 | 补 YAML front matter 与文档定位；新增「上线状态总览」表（状态口径 + 部署物佐证）；经 Tailscale SSH（yyc3-45:9557）现场核实并新增「现场核实记录」节——Qwen3.8-Flash-Next 勘误为完整资产（HF cache 布局 131 分片，清单 18 字节系外层元数据误读）、DeepSeek-V4-Flash 扁平布局 47 分片、NAS 两种布局并存；原清单整体保留为快照章节 |
| v1.2.0 | 2026-10-05 | 衔接审核不足项执行规范化注册：Registry 批量注册 NAS 资产 28 条（offline 归档 + weights_path 挂接 + nas-archive 标签）+ PATCH 补挂存量 3 条，total 18→46、ready 4 无扰、审计链完整；上线状态总览按 Registry 实况修正（ASR 型号闭环 1.7b、embedding/reranker 实跑 0.6b、旗舰心跳停滞告警）；遗留治理三项待决策入注册记录节 |
| v1.3.0 | 2026-10-05 | 遗留治理第二批落地：zhipu 云通道 9 条溯源闭环（model_router 云直连 + main.py seed + 免费组合清单沉淀）并补能力标注；local 旧记录 4 条核对后置 disabled（enabled=true 仅剩 5 条真实有效）；ECS yyc3-33 定位核定（纯 Traefik 公网边缘 → NAS 网关，含仓库脚本幽灵引用提醒） |
| v1.4.0 | 2026-10-05 | 幽灵脚本治理：pg-setup-*.sh / pg-failover.sh / pg-verify-replication.sh / setup-load-balancer.sh / verify-load-balancer.sh / test-failover.sh 共 7 个加退役守卫（exit 1 + YYC3_ALLOW_RETIRED=1 放行，Makefile backup 链自然回退 yyc3_db_backup.sh）；dsv4 旗舰 TP2 死锁排障与恢复（根因/处置/防复发建议入注册记录节） |
