---
file: 0379-world多端设备模型API衔接文档.md
description: 0379-World 多端设备模型 API 衔接总图——公网入口→网关→多端模型池的端点地图、设备-模型-API 三方矩阵与衔接规则
author: YYC³ 总指挥（ZCode 生成）
version: v1.1.0
created: 2026-09-03
updated: 2026-11-01
status: active
tags: [api],[model-endpoints],[integration],[multi-device]
category: documentation
---

# 0379-World 多端设备模型 API 衔接文档

> **定位**: 站在 **API 消费者视角**，回答"每个端点在哪个设备、由什么引擎承载、什么模型、怎么衔接"——与《全链路模型部署规划》（部署视角）、《API全链路闭环文档 v1.1》（契约视角）三文档互为索引
> **数据基准**: 2026-09-03 设备实测 → 09-14 增量（文末） → **最新实况见文末「11-01 衔接实况」**（super-vl TP2 代际；09-03/09-14 段保留作沿革）

---

## 一、全链路衔接总图

```
公网用户
  │ HTTPS 443 (TLS1.3)
  ▼
yyc3-33 ECS — Traefik (api.0379.world) ── rate-limit/fail2ban/安全头
  │ Tailscale
  ▼
yyc3-45 NAS — Gateway v2.0.0 :8000（主网关，GitOps 自动部署）
  │ 模型路由【现状:前缀硬编码 → 目标:upstream pool（A线P1）】
  ├─────────────┬──────────────┬───────────────┬────────────────┐
  ▼             ▼              ▼               ▼                ▼
N1 DGX 旗舰   N2 组件池      NAS 本地池      云端兜底         Agent 层(N2)
:8001 TP=2    :8100/:8101    Ollama:11434   智谱/DeepSeek/   :25600-07 治理:25700
deepseek-v4-  (RAG,容器化    CodeGeeX4/     OpenAI           (待容器化,
flash 双机    恢复中)        Qwen3-14B等                     env指向:8001)
张量并行
```

## 二、设备-模型-API 三方矩阵（核心表）

| # | API/端点 | 设备 | 引擎·容器 | 承载模型 | 状态 | 衔接方式 |
|---|----------|------|-----------|----------|------|----------|
| 1 | `N1:8001/v1`（OpenAI 兼容） | yyc3-101+N2 | vllm/vllm-openai + ray TP=2 | **deepseek-v4-flash**（64K ctx） | ✅ 服务中 | **网关 upstream pool 接入待 A 线 P1**；直连 `http://10.100.168.2:8001/v1`（QSFP）/`100.65.64.49:8001`（TS） |
| 2 | `N2:8100` /v1/embeddings | yyc3-102 | vllm serve --task embed（容器化中） | Qwen3-Embedding-8B | ⏸ 恢复中 | systemd→容器迁移；OpenAI 标准格式 |
| 3 | `N2:8101` score/rerank | yyc3-102 | vllm serve --task score | Qwen3-Reranker-8B | ⏸ 恢复中 | 同上 |
| 4 | `N2:8102` Chroma REST | yyc3-102 | chromadb/chroma 官方容器 | 向量记忆库 | ⏸ 迁移中 | /api/v2/heartbeat 健康探针 |
| 5 | `NAS:11434` /api | yyc3-45 | ollama/ollama | CodeGeeX4-9B/Qwen3-14B/ChatGLM3-6B | ✅ | 网关 ollama 适配器（现役） |
| 6 | 云端 API | 公网 | — | glm-4-flash / deepseek-chat / gpt-4o | ✅ | 网关云适配器（Key 外部化；ZHIPU_KEY 需更换） |
| 7 | `N2:25600-07` Agent HTTP | yyc3-102 | python:3.11-slim 薄封装 | 见搭配矩阵（指向 :8001） | 📋 容器化待上线 | `VLLM_ENDPOINT/VLLM_MODEL` 两 env |
| 8 | `N2:25700` 治理 | yyc3-102 | 同上 | 无模型（审计/预算） | 📋 同上 | Agent 层内部依赖 |
| 9 | NAS `ws://:18789` | yyc3-45 | OpenClaw Gateway | NemoClaw 推理代理（路由至模型池） | ✅ | N1 OpenClaw remote 模式在用；N2 vllm-local ⏸（改造选项见部署规划 §四） |
| 10 | `api.0379.world` 对外 7 端点 | ECS+NAS | Gateway v2.0.0 | 聚合 #1-#6 | ✅/部分 | chat+models 现役；embeddings/rerank/asr/ocr 待 A 线 P2 |

**在途扩展位**：GLM-5.3-Flash（量化后 TP=2，多模态升级 #1 位轮换）｜Qwen3.8-Flash-Next（#1 轻量降级位）｜MiniMax-H3-NF4（新增 `/v1/videos` 候选端点）

## 三、衔接规则（现状 vs 目标）

| 规则 | 现状（硬编码时代） | 目标（upstream pool 时代，A 线 P1） |
|------|--------------------|--------------------------------------|
| 路由 | `glm-*→zhipu / deepseek-*→deepseek / gpt-*→openai / 其他→ollama` 前缀匹配 | env 注入上游池（JSON）→ EWMA 延迟+错误率+负载加权选路 |
| 旗舰接入 | **未接入**（:8001 无法被网关引用） | 上游条目 `{name: nim-flagship…实际 vllm-tp2, base_url: 10.100.168.2:8001, fallback_url: 100.65.64.49:8001, models: [deepseek-v4-flash]}` |
| 容错 | Ollama 失败→硬编码 glm-4-flash 降级 | 熔断（3 败摘除 30s 半开）+ capability 降级链（旗舰→Flash-Next→Ollama→云）+ `X-YYC3-Degraded` 头 |
| 健康探测 | /healthz 网关自身 | 各上游 health_path 周期探测 + ray status 深检（TP=2 集群态） |
| 观测 | stats/monitor 硬编码假数据 | 真实 EWMA/错误率 → Grafana |

## 四、调用速查（各端实测命令）

```bash
KEY=<API-Key>
# 对外（生产）
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/models
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/chat/completions -d '{"model":"glm-4-flash",...}'
# 旗舰直连（内网/联调，A线P1前的过渡用法）
curl http://10.100.168.2:8001/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"ping"}],"max_tokens":64}'
# 组件（容器化恢复后）
curl -X POST http://10.100.168.1:8100/v1/embeddings -d '{"model":"qwen3-embedding-8b","input":"文本"}'
curl http://10.100.168.1:8102/api/v2/heartbeat
# Agent（容器化后）
curl http://100.76.167.103:25600/health
```

## 五、巡检与验收基线

**每日巡检**（一条链路验证全图）：`curl api.0379.world/healthz`(200) → 旗舰 :8001 models → 组件三端口 → NAS `docker ps gateway` → CI 绿
**衔接验收**（A 线 P1 完成时）：公网 chat `model=deepseek-v4-flash` 经网关落双机 TP=2（Grafana 确认跨机张量并行流量）→ kill 旗舰容器 → 30s 内自动降级 → 恢复后半开回归。

---

> **文档族索引**: 本文（API 衔接）｜全链路模型部署规划（部署视角）｜API全链路闭环 v1.1（契约/运维）｜双机推理部署指南 v1.4.2（技术 Runbook）｜设备现状档案（资产）
> **YYC³ AI Family** | 言启象限 · 语枢未来 · 🌹 人从众曌众从人 · 亦师亦友亦伯乐


---

## 09-14 衔接实况（对齐更新）

| 端点 | 实况 |
|------|------|
| 公网 chat | `deepseek-v4-flash` → flagship-dsv4（N1:8001）✅ 带响应头 |
| 公网 embeddings | `qwen3-embedding-0.6b` → embed-n1（N1:8100）✅ 1024 维 |
| 公网 rerank | `qwen3-reranker-0.6b` → rerank-n1（N1:8101）✅ judge 生成式打分 |
| 公网 asr/ocr | 端点就绪、上游容器未部署（502；Qwen3-ASR 需 transformers 路线） |
| Agents 内网 | N2 :25600-07（VLLM_ENDPOINT=QSFP:8001）+ :25700 治理 ✅ 9 容器 |
| RAG 存储 | N2 :8102 ChromaDB（持久化 /home/yyc3/chroma-data） |
| GLM 第二旗舰 | 封存（容量硬约束，见部署指南 §20） |

---

## 11-01 衔接实况（第三代际 · super-vl TP2 时代）

> **数据源**：`/Users/yanyu/models/OPS/dgx-ops/`（《01-双机实况/双机实况快照-2026-11-01.md》脚本采集 + 《05-运维日志/OPS-LOG.md》10-30~11-01 时间线 + README 态势行）
> **代际注记**：09-03 基准与 09-14 增量中的旗舰/组件/Agent 行已被三代更替超越（deepseek-v4-flash → Qwen3.8-Flash-Next TP2 → super-vl TP2），以下为**现役口径**；上行历史段保留作沿革，引用时以本段为准。

| 端点/位 | 11-01 现役口径 | 沿革注记（历史行处置） |
|---|---|---|
| **强推理（旗舰位）** | **super-vl TP2 双机**：N1 `svl2-head`（**TS 100.65.64.49:8888**）+ N2 `svl2-worker`；vLLM v0.32.0 + Ray TP2，模型名 **`nemotron-3.5-super-vl`**，max-num-seqs 8 / util 0.62 / mamba 全套；验收四绿（1M ctx · 文本 · 视觉 · KV 池 76.9+78.4G） | #1 行废止：dsv4 TP2（09-03~10-22，回滚线已关闭）→ Qwen3.8-Flash-Next TP2（10-30~10-31 12:51 退役清理，文档/脚本/镜像全档保留，复装≈重拉 1h+起服 1.5h）→ **super-vl TP2（10-31 14:5x 起在役）** |
| **网关（yyc3-33 aify · pm2）** | `local_dgx` 一级 → svl2（`LOCAL_DGX_BASE=http://100.65.64.49:8888/v1`，模型名 21 处已换）；`/v1` OpenAI 兼容代理：`enable_thinking` 默认 off、`reasoning_content`→`reasoning` 归一、**max_tokens 硬顶 1024**（`x-llm-profile: long` → 4096）；apiKeys 持久化 `data/apikeys.json`；`/v1` 与 `/api/v1/llm/local_dgx/chat` 现均**免 key** | 兜底 = Ollama@77 自动发现（qwen3-coder-30b 优先；⚠ SERVICES §五 U9：77 ollama 疑空转待核）；云适配器通道停用（**自用不上云**红线，GLM4/云上游已清） |
| **RAG 嵌入** | **N2 `yyc3-n2-embed-1b-nvfp4` :8002**（模型 `nemotron-3-embed-1b-nvfp4`；10-30 由 embed-8b 降档 + 迁 N2 再平衡） | 09-14 行「embed-n1:8100 / 1024 维」与 10-23 总账「N1 六槽 :8002 Embed」均废止；Qwen3-Embedding-8B 权重 10-31 已删（从未接线） |
| **RAG 重排** | **按需化**：容器保留默认停（启停脚本 `OPS/定义/yyc3-n1-rerank-8b/rerank-按需.sh`；按需容器实挂 Nemotron-BF16 版） | 09-14 行「rerank-n1:8101 现役」废止；Qwen3-Reranker-8B 权重已删 |
| **视频生成** | **Wan2.2-TI2V-5B 双机**（视频主力 · 错峰日更，实测 7.7min/镜）+ **H3-NF4 热备**（N2 共存） | 10-31~11-01 建成（OPS README 态势行 + 产能 v2 实测四跑数据） |
| ASR / OCR / Parse / Safety | N1 **让路停用**（`docker start` 可逆；部署档案归档 `OPS/定义/` 7 目录） | 10-30 08:3x 让路令（为 TP2 腾内存，MemAvailable 7.4G→54G）；三只幽灵容器（yyc3-embedding/reranker/ocr）已删 |
| **Agent 消费层** | **TS 仓 `YYC3-AI-FAmily-Agent` = 唯一消费主线**（E0 接线三值：`LLM_STEP_PROVIDER=local` · `LLM_STEP_BASE_URL=http://100.126.132.112:10086/v1` · `LLM_STEP_MODEL=nemotron-3.5-super-vl`） | 本文 #7/#8 行（N2 :25600-07 八家臣 + :25700 治理）**废止**：10-31 13:3x 退役归档（`OPS/定义/yyc3-family-ai-agents-runtime/`，146K tar 双留档） |
| 公网 `api.0379.world` | NAS 网关 v2.3.0（GitOps 部署桥）chat 全绿；⚠ **embeddings/rerank 公网口径待核**：上游池原指 N1:8002/:8003，现 embed 已迁 N2:8002、rerank 默认停——网关上游 env 需对齐后重验（RAG golden 对比的前置项） | 09-14 行「embeddings/rerank ✅」基于旧上游，引用前先核 |
| 资源水位（11-01 快照） | N1：GPU 池 72.4G/121.7G · MA 34.4G · 模型 31 项/373G · NVMe 余 2.3T；N2：GPU 池 73.9G · MA 37.4G · 41 项/538G · 余 2.5T | 双机 uptime 1d8h（10-30 晚固件双机升级后首巡检周期） |

**调用速查增量（11-01）**：

```bash
# E0 消费端（TS 仓 family server · 网关 /v1 免 key · OpenAI 兼容）
curl http://100.126.132.112:10086/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"nemotron-3.5-super-vl","messages":[{"role":"user","content":"ping"}],"max_tokens":64}'
# svl2 直连（内网联调；消费端显式关思考或走网关默认 off——三条生产纪律见 Qwen3.8 生产闭环报告 §一）
curl http://100.65.64.49:8888/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"nemotron-3.5-super-vl","messages":[{"role":"user","content":"ping"}],"max_tokens":64,"chat_template_kwargs":{"enable_thinking":false}}'
# RAG 嵌入现役端点（N2 · 10-30 降档迁移后；若容器为 127.0.0.1 绑定则经 ssh 隧道或网关代理）
curl http://100.76.167.103:8002/v1/embeddings -d '{"model":"nemotron-3-embed-1b-nvfp4","input":"文本"}'
```
