---
file: 全链路模型部署规划-NVIDIA核心技术.md
description: YYC³ 双 DGX 全链路模型部署规划——环境/模型部署/NemoClaw-OpenClaw 模型链接/yyc3-family-ai-agents 模型搭配/RAG，融合 NVIDIA 官方镜像-加速-量化核心技术
author: YYC³ 总指挥（ZCode 生成）
version: v1.0.0
created: 2026-09-03
status: active
tags: [deployment-plan],[nvidia-core],[models],[nemoclaw],[agents],[rag]
category: plan
---

# YYC³ 全链路模型部署规划（NVIDIA 核心技术 · 镜像 · 加速 · 量化）

> **定位**: 《DGX-Spark双机推理部署指南》(v1.4.2) 的**实况对齐版总规划**——以五段式（环境→模型部署→NemoClaw 模型链接→Agents 模型搭配→RAG）呈现全链路；所有数据为 2026-09-03 设备实测，规划项均标注状态（✅运行/⏸暂离/⬇在途/📋规划）
> **兄弟文档**: 《0379-world多端设备模型API衔接文档》（对外 API 视角）｜《DGX-Spark双机推理部署指南》（技术细节与 Runbook）

---

## 一、全链路总图

```
┌─────────────────── ③ 模型部署层（本规划核心）───────────────────┐
│  旗舰: DeepSeek-V4-Flash TP=2 ✅ N1:8001（ray+QSFP·双机96G对称）│
│  在途: GLM-5.3-Flash(306G⬇多模态升级位) Qwen3.8-Flash-Next⬇    │
│        MiniMax-H3-NF4⬇(视频生成)  NAS冷库(全量备份)            │
├──────────────────────────────────────────────────────────────────┤
│  ④ NemoClaw-OpenClaw（沙箱+推理代理）      ⑤ yyc3-family-ai-agents│
│     N1: remote网关→NAS:18789 ✅              8 Agent+治理(模型无关)│
│     N2: vllm-local→:8000 ⏸(旗舰腾挪)         VLLM_ENDPOINT 两行切换│
├──────────────────────────────────────────────────────────────────┤
│  ⑥ RAG: Embedding:8100⏸ Reranker:8101⏸ ChromaDB:8102⏸(容器化恢复)│
├──────────────────────────────────────────────────────────────────┤
│  ② NVIDIA 三支柱: 镜像(官方容器规范) · 加速(批处理四件套+QSFP+NCCL)│
│                  · 量化(FP8现役/NVFP4产线)                        │
├──────────────────────────────────────────────────────────────────┤
│  ① 环境层: GB10×2(121G×2) · YanYuCloud集群(210Gbps) · Ubuntu24.04│
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、环境部分（①层 · 2026-09-03 实测）

### 2.1 硬件与集群

| 项 | N1 (yyc3-101) | N2 (yyc3-102) |
|----|---------------|---------------|
| GPU | GB10 Grace Blackwell (sm_121) ×121G UMA | 同构 |
| 集群 | YanYuCloud 官方向导认证（SSH 12/12 · **210.76 Gbps** · 2 devices direct） | |
| 关键链路 | QSFP 双口 10.100.168.2/.169.2 ↔ N2 .1/.1（实测 ~1GB/s 传输、0.087ms） | |
| 外联 | Tailscale 100.65.64.49（对 NAS/ECS 唯一通道 ~2MB/s，仅小文件） | 100.76.167.103 |
| 统一用户 | **yyc3**（免密 sudo ✓ 双机；操作铁律见运维手册） | |

### 2.2 软件栈（NVIDIA 核心）

| 层 | 组件 | 版本/状态 |
|----|------|-----------|
| 系统 | Ubuntu 24.04.4 / 内核 6.17.0-1031-nvidia / Docker 29.2.1 | ✅ |
| 驱动 | NVIDIA 580.173.02 | ✅ |
| 推理容器 | `vllm/vllm-openai:latest`（现役旗舰载体，内置 NCCL 2.28.9） | ✅ |
| NCCL 基座 | `nvcr.io/nvidia/pytorch:26.07-py3`（**NCCL 2.30.7**，门禁/工具） | ✅ |
| 编译产线 | `nvcr.io/nvidia/tensorrt-llm/release:1.3.0rc5/rc12`（量化用） | ✅ |
| CND 渠道 | 畅云 sglang-spark 基础容器 + 图灵 Qwen3.6-35B Spark-NIM（N2 在位） | ✅ 备用 |
| 凭据 | nvcr login（Build钥）✓ / ngc CLI（NGC钥）✓ / .nim-env(600) ✓；**NIM 目录对中国 IP 区域封锁**（2025-02 政策，非 NIM 的 nvcr 拉取正常） | |
| 下载通道 | **hf-mirror 87-117MB/s（首选）** > modelscope（DeepSeek 系 26MB/s，ZhipuAI/Qwen 系仅 0.25-1MB/s ⚠️）> NAS SMB 2MB/s（禁用于大文件）；pip 一律清华源 | |

### 2.3 镜像资产（双机清单见《设备现状档案》§四；关键 6 枚）

`vllm/vllm-openai`(19.9G×2 现役) ｜ pytorch:26.07(NCCL2.30.7×2) ｜ TRT-LLM rc5/rc12 ｜ python:3.11-slim(容器化基底) ｜ tgcr qwen-spark-NIM(21.9G) ｜ chancloud sglang-base(31.5G)

---

## 三、模型部署（③层 · NVIDIA 三支柱落地）

### 3.1 部署矩阵（实况对齐）

| 层 | 模型 | 引擎/镜像 | 位置 | 状态 |
|----|------|-----------|------|------|
| **旗舰** | DeepSeek-V4-Flash（284B MoE/A13B，FP8 混合精度 159.6G） | vllm 官方镜像 + ray TP=2 | **N1:8001**（head）+N2(worker) | ✅ 服务中（64K ctx/KV-FP8/prefix-cache；双机 96G 对称；启停 Runbook 指南 §19） |
| 多模态升级位 | GLM-5.3-Flash（320B/A18B，FP8 全量 306G） | 同上（**量化前置**） | N1 下载中 | ⬇ ~117MB/s；**FP8 超双机容量，到位后走 §3.4 NVFP4 量化→TP=2** |
| 轻旗舰/降级位 | Qwen3.8-Flash-Next | vllm 单机 | N1 下载中 | ⬇（高并发低成本层） |
| 视频生成 | MiniMax-H3-NF4（DiffSynth 系） | 官方 DiffSynth 容器化 | N1 下载中 | ⬇（未来 `/v1/videos` 候选） |
| 组件 | Qwen3-Embedding/Reranker-8B | vllm 官方镜像 serve | N2（现 systemd ⏸） | ⏸ → §六容器化 |
| 冷库 | NAS `/Volume1/yyc3_hd/data/{厂商}/` 全量 | — | NAS | 📋 备份源（含 GLM/Qwen3.8 完整副本） |

### 3.2 支柱一 · 镜像部署规范

1. **只跑官方容器**（vllm/ngc/DockerHub 官方；自研代码仅官方基底薄封装；宿主零业务进程——v1.3 §15 铁律）
2. 通道决策树：NVIDIA 系→nvcr 直拉｜DockerHub→daocloud 镜像源｜被墙仓库→hf-mirror｜双机分发→**QSFP tar 管道**（实测 20G 镜像/159.6G 模型均字节校验一致）
3. 旗舰容器脚本锚定 `/home/yyc3/dsv4_*.sh`（**/tmp 会被清理**——V4 踩坑修正），restart 策略 unless-stopped

### 3.3 支柱二 · 加速

| 手段 | 状态 | 要点 |
|------|------|------|
| QSFP 张量并行 | ✅ | ray `--node-ip-address 10.100.168.x` 锁专线（**VLLM_HOST_IP 在 ray 后端无效**——V4 定档）；NCCL 三参数（IFNAME=QSFP口/IB_HCA=mlx5_0/GDR_LEVEL=5） |
| 批处理四件套 | ✅ 旗舰已带 | `--max-num-batched-tokens 8192 --max-num-seqs 32 --enable-prefix-caching --kv-cache-dtype fp8` |
| CUDA Graph | ✅ | 引擎预热自动捕获（mixed-prefill+decode 全图） |
| NCCL 版本约束 | ⚠️ | 镜像内 2.28.9 可跑 PYNCCL 小缓冲（现役证明）；**集合通信大缓冲场景须 2.30.7 容器**（门禁定档） |
| 内存红线 | ✅ | 旗舰 util 0.72；多模型共存须 ≤0.55（历史 OOM 事故档）；启动窗口暂停大流量下载 |

### 3.4 支柱三 · 量化

| 路线 | 状态 | 适用 |
|------|------|------|
| FP8 现役 | ✅ | DSV4-Flash 官方 FP8 直跑（KV 同 FP8） |
| **NVFP4 产线** | 📋 待 GLM 到位 | TRT-LLM 容器 `quantize.py --qformat fp4 --calib_size 512`（指南 §八）：GLM-5.3-Flash 306G→~170G→TP=2 85G/机；注意力 BF16+FFN NVFP4+KV FP8 混合，压 8x 损失<2% |
| Spark-NIM 现成量化 | ✅ 备选 | 图灵 Qwen3.6-35B-A3B-FP8 Spark-NIM（N2 镜像在位，21.9G 自含）即启即用 |

---

## 四、NemoClaw-OpenClaw · 模型链接（④层）

### 4.1 双机实况（2026-09-03）

| 节点 | 形态 | 模型链接 | 状态 |
|------|------|----------|------|
| **N1** | OpenClaw agent（remote 网关模式）+ 本地沙箱 | `~/.openclaw/openclaw.json` → **ws://100.65.172.88:18789**（NAS 统一网关，token My1210）；推理由网关路由 | ✅ 沙箱 healthy |
| **N2** | NemoClaw 本地全栈（沙箱+推理后端） | `~/.nemoclaw/onboard-session.json`: provider=**vllm-local** → `host.openshell.internal:8000/v1`（nemoclaw-vllm 容器, Qwen3.6-27B-FP8, GPU 直通 native-only） | ⏸ **两容器均停**：nemoclaw-vllm 为旗舰腾内存（20h 前）；沙箱 1h 前 OOM-137（旗舰内存压力） |

### 4.2 模型链接改造（旗舰时代的衔接决策）

```
选项 A（推荐·零改动等恢复）: 旗舰验证期结束后 → docker start nemoclaw-vllm(27B)
        代价：与旗舰抢内存，需旗舰降 util 或 N2 分时
选项 B（旗舰直连·改一行）: NemoClaw provider 改指 N1:8001
        ~/.nemoclaw/onboard-session.json: endpointUrl → http://10.100.168.2:8001/v1
        模型名 → deepseek-v4-flash（sandboxes.json 同步）
选项 C（设计正态·NAS 统一网关）: 按 N1 专属文档《NemoClaw-多设备协同架构》
        inference-routing.yaml: vllm-distributed → 负载均衡 :8002 → N1:8001/N2 各 vLLM
        两机 agent 全走 ws://NAS:18789，模型路由集中管理
```
> 衔接建议：短期 B（一行改动即让 N2 沙箱用上旗舰），中期 C（与网关 A 线 upstream pool 同构收敛）。沙箱 OOM 教训：旗舰 era 重建沙箱须限内存（--memory）。

---

## 五、yyc3-family-ai-agents · 模型搭配（⑤层）

> 代码真身 N2 `~/yyc3-102-projects/yyc3-family-ai-agents/`；8×Flask（agent_server.py 通用壳）+ 治理中枢（SQLite :25700）；**全部模型调用仅依赖 `VLLM_ENDPOINT` + `VLLM_MODEL` 两个 env——模型无关**。

### 5.1 模型搭配矩阵（SLA 驱动）

| Agent | 端口 | SLA | 搭配模型 | 端点指向 |
|-------|------|-----|----------|----------|
| 元启·天枢 | 25600 | <500ms | **deepseek-v4-flash**（决策旗舰） | N1:8001 |
| 言启·千行 | 25601 | <200ms | Qwen3.8-Flash-Next（到货后）/ 暂同旗舰 | 同上 |
| 语枢·万物 | 25602 | <2s | deepseek-v4-flash + RAG | :8001 + :8100/8101 |
| 预见·先知 | 25603 | <3s | deepseek-v4-flash（长推演） | :8001 |
| 千里·伯乐 | 25604 | <500ms | Qwen3-Embedding-8B + Reranker-8B | :8100/:8101 |
| 智云·守护 | 25605 | <100ms | Nemotron-3.5-Content-Safety + NIM 云端管线 | 本地+云 |
| 格物·宗师 | 25606 | <1s | deepseek-v4-flash（编码主场景） | :8001 |
| 创想·灵韵 | 25607 | <2s | GLM-5.3-Flash（到货后·中文创意）/ 暂旗舰 | :8001 |
| 治理中枢 | 25700 | — | 无模型依赖（审计/预算/协同/ACS/图谱） | — |

### 5.2 部署衔接

容器化上线（python:3.11-slim 薄封装 + compose，指南 §15.4；构建上下文=N2）；compose 全局 env 两行即完成旗舰接入：
```yaml
VLLM_ENDPOINT: http://10.100.168.2:8001/v1
VLLM_MODEL: deepseek-v4-flash
```
（参考档案：N1 `YYC3-专属文档/` 内蓝图实战 03/04/08 号文档为 SLA 与映射设计原典）

---

## 六、RAG 模型全链路（⑥层）

| 环节 | 模型/引擎 | 现状 | 恢复/升级路径 |
|------|-----------|------|---------------|
| 嵌入 | Qwen3-Embedding-8B（开源多语/代码第一，MTEB 70.58） | ⏸ systemd 停 | **vllm 官方镜像 serve `--task embed`** 容器化 :8100（权重双机在位） |
| 重排 | Qwen3-Reranker-8B | ⏸ 同上 | `--task score` :8101（备选 bge-reranker-v2-m3 A/B） |
| 向量库 | ChromaDB（宿主 ⏸） | ⏸ | **官方 chromadb/chroma 容器** :8102 + 数据卷迁移；量大升 **Milvus**（N1 镜像在位） |
| 解析 | nemotron-ocr-v2（NIM 云 API，区域封锁不影响 API 调用）/ paddleocr 本地 | 📋 | 网关 A 线 P2 `/v1/ocr` 代理 |
| 生成 | deepseek-v4-flash TP=2 | ✅ | RAG 上下文注入 + prefix-cache 命中 |
| 安全 | Nemotron-Safety + 云端 jailbreak/pii | 📋 | 守护三层管线 |

---

## 七、部署时序与验收（总控）

```
当下已完成: 环境✅ 旗舰TP=2✅ 镜像/通道✅ NCCL门禁✅
本周期(随下载完成):
  GLM到位 → NVFP4量化产线 → TP=2 切换验证 → 灵韵/旗舰轮换
  Qwen3.8-Flash-Next到位 → 单机 serve → 千行/降级位
Next(A线联动): RAG容器化恢复 → agents容器化(§五env) → NemoClaw链接改造(§四B/C)
验收基线: /v1/models 与 chat 冒烟 ×每模型；双机内存对称 <110G；P95首token<50ms
```

---

> **YYC³ AI Family** | 言启象限 · 语枢未来 · 🌹 人从众曌众从人 · 亦师亦友亦伯乐
