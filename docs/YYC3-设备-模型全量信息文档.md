# YYC³ 设备-模型全量信息文档
## 多端设备 × 模型路径 × NVIDIA NIM 模型分析 · 全量汇总

> **文档版本**: v1.0.0 | **生成日期**: 2026-08-30
> **数据基准**: 2026-08-21 实况核验（网络拓扑/四端盘点）+ 2026-08-04/05 设备现状采集 + 2026-07-28/29 链路选型定稿
> **体系**: YYC³ (YanYuCloudCube) · 五高五标五化 · 8 大 AI Family Agent 协同
> **汇总范围**: 六节点设备矩阵 / 五端模型资产全量路径 / NVIDIA NIM 138 款模型对照 / 部署量化策略 / Agent 映射 / 行动路线
> **数据来源**: 工作区 20+ 份源文档实测实录（完整索引见附录 B）

---

## 一、核心结论（TL;DR）

1. **六节点体系已成形**：yyc3-33（ECS 公网网关）→ yyc3-45（NAS 存储+网关备）→ yyc3-101/102（DGX Spark 双机推理/训练主阵地）→ yyc3-22（MacBook 主控开发）→ yyc3-77（iMac 热备，离线中）。全链路 `https://api.0379.world` 实测 HTTP 200 打通。
2. **五端模型资产 60+ 款、总量数十 TB**：101 部署 20 款（vLLM 主推理 Qwen3.6-35B-A3B-FP8 运行中）、102 部署 9 款（27B-FP8 vLLM + DPO 训练资产）、macOS 本机 Ollama 3 款 + 外置盘 20 个模型目录、NAS 三级路径 28 个模型目录（旗舰 DeepSeek-V4-Flash/Pro、GLM-5.1、Kimi-K2.6、Ring-2.6-1T 等）、ECS 无本地模型（纯网关）。
3. **NIM 138 款报告与现有资产强互补**：已有推理/编码/多模态/RAG/安全五大类闭环；**缺口为 nemotron-ocr-v2（文档解析）、nemotron-3-embed-1b（代码嵌入）、nemoguard-jailbreak-detect（越狱检测）、gliner-pii（PII 脱敏）、parakeet 系列（工业 ASR）**。
4. **双机 DGX 目标组合已定但未落地**：DeepSeek-V4-Flash（代码知识库）+ GLM-5.2（中文政企）+ Kimi-K2.6（多模态）规划 TP=2 双机部署，权重已在 NAS 仓库，**当前 101/102 实跑 Qwen3.6 系，旗舰资产闲置**。
5. **量化与引擎标准统一**：NVFP4 混合量化（注意力 BF16 + FFN NVFP4 + KV FP8）、vLLM 0.7+（大模型）+ NIM 容器（组件）+ Ollama（轻量）；**NCCL 跨节点死锁是已知 GB10 Bug，双机现实采用 HTTP 服务级分工而非张量并行**。
6. **冗余可回收 ~58GB+**：Qwen3.6-27B-FP8 等模型在 101/102/NAS/macOS 多副本并存，需按「NAS 唯一真源 + 按需加载」策略去重。

---

## 二、设备全景矩阵（六节点）

| 节点 | 设备 | 关键 IP | 核心角色 | 关键服务与端口 | 状态（08-21） |
|------|------|---------|---------|---------------|--------------|
| **yyc3-33** | 阿里云 ECS · Ubuntu 24.04 · 4核/7.1GB/79GB | 公网 39.97.53.176 / TS 100.126.132.112 | 生产网关 / 流量入口 | Traefik 80/443 · Gateway :8000 · PostgreSQL :5432 · Redis :6379 · fail2ban · (监控栈待启动) | ✅ 运行中 |
| **yyc3-45** | TerraMaster F4-423 · N5095 4核/32GB | 192.168.3.45 / TS 100.65.172.88（SSH 端口 9557） | 存储中心 / 网关备 | Gateway v2.0.0 :8000 · Redis :6399 · NFS 模型仓库 · PG14 | ✅ 运行中 |
| **yyc3-101** | DGX Spark GB10 (N1) · 121GB UMA / 3.7TB NVMe | TS 100.65.64.49 / LAN 192.168.3.101 / QSFP 10.100.168.2+169.2 | 推理主节点 | vLLM :8000 (Qwen3.6-35B-A3B-FP8) · Ollama :11434 · ASR/RAG 组件 | ✅ 运行中（内存 110/121G） |
| **yyc3-102** | DGX Spark GB10 (N2) · 121GB UMA / 3.7TB NVMe | TS 100.76.167.103 / LAN 192.168.3.102 / QSFP 10.100.168.1+169.1 | 训练 / 推理节点 | vLLM :8000 (27B-FP8, 256K ctx) · 8 Agent :25600-25607 · 治理中枢 :25700 · Embedding :8100 · Reranker :8101 · Memory :8102 · OpenShell :8080 | ✅ 运行中 |
| **yyc3-22** | MacBook Pro M4 Max · 128GB / 2TB+2TB + 外置 Max 盘 | 192.168.3.22 / TS 本机 | 主控 / 开发中枢 / SSH 枢纽 | Ollama :11434 · Agent :18789 · MLX 微调环境 · 模型资产 363G | ✅ 运行中 |
| **yyc3-77** | iMac M4 · 32GB | TS 100.98.206.18 | 测试 / 热备 | PostgreSQL 副本 :5434 | 🔴 离线 7 天 |

**DGX 硬件与软件基线**（101/102 同规格）：GB10 Grace Blackwell Superchip（sm_121，aarch64）· 驱动 580.173.02 · CUDA 13.0 · NCCL 2.28.9（sm_121 已编译）· TransformerEngine 2.19.0（FP8 就绪）· TRT-LLM v1.3.0rc12 · DGX OS kernel 6.17.0-1026-nvidia · 统一内存 121GB。

---

## 三、网络拓扑与双机互联

### 3.1 全链路请求路径

```
① 公网请求 → api.0379.world (HTTPS 443, TLS 1.3)
② Traefik (yyc3-33) → rate-limit(20req/s) → security-headers → fail2ban 双 jail
③ Gateway API :8000 → 认证 401 拦截 / 健康检查
④ 模型路由（EWMA 延迟+错误率+负载智能调度）
     ├→ DGX-101 vLLM :8000 (Qwen3.6-35B-A3B-FP8 主推理)
     ├→ DGX-102 vLLM :8000 (27B-FP8 备/训练)
     ├→ yyc3-22 Ollama :11434 (yyc3-family-coder)
     └→ 云端 API: DeepSeek / 智谱 GLM (兜底)
⑤ 持久化 → PostgreSQL (ECS 生产主库) + Redis 缓存
⑥ 存储回源 → NAS yyc3-45 NFS (/Volume1 模型仓库, Tailscale 挂载)
⑦ 可观测 → Prometheus + Grafana + Loki (ECS, compose 已就绪待启动)
```

### 3.2 双机互联实况（2026-08-04 新拓扑）

| 链路 | 地址 | 状态 |
|------|------|------|
| N2 (102) QSFP 口1 / 口2 | 10.100.168.1 / 10.100.169.1 (enp1s0f0np0 / enP2p1s0f0np0) | ✅ |
| N1 (101) QSFP 口1 / 口2 | 10.100.168.2 / 10.100.169.2 | ✅ 0% 丢包 0.2-0.3ms，SSH 免密 |
| 以太网 LAN | 192.168.3.101 / 102 | ✅ 保留，ping 0.8ms |
| 旧 link-local 169.254.x.x | 已失效 | ❌ 弃用（已从 /etc/hosts 清理） |
| NAS → 双机 | Tailscale 100.65.172.88 NFS 挂载 | ✅ 2026-08-05 起 N1+N2 均挂载 |

> ⚠️ **关键约束**：NCCL 跨节点集合通信当前**死锁**（GB10 已知 Bug），vLLM TP=2 张量并行**不可用**；跨节点协作走 **HTTP API**（QSFP/以太网均可）。NIM 报告中的双机 TP=2 方案（RoCE 200Gbps + GPUDirect RDMA）是目标架构，落地前以「服务级分工」替代。

### 3.3 别名登录速查

```bash
ssh yyc3-22      # 本机 MacBook (yanyu)
ssh yyc3-33      # ECS 生产网关 (TS 100.126.132.112, root)
ssh yyc3-45      # NAS 存储 (TS 100.65.172.88, YYC3, 端口 9557)
ssh yyc3-101     # DGX 主推理 (TS 100.65.64.49, yyc3-101)
ssh yyc3-102     # DGX 训练 (TS 100.76.167.103, yyc3-102)
# 扩展别名: yyc3-101-vllm (登录即看 nvidia-smi+vLLM 模型) / yyc3-45-gw / yyc3-45-docker / yyc3-202 (备用 ECS)
```

---

## 四、各端模型资产明细（全量路径）

### 4.1 yyc3-101 · DGX Spark 主推理节点（20 款）

**运行实况**：vLLM :8000 常驻 `Qwen3.6-35B-A3B-FP8`（MoE，FP8，`--max-model-len 32768 --kv-cache-dtype fp8`）；Ollama :11434 常驻 yyc3-mgmt-v2 (16G) / yyc3-coder-v1 (18G) / qwen3.6:35b-a3b (23G)；内存 110/121GB。

| 类别 | 模型（磁盘实录 19 条目） | 状态 |
|------|--------------------------|------|
| 主推理 (vLLM) | Qwen3.6-35B-A3B-FP8 | ✅ 运行中 |
| 推理备选 | Qwen3.6-27B / Qwen3.6-27B-FP8 / Qwen3.5-9B / Qwen3.5-4B / Qwen3.5-0.8B / Qwen3-0.6B | ✅ 已部署 |
| 编码 | Qwen3-Coder-30B-A3B-Q4_K_M.gguf / Modelfile-coder / YYC3-Family-Coder / yyc3-manager-v1-Q4_K_M.gguf | ✅ 已部署 |
| 多模态 | MiniCPM-V-4.6 | ✅ 已部署 |
| 图像生成 | HiDream-O1-Image / lingbot-map | ✅ 已部署 |
| 语音 | Qwen3-ASR-0.6B / Qwen3-ASR-1.7B | ✅ 已部署 |
| RAG | Qwen3-Embedding-8B / Qwen3-Reranker-8B | ✅ 已部署 |
| 安全 | Nemotron-3.5-Content-Safety | ✅ 已部署 |

> 源文档《四端盘点》口径为 20 款，`yyc3-101-projects/models/models.md` 磁盘实录 19 条目（Modelfile-coder 计法差异）。专属文档库位于 `YYC3-DGX-101/YYC3-101-专属文档/`（00-11 编号报告 + NVIDIA-ku 技术库 + NemoClaw 运维系列）。

### 4.2 yyc3-102 · DGX Spark 训练/推理节点（9 款 + 训练资产）

**运行实况**：vLLM :8000 常驻 `Qwen3.6-27B-FP8`（83GB 含 KV，max_model_len=262144）；Ollama 另跑 qwen3:32b 等；8 Agent 容器 + 治理中枢 + 三大组件服务全部在线。

| 模型 | 大小 | 架构/量化 | 用途 |
|------|------|-----------|------|
| Qwen3.6-27B-FP8 | 29GB | MoE FP8 | vLLM 主推理（天枢/万物/先知共享） |
| YYC3-Family-Coder | 28GB | Qwen3-14B 40层 BF16 全量合并 | 宗师·前端编码专用（React/Next.js/TS/Tailwind）|
| merged-v2 | 28GB | Qwen3-14B BF16 (6-shard) | DPO 基座 |
| Qwen3-14B | 28GB | BF16 | 备用基座/灵韵创意 |
| MegaStyle-1.4M | 21GB | — | 风格迁移 |
| Qwen3-Reranker-8B | 16GB | BF16 | 伯乐·重排序（:8101 已上线）|
| Qwen3-Embedding-8B | 15GB | BF16 | 伯乐·向量化（:8100 已上线）|
| Nemotron-3.5-Content-Safety | 8.1GB | BF16 | 守护·内容安全 |
| MiniCPM-V-4.6 | 1.2GB | BF16 | 多模态备选 |
| **本地合计** | **~175GB** | | |

**训练资产**（`yyc3-102-projects/`）：
- `yyc3-dpo-v1/`：DPO LoRA 适配器（r=8/α=16，目标 q/k/v/o/gate/up/down_proj），25 个 checkpoint 至 12250 步，eval_rewards_accuracy **99.85%**，偏好区分度 18.32；
- 训练环境：llama-factory-env（torch 2.12.0+cu130 / transformers 5.8.1 / peft 0.18.1 / trl 0.24.0）；yyc3-dpo-env 已废弃复用前者；
- 记忆层：ChromaDB v1.5.9（:8102 API）+ embedding/reranker/memory 三 systemd 服务；
- 待训 LoRA：yyc3-mgmt-v2（企业管理 SFT）、yyc3-security-v1（安全审计 SFT）。

### 4.3 yyc3-22 · MacBook M4 Max 本机

**Ollama 常驻 3 款**（:11434）：

| 模型 | 大小 | 用途 |
|------|------|------|
| yyc3-family-coder:14b-q4 | 9.0 GB | 家族编码主模型 |
| qwen3-coder-30b | 18.6 GB | 代码生成 |
| nemotron-3.5-content-safety | 8.6 GB | 内容安全 |

**外置模型库 `/Volumes/Max/models`**（约 363GB，含 20 个模型目录 + 分析文档）：

```
/Volumes/Max/models/
├── DeepSeek-V4-Flash/          # 旗舰 MoE（附 NIM 分析文档）
├── Cogagent-9B/  Cogvideox-5B/ MiniCPM-V-4.6/
├── HiDream-ai/  Robbyant/  Tencent-Hunyuan/  Z-Image-Turbo/
├── yyc3-finetune/              # 微调工作区
├── Qwen/                       # 11 款：
│   Qwen3-0.6B系之外 → Qwen3-8B / Qwen3-14B / Qwen3-14B-YYC3-merged(-gguf)
│   Qwen3-Coder-30B-A3B-Q4 / Qwen3-Embedding-8B / Qwen3-Reranker-8B
│   Qwen3.6-27B(-FP8) / Qwen3.6-35B-A3B(-FP8)
└── *.md 分析文档（DeepSeek-V4-Flash / Kimi-K2.6 / Qwen3.5-122B-A10B / Qwen3.5-397B-A17B
    + 行业报告 Financial/Legal/Medical/LLM）
```

### 4.4 yyc3-45 · NAS 模型仓库（三级路径，28 个模型目录）

**路径 ① `/Volume1/yyc3_hd/data`（HDD RAID6 主仓库，yyc3_hd 占 7.7TB）**：

| 类别 | 模型目录 |
|------|----------|
| 旗舰 | DeepSeek-V4-Flash / DeepSeek-V4-Pro / Kimi-K2.6 / Ring-2.6-1T |
| 国产 | GLM-5.1 / GLM-5.1-FP8 |
| 基座 | DeepSeek-Base / MegaStyle-1.4M / MiniCPM-V-4.6 |
| Qwen 子目录（11 款） | Qwen3-8B / Qwen3-Coder-30B-A3B(-Q4) / Qwen3-Embedding-8B / Qwen3-Reranker-8B / **Qwen3.5-122B-A10B** / **Qwen3.5-397B-A17B** / Qwen3.6-27B(-FP8) / Qwen3.6-35B-A3B(-FP8) |
| 分析文档 | NVIDIA-DeepSeek-V4-Flash.md / NVIDIA-Kimi-K2.6.md / NVIDIA-Qwen3.5-122B-A10B.md / NVIDIA-Qwen3.5-397B-A17B.md |

**路径 ② `/Volume2/docker/models`（容器轻量层，8 款）**：
ChatGLM3-6B / CodeGeeX4-9B / CodeGeex4-9B_Q8 / Cogagent-9B / Cogvideox-5B / Qwen3-14B / Qwen3-14B-YYC3-merged(-gguf)

**路径 ③ `/Volume3`（NVMe RAID1 SSD 高速池，规划中）**：`ai_hot/{datasets,models,checkpoints,rag_index}` —— 推理热数据/微调权重/向量索引的目标落盘区（当前仅用 2%）。

**存储底座**：md0 RAID6 4×8T HDD（14.5TB，Volume1 用 63%）+ md1 RAID1 2×2T NVMe（1.8TB，Volume3）+ 全盘 SMART 零坏扇区；PG14 `yyc3_kb` RAG 知识库 4GB/19.7 万条 4096 维向量（⚠️ HNSW 索引 INVALID 待重建）。

### 4.5 yyc3-33 · 阿里云 ECS（无本地模型）

8GB 内存轻量云主机，**不承载模型权重**，专职生产网关：Traefik SSL 终结 + rate-limit + fail2ban、Gateway :8000、PostgreSQL :5432 生产库、Redis :6379；监控栈 Prometheus/Grafana/Loki compose 已就绪未启动；曾遭 WordPress 扫描攻击（已 401 拦截 + 加固）。

---

## 五、跨设备模型分布与冗余分析

| 模型 | 101 | 102 | macOS | NAS | 冗余评估 |
|------|:---:|:---:|:-----:|:---:|----------|
| Qwen3.6-27B-FP8 | ✅ | ✅ 运行 | ✅ (Max盘) | ✅ | 🔴 三副本，建议 NAS 唯一真源 + 101/102 按需加载 |
| Qwen3.6-35B-A3B-FP8 | ✅ 运行 | — | ✅ | ✅ | 🟡 双副本可接受（主推理热备） |
| Qwen3.6-27B (BF16) | ✅ | — | ✅ | ✅ | 🟡 FP8 已在用，BF16 可归档 NAS |
| Qwen3-Coder-30B(-Q4) | ✅ | — | ✅ | ✅ | 🟡 Q4 版本四处分布，统一 Q4_K_M |
| Qwen3-Embedding-8B | ✅ | ✅ | ✅ | ✅ | 🔴 四副本，组件建议仅 N1 常驻 |
| Qwen3-Reranker-8B | ✅ | ✅ | ✅ | ✅ | 🔴 同上 |
| MiniCPM-V-4.6 | ✅ | ✅ | ✅ | ✅ | 🟡 1.2GB 轻量，影响小 |
| Nemotron-3.5-Content-Safety | ✅ | ✅ | ✅ | — | 🟡 安全组件本地双备合理 |
| YYC3-Family-Coder | ✅ | ✅ | ✅(gguf) | ✅(merged) | 🟡 微调产物，需版本管理（v1/v2/merged） |
| Qwen3-14B 系 | — | ✅ | ✅ | ✅ | 🟡 微调基座多版本（含 merged/gguf） |
| DeepSeek-V4-Flash | — | — | ✅ | ✅ | ⏳ 旗舰闲置：规划双机部署未执行 |
| GLM-5.1(-FP8) | — | — | — | ✅ | ⏳ 仓库版 5.1，目标版本 5.2 需升级 |
| Kimi-K2.6 | — | — | 分析文档 | ✅ | ⏳ 旗舰闲置 |
| Ring-2.6-1T / Qwen3.5-397B/122B | — | — | 部分 | ✅ | ⏳ 超大模型仅 NAS 存档 |

**去重策略**：以 NAS `/Volume1/yyc3_hd/data` 为唯一真源（Source of Truth），DGX 本地仅保留常驻推理模型；旗舰大模型按需加载（NVFP4 ~40s / FP8 ~2min / BF16 ~5min），不常驻 UMA。预计可释放 58GB+ 本地存储与 UMA。

---

## 六、NVIDIA NIM 138 款模型分析对照

### 6.1 十大类全景 × YYC³ 覆盖度

| # | 大类 | 数量 | YYC³ 现有覆盖 | 关键缺口（建议补） |
|---|------|:----:|--------------|-------------------|
| 1 | 大语言模型（通用/编码/智能体） | 32 | ✅ Qwen3.6 系 + YYC3 微调系 | nemotron-3-ultra-550b（可选旗舰） |
| 2 | 多模态 VLM | 18 | ✅ MiniCPM-V-4.6 | llama-4-maverick-17b / minimax-m3 |
| 3 | RAG 全链路组件 | 21 | ⚠️ Embedding+Reranker 已有 | **nemotron-ocr-v2（文档解析）** / nemotron-3-embed-1b（代码嵌入） |
| 4 | 语音音频 | 15 | ⚠️ Qwen3-ASR-0.6B/1.7B 已有 | **parakeet 系列（工业级多语种 ASR）** |
| 5 | 图像生成 | 9 | ✅ HiDream-O1 / lingbot-map / Z-Image-Turbo | FLUX.1-schnell（灵韵配图可选） |
| 6 | 视频媒体 | 10 | ❌ 无 | 按需（LipSync / 视频超分） |
| 7 | 生物科技 | 13 | ❌ 无 | 按需（AlphaFold2 / OpenFold3） |
| 8 | 自动驾驶/物理 AI | 9 | ❌ 无 | 按需（cosmos3 系） |
| 9 | 安全合规 | 8 | ⚠️ Content-Safety 已有 | **nemoguard-jailbreak-detect + gliner-pii** |
| 10 | 行业工具 | 3 | ❌ 无 | cuOpt（物流）/ FourCastNet（气象） |

### 6.2 旗舰级模型档案（本地 NVIDIA 分析文档 + NIM 报告交叉核验）

| 模型 | 架构 | 上下文 | 核心能力 | 双机 DGX 适配（NIM 报告） | YYC³ 状态 |
|------|------|--------|----------|---------------------------|-----------|
| **DeepSeek-V4-Flash** | MoE 284B 总/A13B 激活，混合注意力 | **1M** | 高速编码+智能体，三档思考模式（非思考/高思维/最大思考） | TP=2 NVFP4，1M 稳定，单流解码 40+ tok/s，编码首选；Marlin MoE 加速 | ✅ 权重在 NAS+macOS，⏳ 未部署（P0） |
| **DeepSeek-V4-Pro** | MoE 284B | 1M | 高阶推理精度，复杂算法/系统级编程 | TP=2 混合量化（保留更多 BF16 层保精度） | ✅ 权重在 NAS，⏳ 未部署 |
| **GLM-5.2**（仓库为 5.1） | 国产旗舰 MoE | 128K（双机） | 智能体工作流/全栈编码/中文生态 | TP=2 NVFP4，中文政企生产首选 | ⏳ NAS 有 5.1(-FP8)，需升级 5.2 |
| **Kimi-K2.6** | MoE **1T 总/A32B**，MLA 注意力，MoonViT 400M 视觉编码器 | 256K | 长时程编码（Rust/Go/Python/前端/DevOps），可编排 300 子智能体/4000 协调步骤 | TP=2 双机承载，视觉编码器与 LLM 分层部署 | ✅ 权重在 NAS，⏳ 未部署 |
| **Qwen3.5-397B-A17B** | 多模态基础 MoE，门控三角洲网络+稀疏 MoE | 262K（YaRN 至 1.01M） | 早期融合视觉语言，**201 种语言**，默认思考模式 | NVFP4 量化可部署 | ✅ 权重在 NAS+macOS，存档 |
| **Qwen3.5-122B-A10B** | 多模态 VLM MoE | 262K（YaRN 至 1.01M） | 多模态代理/编码/视觉理解 | NVFP4 量化可部署 | ✅ 权重在 NAS+macOS，存档 |
| nemotron-3-ultra-550b-a55b | Mamba-Transformer MoE 550B | 1M | 智能体/编码/规划全能旗舰 | TP=2 完美适配（NVIDIA 原生） | ❌ 未引入（可选） |
| nemotron-3-super-120b-a12b | MoE 120B | 1M | 编码/推理/对话均衡 | 单机完美 / 双机高并发 | ❌ 天枢云端备选 |

### 6.3 NIM 组件级选型定论（08 设计 v2 定稿）

| 功能 | 首选 | 部署 | 说明 |
|------|------|------|------|
| 中文嵌入 | **bge-m3** | NIM API | 稠密+多向量+稀疏三模式，中文最强 |
| 本地嵌入 | Qwen3-Embedding-8B | N1 TEI :8100 | 无网络兜底（✅ 已上线） |
| 代码嵌入 | nemotron-3-embed-1b | NIM API | 代码知识库专用 |
| 重排 | Qwen3-Reranker-8B（本地）/ llama-nemotron-rerank-1b-v2（云备） | N1 TEI :8101 | ✅ 已上线 |
| OCR | **nemotron-ocr-v2**（云）/ paddleocr（中文本地备） | NIM API / Docker | 文档入库链路关键缺口 |
| 表格/版面 | nemotron-table-structure-v1 / nemotron-page-elements-v3 | NIM API | 财务报表与版面结构化 |
| 越狱检测 | nemoguard-jailbreak-detect | NIM API | 守护 Layer 1（~100ms） |
| PII 脱敏 | gliner-pii | NIM API | 守护 Layer 3（~50ms） |
| ASR 升级 | parakeet-ctc-0.6b-zh-cn（中文标杆）/ canary-1b（识别+翻译） | NIM 容器 | 工业级语音链路 |
| 图像生成 | FLUX.1-schnell | NIM API | 灵韵营销配图可选 |

---

## 七、部署策略：量化标准与双机链路

### 7.1 NVFP4 混合量化标准（NVIDIA 官方推荐，全线统一）

```yaml
NVFP4 混合量化:
  注意力层: BF16        # 精度关键
  FFN 层:   NVFP4       # 75% 压缩
  路由层:   BF16        # MoE 决策关键
  KV 缓存:  FP8         # 延迟优化
效果: 内存压缩 8x / 精度损失 <2% / MoE 稀疏激活速度提升 20x+
已符合资产: Qwen3.6-27B-FP8, Qwen3.6-35B-A3B-FP8（101/102 在跑）
```

### 7.2 引擎分工与部署基线

| 引擎 | 适用 | 版本/状态 |
|------|------|-----------|
| **vLLM** | 大模型主推理（LoRA 热加载 `--enable-lora`） | 0.7+，101/102 :8000 运行中 |
| **NIM 容器** | MoE 旗舰（ARM64 原生 DGX Spark 专用镜像）与组件模型 | Qwen3-32B NVFP4 NIM ≈40GB UMA / 35-50 tok/s |
| **Ollama** | 轻量 GGUF（路由/创意/编码 Q4） | 101/102/22 :11434 |
| **TEI** | Embedding/Reranker 组件 | 102 :8100/:8101 运行中 |

**环境基线**：DGX OS 6.2+ · Driver 560+（实机 580.173.02）· CUDA 12.8+（实机 13.0）· NCCL 2.29+（实机 2.28.9 sm_121）· 目标互联 RoCE v2 200Gbps ConnectX-7 + GPUDirect RDMA（当前 QSFP 直连替代）。

### 7.3 单机 / 双机最优组合（NIM 报告方案）

**单机（128GB UMA，主 LLM 60% + 组件 25% + 系统 15%）**：

| 场景 | 组合 | 占用 | 并发 |
|------|------|------|------|
| 代码助手+知识库 | deepseek-v4-flash INT4 / glm-5.2 NVFP4 + ocr-v2 + embed-1b + rerank | ~95GB | 3-5 路 |
| 通用企业知识库 | nemotron-3-super-120b + ocr-v2 + bge-m3 + rerank + safety | ~80GB | 8-10 路 |
| 多模态内容生产 | minimax-m3 + FLUX.1-schnell + ocr + safety | ~90GB | 2-3 路 |

**双机 TP=2（256GB 总内存，目标架构）**：

| 场景 | 主模型 | 节点1 | 节点2 |
|------|--------|-------|-------|
| 企业级代码知识库（首选） | DeepSeek-V4-Flash NVFP4 | 主 LLM 分片+嵌入+向量库 | OCR+安全护栏+重排 |
| 中文政企平台 | GLM-5.2 NVFP4 | 主 LLM 分片+bge-m3 | OCR+合规+文档解析 |
| 旗舰智能体平台 | nemotron-3-ultra-550b | 主 LLM 分片+工具网关 | 多模态+安全+语音 |
| 多模态内容平台 | Kimi-K2.6 | 主 LLM 分片+FLUX | 视频+语音+审核 |

> 现实执行顺序：NCCL 死锁修复/绕过前，先以「服务级分工」跑通（见 7.4），TP=2 作为终态目标。

### 7.4 双机现实分工方案（HTTP 服务级拆分，07 选型定稿）

```
N2 (yyc3-102) — 核心推理 + 训练
  vLLM: Qwen3.6-27B-FP8 (83GB) → 升级目标 Qwen3.6-35B-A3B-FP8 (~20GB, 35-45 tok/s)
        再进阶 NVFP4 (~12GB, 50-60 tok/s)，释放 63GB+ 用于训练/记忆层
  宗师 YYC3-Family-Coder (Ollama ~14GB) + ChromaDB 记忆层

N1 (yyc3-101) — 路由推理 + RAG 组件 + 安全
  Ollama: qwen3:8b (千行 8GB) + qwen3:14b (灵韵 28GB) + Nemotron-Safety (8GB)
  TEI: Embedding-8B (15GB) + Reranker-8B (16GB)

跨节点: 全部走 HTTP API（千行路由→N2 vLLM；守护→N1 Safety；伯乐→N1 TEI）
```

---

## 八、8 Agent × 模型 × 设备映射（v2 定稿矩阵）

| Agent | 职能 | 类型 | 主模型（目标） | 引擎 | 节点 | UMA |
|-------|------|------|----------------|------|------|-----|
| 🧠 元启·天枢 | 深度决策 | A 深度推理 | Qwen3-32B NVFP4（NIM）或 Qwen3.6-27B-FP8 共享 | NIM/vLLM | N2 | ~40GB/共享 |
| 🧭 言启·千行 | 快速路由 | B 快速响应 | qwen3:8b | Ollama | N1 | 8GB |
| 🤔 语枢·万物 | 深度分析 | A 深度推理 | Qwen3.6-27B-FP8（共享 vLLM + LoRA 热加载） | vLLM | N2 | 共享 |
| 🔮 预见·先知 | 趋势预测 | A 深度推理 | Qwen3.6-27B-FP8（共享） | vLLM | N2 | 共享 |
| 🎯 知遇·伯乐 | 检索推荐 | C 功能组件 | Qwen3-Embedding-8B + Reranker-8B | TEI | N1 | 31GB |
| 🛡️ 智云·守护 | 安全合规 | C 功能组件 | Nemotron-Safety + NIM 云端三层管线 | Ollama+NIM | N1+云 | 8GB |
| 📚 格物·宗师 | 代码质量 | D 领域专用 | YYC3-Family-Coder（14B，上下文 4K→32K 需扩） | Ollama | N2 | 14GB |
| 🎨 创想·灵韵 | 创意生成 | D 领域专用 | qwen3:14b（temp 0.7）+ FLUX.1-schnell 可选 | Ollama | N1 | 28GB |

**守护三层管线**：Layer1 越狱检测（nemoguard-jailbreak-detect，NIM 云 ~100ms）→ Layer2 内容安全（Nemotron-3.5-Safety，本地 ~50ms）→ Layer3 PII 脱敏（gliner-pii，NIM 云 ~50ms）→ 放行路由 / 审计 + kill switch。

**UMA 预算终态**：N2 ≈ 97GB/121GB（余 24GB）；N1 ≈ 85GB/121GB（余 36GB）；NAS 旗舰按需加载不常驻。

**模型升级路线**：Phase1 现状加固（LoRA 热加载 + N1 激活 + 云端 NIM 组件）→ Phase2 MoE 升级（27B 稠密 83GB → 35B-A3B 20GB / NIM 32B NVFP4 40GB，二选一按 LoRA 优先级）→ Phase3 NAS 旗舰按需（DeepSeek-V4-Flash / GLM-5.1-FP8 / Qwen3.5-122B / Ring-2.6-1T）。

---

## 九、RAG 知识库全链路

```
【摄入·异步】 原始文档
  中文 PDF/图片 → paddleocr(本地) 或 nemotron-ocr-v2(NIM ★★★★★)
  英文文档     → nemotron-ocr-v2 ·  表格 → nemotron-table-structure-v1 ·  版面 → page-elements-v3
  → 分块 (chunk 500 / overlap 50)
  → 嵌入: bge-m3(中文首选,云) / nemotron-3-embed-1b(代码,云) / Qwen3-Embedding-8B(本地 N1)
  → 向量库: ChromaDB (N2 :19500) 或 Milvus (Docker)

【检索·实时】 查询 → 嵌入 → Top-20 检索 → 重排 Top-5 (Qwen3-Reranker-8B 本地 / rerank-1b-v2 云备)
  → 上下文组装 (结果+查询+Agent人格+记忆) → vLLM 推理 (+LoRA+prefix cache)
  → 守护三层过滤 → 回复(含来源引用)
```

**存量资产**：NAS PG14 `yyc3_kb` 已有 197,558 条文档 / 4096 维向量（4GB），⚠️ HNSW 索引 INVALID 是当前 RAG 检索首要瓶颈（P1 重建）。

---

## 十、缺口与行动路线（优先级定稿）

| 优先级 | 行动 | 价值 | 依据 |
|--------|------|------|------|
| **P0** | NAS 挂载 DeepSeek-V4-Flash → 双机部署（先 HTTP 分工验证，TP=2 待 NCCL） | 代码知识库核心能力 | 四端盘点 §4.2 |
| **P0** | N1 (101) Ollama 组件激活：qwen3:8b + Embedding/Reranker 分流 | 千行/伯乐独立模型，释放 N2 | 03 映射 §四 |
| **P1** | 部署 nemotron-ocr-v2（云 API 先行）+ 重建 yyc3_kb HNSW 索引 | RAG 文档入库 + 检索修复 | 08 设计 §五 |
| **P1** | 守护三层管线接入（jailbreak-detect + gliner-pii NIM API） | 安全合规强化 | 08 设计 §4.3 |
| **P1** | ECS 监控栈启动（Prometheus+Grafana+Loki compose 就绪） | 可观测性 | ECS 运维 §五 |
| **P2** | parakeet ASR 系列引入（zh-cn 优先） | 语音链路工业化 | NIM 报告 §2.4 |
| **P2** | 101/102/macOS 模型去重（27B-FP8 三副本等），NAS 唯一真源 | 释放 58GB+ | 四端盘点 §4.2 |
| **P2** | GLM-5.1 → 5.2 升级 + Kimi-K2.6 双机部署 | 中文政企 + 多模态旗舰 | 四端盘点 §4.1 |
| **P2** | DPO LoRA vLLM 热加载 + mgmt-v2/security-v1 LoRA 训练 | Agent 个性化 | 00 现状 §四 |
| 🟡 治理 | 根域 0379.world 配置 / yyc3-77 复活 / NAS Gateway→Ollama 指向 101 | 链路完整性 | 拓扑 §4.2 |

**已知风险**：N2 内存 91/121GB 偏高（多模型并存需 `--gpu-memory-utilization 0.60`）；NAS Volume1 63% 增长监控；YYC3-Family-Coder 上下文仅 4K 需扩 32K；NCCL 跨节点死锁（GB10 Bug）持续跟踪官方修复。

---

## 附录 A：本文档汇总口径说明

- 「已部署/运行中」= 源文档 2026-08-21 实况；「⏳ 规划」= 选型定稿未执行。
- 模型目录数以各端 `models.md` / `Models-路径及详情.md` 磁盘实录为准；101 端「20 款」为盘点口径、磁盘实录 19 条目。
- 旗舰模型参数以本地 NVIDIA-*-*.md 分析文档（build.nvidia.com 模型卡译文）与 NIM 138 款报告交叉核验。
- ⚠️ **安全提示**：`YYC3-22-macOS-本机/models/DeepSeek-V4-Flash.md` 首行含 NVIDIA NGC API Key 明文（nvapi-…），建议轮换该 Key 并从文档中脱敏；本文档不复制该密钥。

## 附录 B：源文档索引

| 源文档 | 位置 | 主要贡献 |
|--------|------|----------|
| YYC3-四端模型全景盘点与NIM落地方案.md | 工作区根 | 四端清单实况 / 缺口 / P0-P2 |
| NVIDIA-NIM-全量模型-分析报告.md | 工作区根 | 138 款 10 大类 / 单双机组合 / 行业链路 |
| YYC3-高可用多设备网络拓扑-可视化架构链路文档.md | 工作区根 | 六节点矩阵 / 请求链路 / HA 现状 |
| YYC3-0379-World-多端部署落地建议与全链路别名登录方案.md | 工作区根 | 部署矩阵 / SSH 别名 / 实测快照 |
| YYC3-33-ECS上线-运维总结与后续执行方案.md | 工作区根 | ECS 现状 / 链路验证 / 安全加固 |
| Models-路径及详情.md（×3） | 22/45/102 目录 | 各端磁盘实录路径 |
| models.md（101/102/22/NAS） | 各端 models/ | 模型清单条目 |
| NAS-存储架构文档.md | 45 目录 + 101 目录 | RAID/LVM/卷/数据库 |
| 00-设备现状分析报告-2026-08-04.md | 102 现状进度 | 双机新拓扑 / 服务状态 / Gap |
| 03-Agent模型映射与设备算力部署分析.md | 102 蓝图实战 | Agent×模型×设备 / UMA 分配 |
| 04-模型链路闭环选型分析.md | 102 蓝图实战 | 需求驱动选型方法论 |
| 07-MoE-NVFP4-双机链路选型分析-2026-07-29.md | 102 蓝图实战 | NCCL 约束 / HTTP 分工 / 升级路径 |
| 08-模型全链路闭环设计v2-2026-07-29.md | 102 蓝图实战 | 三级供给 / 8 Agent 终版矩阵 / RAG 组件 |
| 11-YYC3模型选型与量化技术快速导航.md | 101 专属文档 | NVFP4 标准 / 4 周路线 |
| 07-DGX-GB10-MoE架构与模型链路总结报告.md | 101 专属文档 | MoE 架构 / NIM 部署实战 |
| NVIDIA-*-*.md 旗舰分析（DeepSeek/Kimi/Qwen3.5×2） | 22/NAS models | 模型卡参数 |

---

> **YYC³ AI Family** | 言启象限 · 语枢未来
> 文档管理员: YYC³ 总指挥 | 2026-08-30
> 🌹 人从众曌众从人 · 亦师亦友亦伯乐
