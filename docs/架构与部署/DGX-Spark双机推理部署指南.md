# YYC³ DGX Spark GB10 双机推理部署 · 模型部署闭环最佳指导文档

> **文档版本**: v1.4.2 | **生成日期**: 2026-09-02
> **v1.4.2**: 新增 **§19 DeepSeek-V4-Flash TP=2 落地 Runbook**（前置检查实测结论 + Phase 0 已完成：旗舰 159.6GB 经 QSFP 196 秒同步 N1 规范路径，46/46 分片核验）
> **文档版本(历史)**: v1.4.1 | **生成日期**: 2026-09-02
> **v1.4.1 勘误**: ① §17 GLM-5.3-Flash 体量**算错修正**：FP8 全量为 **328GB**（下载实测口径，320B 参数 ×1B），**超双机 242G——FP8 不能直跑 TP=2**，正确路径 = NVFP4/INT4 量化（~170G → 85G/机 ✓，走 §八 TRT-LLM 量化产线）或等官方低比特版；② 模型真身路径勘误：设备模型资产在 `~/yyc3-{101,102}-projects/models/`（N1 含 20 款主库 + **GLM-5.3-Flash 328G venv 稳传下载中**），非 `~/models/`（后者为 Day1 临时下载区）；③ 新增 venv-modelscope 下载规范（双节点已建，docs 两份说明）；④ v1.3.1 "yyc3-101-projects 空骨架"结论**撤回**
> **文档版本(历史)**: v1.4.0 | **生成日期**: 2026-09-02
> **v1.4 变更**: 新增 **§17 2026-09 开源模型版图与最优矩阵**——按用户要求**忽略设备存量资产**，基于最新发布的 DeepSeek-V4 / GLM-5.3 / Qwen3.8 系（含 2026-08-26 新发 GLM-5.3-Flash、2026-08-02 Qwen3.8-Max）重做选型；结合 NIM 138 报告 + Hub 官方技术，给出 TP=2 主模型 / RAG 全链路 / yyc3-family-ai-agents 的最佳适配；新增 **§18 API 生产部署建议**（基于 YYC3-0379-World 网关代码库实况）
> **文档版本(历史)**: v1.3.2 | **生成日期**: 2026-09-02
> **v1.3.2 变更（Phase D 改道）**: ① **NIM 区域封锁实测**：NVIDIA 自 2025-02-15 拒绝中国 IP 下载 NIM 镜像/模型（`nvcr.io/nim/*` 与 `nimevents/*` 双双 DENIED；**非 NIM 的 nvcr 拉取不受影响**，pytorch:26.07 即为实证）；替代官方渠道为中国 NIM 合作伙伴（catalog.ngc.nvidia.com/china-nim-distributors，需用户决策开户）。② **双钥匙分工实测**：NGC 钥→`ngc` CLI 目录查询 ✓；NVIDIA Build 钥→`nvcr.io docker login` ✓（已双机配置，运行钥落 `~/nvidia-workbench/.nim-env` 600）。③ **旗舰路径改道为主线**：ModelScope 官方原仓 `deepseek-ai/DeepSeek-V4-Flash`（FP8 原生，与 NAS 副本同规格：46 分片/≈160GB/1M ctx）直下实测 26MB/s → vLLM TP=2 双机分片（80GB/rank）。④ NAS 模型库已重组为厂商子目录（`data/DeepSeek/`、`data/Qwen/`…），历史文档路径需 +1 层。
> **文档版本(历史)**: v1.3.1 | **生成日期**: 2026-09-02
> **v1.3.1 变更（实况校准）**: ① NGC 旧凭据**实测失效**（ngc 403 / docker DENIED）——Phase D 前置明确为"需用户提供新 NVIDIA KEY"；② `yyc3-101-projects` 实为**空骨架**（Agent 代码真身在 N2 `~/yyc3-102-projects`）——§15.4 构建上下文修正为 N2；③ `nvidia-workbench` 真身定性为**12 类 NVIDIA 官方开源库策展**（含 TensorRT-LLM/TransformerEngine/NCCL 源码，每类带目录映射表），宿主 `~/nccl/build`=2.28.9（历史死锁版）留档；④ 双机 `YYC3-专属文档` 各自完整，N2 另有 `DGX-Cluster-Docs` 五卷运维库
> **文档版本(历史)**: v1.3.0 | **生成日期**: 2026-09-02
> **v1.3 变更**: 新增 §十五「官方镜像优先执行方案」——确立**所有部署以 NVIDIA/DockerHub 官方镜像为准绳、杜绝直接部署在宿主机系统**的铁律；结合 2026-09-02 Day1 执行实录（NCCL 2.30.7 门禁通过 / TP=2 ray 双机上线 / 镜像通道全通）给出容器化迁移四阶段方案；**同时废止 fix-n2.sh 第 2 步的 systemd 化方向**（改为容器化，详见 §15.4）
> **文档版本(历史)**: v1.2.0 | **生成日期**: 2026-08-30
> **v1.1 变更**: 双机 NVIDIA 高速互联线已实现互联（2026-08-30 确认）——主推方案由 A 方案（HTTP 分工）切换为 **B 方案（NIM TP=2 张量并行）**，NCCL `all_reduce_perf` 冒烟测试成为唯一剩余门禁
> **v1.2 变更**: **官方向导集群配置完成并全套通过（2026-08-30 截图证据）**——NVIDIA 集群向导 SSH Setup 12/12 ✓、网络性能实测 **210.76 Gbps**（阈值 >180 Gbps，117% 超额）、"Your cluster is ready!" 集群 **YanYuCloud**（2 devices, direct connection）正式就绪
> **适用范围**: yyc3-101 (N1) + yyc3-102 (N2) 双 DGX Spark GB10 推理集群
> **设计前提**: **忽略各设备现有已部署模型**——本文档仅基于 ① 双机硬件底座 ② 已有模型资产池（NAS/macOS 权重库）③ NVIDIA NIM 138 款模型分析 ④ DGX-SPARK-HUB 官方技术核心（镜像/容器/加速）从零设计
> **核心依据**: `DGX-SPARK-HUB-OFFLINE.html`（45 条官方指南）+ `NVIDIA-NIM-全量模型-分析报告.md` + `07-DGX-GB10-MoE架构与模型链路总结报告.md`（NIM 实战）+ 101 优化脚本/configs 实测参数
> **闭环定义**: 资产盘点 → 双机互联 → 镜像底座 → 模型选型 → 量化产线 → 容器编排 → RAG 链路 → 性能加速 → 验证基准 → 监控运维 → 回滚升级（11 环全覆盖）

---

## 一、核心结论（TL;DR）

1. **双机高速互联已通过 NVIDIA 官方集群向导全套验证（2026-08-30 截图证据）——「B 方案 NIM TP=2 张量并行」全面解锁**：SSH Setup 12/12 ✓、网络性能实测 **210.76 Gbps**（官方阈值 >180 Gbps，超额 17%）、集群 **YanYuCloud** 正式就绪（2 devices, direct connection）。部署 §9.3 TP=2 compose 前，跑一次显式 `all_reduce_perf` 做最终留档即可（预期通过）；异常仍可秒退 A 方案。
2. **旗舰模型从 NAS 资产池直接启用，无需新购**：DeepSeek-V4-Flash（284B MoE/A13B，1M 上下文）单机 NVFP4 即可承载，是双机体系的核心推理引擎；GLM-5.1-FP8、Kimi-K2.6、Qwen3.5-122B-A10B 按任务按需加载（不常驻）。
3. **镜像底座全线官方化**（Hub 指南口径）：主推理 `vllm/vllm-openai` + 旗舰 `nvcr.io/nimevents/*` NIM 容器 + 组件 NIM（OCR/嵌入/重排/安全）+ 轻量 `ollama/ollama` + 监控 `nvidia/dgx-dashboard`；统一 CUDA 12.8+ 基镜像。
4. **量化产线标准化 NVFP4 混合量化**（注意力 BF16 + FFN NVFP4 + KV FP8）：内存压缩 8x、精度损失 <2%；Hub g11 提供官方 TRT-LLM `quantize.py --qformat fp4` 流程。
5. **加速四件套必开**：连续批处理 + CUDA Graph + Prefix Caching + KV FP8；进阶叠加推测解码（2-3x）与 TRT-LLM 引擎编译；101 已实测的批处理参数（`max-num-batched-tokens 8192 / max-num-seqs 32 / gpu-mem-util 0.9`）直接复用。

---

## 二、双机硬件底座与官方技术基线

### 2.1 硬件规格（N1/N2 同构）

| 组件 | 规格 | 推理部署意义 |
|------|------|--------------|
| GPU | GB10 Grace Blackwell Superchip（sm_121，Blackwell 架构） | NVFP4 原生硬件支持（第四代 Tensor Core） |
| 统一内存 | 121GB UMA / 每机（双机 242GB） | 单机可载 284B MoE NVFP4 旗舰 |
| 本地盘 | 3.7TB NVMe / 每机 | 常驻模型权重 + NIM 缓存 |
| 互联 | CX-7 QSFP 双口直连（可 RoCE 200Gbps） | TP=2 张量并行的物理基础 |
| 架构 | aarch64 (ARM64) | **必须用 ARM64 原生镜像**（NIM 有 DGX Spark 专用容器） |

### 2.2 软件栈基线（实机已就位）

| 层 | 组件 | 版本 | 状态 |
|----|------|------|------|
| 驱动 | NVIDIA Driver | 580.173.02 | ✅ |
| CUDA | CUDA Toolkit | 13.0（≥12.8 即满足 NIM 基线） | ✅ |
| 通信 | NCCL (sm_121 自编译) | 2.28.9 | ⚠️ 单机可用/跨节点死锁 |
| 精度 | TransformerEngine (FP8) | 2.19.0 源码编译 | ✅ |
| 编译 | TensorRT-LLM | v1.3.0rc12 镜像 | ✅ |
| 运行时 | Docker + NVIDIA Container Toolkit | `--gpus all` 可用 | ✅ |
| OS | DGX OS kernel 6.17.0-1026-nvidia | aarch64 | ✅ |

### 2.3 双机互联现状（2026-08-30 官方向导实测，全套通过 ✅）

| 项 | 实测结果（官方向导截图证据） | 说明 |
|----|------------------------------|------|
| 集群状态 | ✅ **"Your cluster is ready!"** | 集群名 **YanYuCloud**，Topology: 2 devices, direct connection |
| 网络性能 | ✅ **Speed Test 210.76 Gbps**（阈值 > 180 Gbps） | 双 QSFP 链路聚合实测，达官方阈值 117%，接近 ConnectX-7 双口理论峰值 |
| SSH 免密 | ✅ SSH Setup 12/12 全过 | 向导自动完成：密钥对/公钥共享/SSH config/known_hosts/连接测试（N1+N2 各 6 项） |
| 接口 IP | 101: `enp1s0f0np0`=10.100.168.2 + `enP2p1s0f0np0`=10.100.169.2；102: `.168.1` + `.169.1` | 与本文档 §9.3 compose 中 `MASTER_ADDR=10.100.168.2`（N1=rank0）**完全一致，零改动可用** |
| 集群通信 | 🟢 官方向导带宽/延迟检测通过 → NCCL 门禁预期通过 | 显式 `all_reduce_perf` 建议跑一次留档（§5.2）；历史死锁记录见附录 C |

> 注：官方向导注册集群名为 **YanYuCloud**（2026-08-04 手工配置时期记录为 YanYuCloudCube，以向导注册名为准）。向导完成页建议的"复制网络配置 + 运行 workload 示例"与本报告 §5.2 NCCL 留档测试 + §9.3 TP=2 部署正好对应。

---

## 三、模型部署闭环总览

```
┌─────────────────── 模型部署闭环（11 环） ───────────────────┐
│                                                              │
│  ①资产盘点 ──→ ②双机互联 ──→ ③镜像底座 ──→ ④模型选型        │
│      ↑                                              │        │
│      │                                              ▼        │
│  ⑪回滚升级 ←── ⑩监控运维 ←── ⑨验证基准 ←── ⑧性能加速       │
│      ↑              ↑                                │        │
│      │              └────── ⑦RAG链路组件 ←────────────┤        │
│      └──────────────── ⑥容器编排 ←── ⑤量化产线 ←──────┘        │
└──────────────────────────────────────────────────────────────┘
```

---

## 四、Phase ① —— 模型资产池盘点（部署输入）

> 前提：**不依赖任何设备现有部署**，以下资产池是唯一模型来源（NAS 为真源，macOS Max 盘为副本）。

### 4.1 NAS 资产池 `/Volume1/yyc3_hd/data`（真源，NFS 已挂载双机）

| 模型 | 架构 | 权重量级 | 双机部署定位 | 量化方案 |
|------|------|----------|--------------|----------|
| **DeepSeek-V4-Flash** | MoE 284B/A13B，1M ctx | 大 | **核心推理引擎**（编码+智能体） | NVFP4 单机 / TP=2 终态 |
| DeepSeek-V4-Pro | MoE 284B，1M ctx | 大 | 高精度推理备选（混合量化保 BF16 层） | 混合量化 |
| **GLM-5.1-FP8** | 国产 MoE | 中 | 中文政企推理（NIM 分析推荐升级 5.2） | FP8 现成 / NVFP4 |
| **Kimi-K2.6** | MoE 1T/A32B + MoonViT | 大 | 多模态旗舰（视觉编码器与 LLM 分层） | 混合精度 |
| **Qwen3.5-122B-A10B** | 多模态 VLM MoE，262K ctx | 中 | 多模态推理/编码（NVFP4 友好） | NVFP4 |
| Qwen3.5-397B-A17B | 多模态基础 MoE，201 语言 | 大 | 存档级（按需） | NVFP4 |
| Ring-2.6-1T | 超大 MoE | 大 | 存档级（按需） | — |
| **Qwen3-Coder-30B-A3B(-Q4)** | 编码 MoE A3B | 小 | 轻量编码（Q4 直接可用） | Q4 现成 |
| Qwen3-Embedding-8B / Reranker-8B | 组件 | 小 | RAG 检索双件套 | BF16 |
| Qwen3-8B / Qwen3-14B | 稠密 | 小 | 路由/创意轻量层 | GGUF |
| MiniCPM-V-4.6 | 轻量 VLM | 小 | 多模态轻量备选 | BF16 |
| MegaStyle-1.4M | 风格模型 | 中 | 创意辅助 | — |

### 4.2 macOS Max 盘 `/Volumes/Max/models`（副本源）

DeepSeek-V4-Flash / Qwen 全套 / HiDream-ai / Z-Image-Turbo（图像生成）/ Tencent-Hunyuan / Cogvideox-5B（视频）/ Cogagent-9B / yyc3-finetune 微调产物 —— 作为 NAS 的二级备份与图像/视频生成补充资产。

### 4.3 NIM 云端组件池（build.nvidia.com，本地无权重的缺口组件）

`nemotron-ocr-v2`（OCR ★★★★★）· `nemotron-3-embed-1b`（代码嵌入）· `bge-m3`（中文嵌入 ★★★★★）· `llama-nemotron-rerank-1b-v2` · `nemotron-table-structure-v1` / `nemotron-page-elements-v3`（表格/版面）· `nemoguard-jailbreak-detect`（越狱检测）· `gliner-pii`（PII 脱敏）· `parakeet-ctc-0.6b-zh-cn`（中文 ASR 标杆）· `FLUX.1-schnell`（图像生成）—— 均为轻量组件（<10GB），可 NIM 容器本地化或 API 直调。

---

## 五、Phase ② —— 双机互联与基础环境（Hub g08/g35）

### 5.1 互联配置（✅ 官方向导已完成，以下仅复核）

> **2026-08-30 更新**：NVIDIA 官方集群向导已完成全部互联配置（SSH 免密 12/12、网络 210.76 Gbps、集群 YanYuCloud 就绪），以下命令从「配置动作」降级为「复核动作」，开机后任意时刻可验证：

```bash
# 1. 链路复核（向导已配好，仅确认）
ip addr show enp1s0f0np0 && ethtool enp1s0f0np0 | grep "Link detected"
# 预期: N1=10.100.168.2 / N2=10.100.168.1（第二口 10.100.169.x）

# 2. SSH 免密复核（向导已生成密钥对+config+known_hosts）
ssh 10.100.168.2 hostname    # 双向均应免密直连

# 3. 带宽复核（向导实测 210.76 Gbps；重测用）
iperf3 -c 10.100.168.2 && nvidia-smi topo -m
```

### 5.2 NCCL 留档测试（Hub g35 —— TP=2 部署前最终确认，预期通过 ✅）

> 官方向导的网络性能检测（210.76 Gbps > 180 Gbps 阈值）已验证**链路层**就绪；本测试目的为 **NCCL 集合通信层留档**，预期通过。
>
> ⚠️ **历史根因警示（2026-08-10 架构审核报告定档，设备侧 `~/YYC3-专属文档/` 有原件）**：GB10 双机 121GB×2 UMA 对称虚拟地址**超出 int32 范围**，触发 `malloc -24,805,113,728 bytes`，当时定性为"永久架构约束、无官方修复"，并据此采纳 **ADR-4：放弃 NCCL TP=2，双机一律服务级分工 + HTTP**。官方向导 210.76 Gbps 证明的是链路健康，**不推翻**该根因。因此本测试若通过（说明 NVIDIA 已在 NCCL/DGX OS 层修复），方可启用 §9.3 TP=2；若仍挂起，维持 ADR-4，A 方案（HTTP 分工）就是终态而非过渡——高可用架构见配套《YYC3-高可用API架构闭环-最佳指导文档.md》。

```bash
# NCCL 带宽冒烟（预期：无挂起，all_reduce 带宽接近 200Gbps 量级）
mpirun -np 2 --host 10.100.168.1,10.100.168.2 all_reduce_perf -b 8 -e 128M -f 2 -g 1

# 若出现挂起（回退排障路径）：
export NCCL_SOCKET_IFNAME=enp1s0f0np0      # 绑定 QSFP 网卡（勿走 Tailscale/eth0）
export NCCL_IB_HCA=mlx5_0                   # ConnectX-7 RoCE
export NCCL_NET_GDR_LEVEL=5                 # GPUDirect RDMA 全开
export NCCL_DEBUG=INFO                      # 定位卡点
mpirun -np 2 --host 10.100.168.1,10.100.168.2 all_reduce_perf -b 8 -e 128M -f 2 -g 1
```

**决策树**：

```
all_reduce_perf 通过 ──→ ✅ 直接执行 §9.3 B 方案 TP=2 compose（主推，本文档主线）
测试仍死锁 ──────────→ ⚠️ 回落 A 方案（HTTP 分工，§7.3），同时：
                        · 保留 NCCL_DEBUG=INFO 日志提报 NVIDIA（GB10 历史问题复查）
                        · 升级 NCCL ≥2.29 / DGX OS 补丁后重测
```

### 5.3 NIM 前置：NGC 凭据与缓存

```bash
# NGC API Key（注意：密钥勿写入文档，走环境变量）
export NGC_API_KEY=<NGC_API_KEY>
docker login nvcr.io -u '$oauthtoken' -p "$NGC_API_KEY"
# NIM 统一缓存目录（两机一致）
export LOCAL_NIM_CACHE=~/.cache/nim && mkdir -p "$LOCAL_NIM_CACHE" && chmod -R a+w "$LOCAL_NIM_CACHE"
```

---

## 六、Phase ③ —— 容器镜像底座（Hub 官方镜像清单）

### 6.1 推理集群镜像清单（全部来自 Hub 指南，ARM64 原生）

| 用途 | 镜像 | Hub 指南 | 部署节点 |
|------|------|----------|----------|
| 旗舰推理（NVFP4 NIM） | `nvcr.io/nimevents/deepseek-v4-flash:latest` | 101 实战报告 | N1 或 N2（TP=2 时双机） |
| 通用 NIM 微服务 | `nvcr.io/nvidia/nim:latest` | g30 | 按需 |
| Nemotron 系 | `nvcr.io/nvidia/nemotron:latest` | g28 | 安全/组件 |
| 高性能 LLM 推理 | `vllm/vllm-openai:latest` | g02 | N1+N2 |
| RadixAttention 推理 | `lmsysorg/sglang:latest` | g03 | 备选引擎（多模态友好） |
| 轻量 GGUF | `ollama/ollama` | g01/g20 | 轻量层 |
| llama.cpp 服务 | `ghcr.io/ggerganov/llama.cpp:server` | g44 | 边缘备选 |
| TRT-LLM 编译/量化 | `nvidia/tensorrt-llm:latest` | g11/g29 | 量化产线（一次性任务） |
| RAG OCR | `nvcr.io/nimevents/nemotron-ocr-v2:latest` | 101 RAG compose | 组件机 |
| 管理界面 | `ghcr.io/open-webui/open-webui:main` | g01 | 网关层 |
| 监控面板 | `nvidia/dgx-dashboard:latest` | g14 | N1+N2 |
| CUDA 基镜像 | `nvcr.io/nvidia/cuda:12.8.0-base-ubuntu24.04` | Hub 通用 | 自研容器底座 |
| 微调（后续） | `nvidia/llama-factory:latest` / `nvidia/nemo:24.07` / `unsloth/unsloth` | g22/g12/g23 | 训练机（推理之外的扩展位） |

### 6.2 统一拉取脚本

```bash
IMAGES=(
  vllm/vllm-openai:latest
  nvcr.io/nimevents/deepseek-v4-flash:latest
  nvcr.io/nimevents/nemotron-ocr-v2:latest
  nvcr.io/nvidia/nemotron:latest
  ollama/ollama
  lmsysorg/sglang:latest
  nvidia/tensorrt-llm:latest
  nvidia/dgx-dashboard:latest
  ghcr.io/open-webui/open-webui:main
  nvcr.io/nvidia/cuda:12.8.0-base-ubuntu24.04
)
for img in "${IMAGES[@]}"; do docker pull "$img"; done
# NIM 缓存预热（--shm-size=16GB 为官方口径）
docker run -it --rm --gpus all --shm-size=16GB \
  -e NGC_API_KEY -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" -p 8000:8000 \
  nvcr.io/nimevents/deepseek-v4-flash:latest  # 首次拉取模型权重入缓存
```

---

## 七、Phase ④ —— 模型选型与双机分工矩阵（核心决策）

### 7.1 决策原则

1. **单机 121GB UMA 红线**：常驻模型合计 ≤ 95GB（系统预留 15%+ 组件 25% 官方分配比）。
2. **MoE 优先**：GB10 与 MoE 稀疏激活天然匹配（NIM 分析：MoE 速度提升 20x+）；旗舰走 NVFP4。
3. **旗舰不常驻**：DeepSeek-V4-Flash 等大权重从 NAS 按需加载（NVFP4 ~40s / FP8 ~2min / BF16 ~5min）。
4. **组件分层**：推理 LLM、RAG 组件、安全组件、多模态各占独立容器，互不挤占。

### 7.2 B 方案 · NIM TP=2 张量并行（**主推方案** —— 官方集群 YanYuCloud 已就绪，可直接执行）

```
双机 TP=2 分片（DeepSeek-V4-Flash NVFP4，1M 上下文稳定，吞吐翻倍）

N1 rank=0 (10.100.168.2)                    N2 rank=1 (10.100.168.1)
├─ 主 LLM 分片 (权重一半)                    ├─ 主 LLM 分片 (权重一半)
├─ RAG 检索组: Embedding-8B :8100           ├─ OCR 文档解析 :8001
│            + Reranker-8B :8101            ├─ 安全审核系 :8103
├─ 向量库 Milvus/ChromaDB                    ├─ ASR parakeet-zh :8004
└─ 轻量路由 Qwen3-8B :11434                 └─ 多模态 Qwen3.5-122B 按需（TP 任务间隙）
```

**NIM 报告四场景双机组合**（高速互联就绪后全部可选）：

| 业务场景 | 主模型（双机 TP=2） | N1 承载 | N2 承载 |
|--------------------------|---------------------|---------|---------|
| 企业级代码知识库（首选） | DeepSeek-V4-Flash NVFP4 | 主 LLM 分片 + 嵌入 + 向量库 | OCR + 安全护栏 + 重排 |
| 中文政企平台 | GLM-5.1-FP8（→5.2） | 主 LLM 分片 + bge-m3 | OCR + 合规组件 |
| 旗舰智能体平台 | nemotron-3-ultra-550b | 主 LLM 分片 + 工具网关 | 多模态 + 安全 + 语音 |
| 多模态内容平台 | Kimi-K2.6 | 主 LLM 分片 + FLUX | 视频 + 语音 + 审核 |

### 7.3 A 方案 · HTTP 服务级分工（回退方案 —— NCCL 门禁未过时自动采用）

```
N2 (yyc3-102, 10.100.168.1) — 旗舰推理机
├─ NIM: DeepSeek-V4-Flash NVFP4      ~40-60GB   1M ctx，编码/智能体核心
├─ vLLM: Qwen3.5-122B-A10B NVFP4     ~25GB      多模态推理（共享承载）
├─ Ollama: Qwen3-Coder-30B-A3B-Q4    ~18GB      高频轻量编码
└─ 预留训练位: 旗舰切换窗口期释放

N1 (yyc3-101, 10.100.168.2) — 组件服务机
├─ NEM/TEI: Qwen3-Embedding-8B       15GB   向量化 :8100
├─ TEI: Qwen3-Reranker-8B            16GB   重排 :8101
├─ Ollama: nemotron 安全系            9GB    内容安全 :8103
├─ NIM: nemotron-ocr-v2              ~10GB  文档解析 :8001
├─ ASR: parakeet-ctc-0.6b-zh-cn      ~2GB   语音 :8004
└─ 轻量 LLM: Qwen3-8B (GGUF)          8GB   路由/分流 :11434
```

**跨机调用全走 HTTP**（千行路由 → N2 旗舰；文档入库 → N1 OCR；检索 → N1 双件套；安全 → N1 审核层）。NCCL 门禁通过后随时可切换 7.2 B 方案，模型与组件无需重下。

### 7.4 模型 × 资产 × 引擎 × 性能总表

| 模型（资产来源） | 引擎 | 量化 | UMA 占用 | 预期性能 | 部署模式 |
|------------------|------|------|----------|----------|----------|
| DeepSeek-V4-Flash（NAS） | NIM | NVFP4 | ~40-60GB | 单流 40+ tok/s，1M ctx | A:单机 / B:TP=2 |
| Qwen3.5-122B-A10B（NAS） | vLLM | NVFP4 | ~25GB | 30-40 tok/s | A: 常驻多模态 |
| Qwen3-Coder-30B-A3B-Q4（NAS） | Ollama | Q4_K_M | ~18GB | 40+ tok/s | A: 常驻编码 |
| GLM-5.1-FP8（NAS） | vLLM | FP8 | ~40GB | 25-35 tok/s | 按需（中文任务） |
| Kimi-K2.6（NAS） | NIM | 混合 | ~140GB(双机) | 多模态旗舰 | B: TP=2 专项 |
| Qwen3-Embedding/Reranker-8B（NAS） | TEI | BF16 | 31GB | 组件 | A: N1 常驻 |
| nemotron-ocr-v2（NIM） | NIM 容器 | — | ~10GB | 批量文档入库 | A: N1 |
| Nemotron 安全系（NIM） | NIM/Ollama | — | ~9GB | 80+ tok/s 审核流 | A: N1 |
| parakeet-zh-cn（NIM） | NIM 容器 | — | ~2GB | 实时中文 ASR | A: N1 |

---

## 八、Phase ⑤ —— NVFP4 量化产线（Hub g11 官方流程）

### 8.1 量化标准（全线统一）

```yaml
NVFP4 混合量化（NVIDIA 官方推荐）:
  注意力层: BF16        # 精度关键
  FFN 层:   NVFP4       # 75% 压缩
  路由层:   BF16        # MoE 专家路由决策
  KV 缓存:  FP8         # vLLM --kv-cache-dtype fp8
效果: 内存压缩 8x / 精度损失 <2%
已现成资产: NAS 的 *-FP8 权重可直接用；NVFP4 需按下列产线产出
```

### 8.2 TRT-LLM 量化产线（Hub g11 五步）

```bash
# Step1 量化环境（TRT-LLM 容器）
docker run --gpus all -it --rm -v ~/.cache/huggingface:/root/.cache/huggingface \
  -v /mnt/yyc3_hd:/models nvidia/tensorrt-llm:latest /bin/bash

# Step2 取源权重（NAS 真源挂载）
# mount -t nfs 100.65.172.88:/Volume1/yyc3_hd/data /mnt/yyc3_hd

# Step3 执行 NVFP4 量化（官方命令，校准样本 512）
python ../examples/quantization/quantize.py \
  --model_dir /models/DeepSeek-V4-Flash \
  --dtype float16 --qformat fp4 \
  --output_dir /models/DeepSeek-V4-Flash-NVFP4 \
  --calib_size 512

# Step4 产物验证（TRT 引擎试跑）
python ../examples/scripts/run.py --engine_dir /models/DeepSeek-V4-Flash-NVFP4 \
  --max_output_len 512 --tokenizer_dir /models/DeepSeek-V4-Flash

# Step5 显存/效果对比
nvidia-smi --query-gpu=memory.used --format=csv
```

> 提示：NIM 官方容器（`NIM_NVFP4_ENABLE=true`）内置 NVFP4 支持时无需自量化，优先用官方 NVFP4 NIM 镜像；自量化产线用于 NAS 上的无 NIM 版本权重（如 Qwen3.5-122B、GLM-5.1）。

---

## 九、Phase ⑥ —— 容器编排（双机 docker-compose 全量）

### 9.1 N2 · 旗舰推理机 `docker-compose-n2.yml`

```yaml
version: '3.8'
services:
  # 旗舰推理 — DeepSeek-V4-Flash NVFP4（101 实战参数）
  deepseek-nim:
    image: nvcr.io/nimevents/deepseek-v4-flash:latest
    container_name: deepseek-main
    restart: unless-stopped
    shm_size: '16gb'
    environment:
      - NIM_NVFP4_ENABLE=true
      - NIM_MAX_MODEL_LEN=1000000
      - NIM_TENSOR_PARALLEL_SIZE=1        # A 方案单机；B 方案改 2
    ports: ['8000:8000']
    volumes:
      - /mnt/yyc3_hd/data/DeepSeek-V4-Flash-NVFP4:/models:ro
      - ~/.cache/nim:/opt/nim/.cache

  # 多模态推理 — Qwen3.5-122B-A10B（SGLang RadixAttention，Hub g03）
  qwen-vl:
    image: lmsysorg/sglang:latest
    restart: unless-stopped
    command: >
      python3 -m sglang.launch_server
      --model-path /models/Qwen3.5-122B-A10B
      --port 30000
    ports: ['30000:30000']
    volumes: ['/mnt/yyc3_hd/data/Qwen/Qwen3.5-122B-A10B:/models:ro']

  # 高频轻量编码 — Qwen3-Coder-30B-A3B-Q4（Hub g01 容器化）
  ollama-coder:
    image: ollama/ollama
    restart: unless-stopped
    ports: ['11434:11434']
    volumes: ['ollama-coder:/root/.ollama']

volumes: { ollama-coder: {} }
```

### 9.2 N1 · 组件服务机 `docker-compose-n1.yml`

```yaml
version: '3.8'
services:
  # OCR 文档解析（101 RAG compose 实战参数）
  nemotron-ocr:
    image: nvcr.io/nimevents/nemotron-ocr-v2:latest
    restart: unless-stopped
    environment:
      - OCR_BATCH_SIZE=16
      - OCR_TABLE_EXTRACT=true
    ports: ['8001:8000']

  # 嵌入/重排双件套（TEI，组件端口对齐 YYC³ 现网 8100/8101）
  embedder:
    image: ghcr.io/huggingface/text-embeddings-inference:latest  # ARM64
    restart: unless-stopped
    command: --model-id /models/Qwen3-Embedding-8B --port 8100
    ports: ['8100:8100']
    volumes: ['/mnt/yyc3_hd/data/Qwen/Qwen3-Embedding-8B:/models:ro']

  reranker:
    image: ghcr.io/huggingface/text-embeddings-inference:latest
    restart: unless-stopped
    command: --model-id /models/Qwen3-Reranker-8B --port 8101
    ports: ['8101:8101']
    volumes: ['/mnt/yyc3_hd/data/Qwen/Qwen3-Reranker-8B:/models:ro']

  # 安全审核（nemotron 系，Hub g28）
  safety:
    image: nvcr.io/nvidia/nemotron:latest
    restart: unless-stopped
    ports: ['8103:8000']

  # 中文 ASR（parakeet NIM）
  asr:
    image: nvcr.io/nim/parakeet-ctc-0.6b-zh-cn:latest
    restart: unless-stopped
    ports: ['8004:8000']

  # 轻量路由 LLM
  router-llm:
    image: ollama/ollama
    restart: unless-stopped
    ports: ['11435:11434']
    volumes: ['ollama-router:/root/.ollama']

  # 监控面板（Hub g14）
  dashboard:
    image: nvidia/dgx-dashboard:latest
    restart: unless-stopped
    ports: ['8888:8888']
    volumes: ['/var/run/docker.sock:/var/run/docker.sock']

volumes: { ollama-router: {} }
```

### 9.3 B 方案 · TP=2 编排（**主推——官方集群已就绪**；101 实战 compose + RoCE/GPUDirect 强化）

```yaml
# docker-compose-dgx.yml（每机一份，rank 不同）
services:
  deepseek-node1:            # N1: rank=0
    image: nvcr.io/nimevents/deepseek-v4-flash:latest
    shm_size: '16gb'
    environment:
      - NIM_TENSOR_PARALLEL_SIZE=2
      - NIM_TENSOR_PARALLEL_RANK=0
      - NIM_MASTER_ADDR=10.100.168.2      # 主节点 QSFP 地址
      - NIM_MASTER_PORT=29500
      - NIM_NVFP4_ENABLE=true
      - NCCL_SOCKET_IFNAME=enp1s0f0np0    # 绑定 QSFP 高速互联网卡
      - NCCL_IB_HCA=mlx5_0                # ConnectX-7 RoCE
      - NCCL_NET_GDR_LEVEL=5              # GPUDirect RDMA 全开
    ports: ['8000:8000']
  deepseek-node2:            # N2: rank=1，MASTER_ADDR 同指 N1
    shm_size: '16gb'
    environment:
      - NIM_TENSOR_PARALLEL_SIZE=2
      - NIM_TENSOR_PARALLEL_RANK=1
      - NIM_MASTER_ADDR=10.100.168.2
      - NIM_MASTER_PORT=29500
      - NIM_NVFP4_ENABLE=true
      - NCCL_SOCKET_IFNAME=enp1s0f0np0
      - NCCL_IB_HCA=mlx5_0
      - NCCL_NET_GDR_LEVEL=5
```

**启动顺序**：先起 rank=0（N1）等待 `29500` 监听 → 再起 rank=1（N2）→ 双机 `curl :8000/v1/models` 验证。任一异常按 §14.1 方案级回滚（TP=2 → TP=1 秒退单机）。

---

## 十、Phase ⑦ —— RAG 全链路组件部署（六层闭环）

```
①文档解析   nemotron-ocr-v2 (N1:8001) ── 备选 paddleocr（中文票据）
②表格/版面  nemotron-table-structure-v1 / page-elements-v3 (NIM API)
③向量化     本地 Qwen3-Embedding-8B (N1:8100) ── 云端增强 bge-m3 / nemotron-3-embed-1b(代码)
④向量存储   Milvus（GPU 加速，官方推荐）/ ChromaDB（轻量备选）
⑤检索重排   Qwen3-Reranker-8B (N1:8101) ── 云备 llama-nemotron-rerank-1b-v2
⑥主推理+安全 DeepSeek-V4-Flash (N2:8000) + nemotron 安全系 (N1:8103)
```

**分块规范**：`chunk_size=500 / overlap=50`（RecursiveCharacterTextSplitter）；检索 Top-20 → 重排 Top-5 → 上下文组装（结果+查询+Agent 人格+记忆）→ 主推理（prefix cache）→ 安全过滤 → 带来源引用输出。

---

## 十一、Phase ⑧ —— 性能加速套件（官方核心）

### 11.1 vLLM 批处理四件套（101 实测参数直接复用）

```bash
docker run -d --name vllm-opt --restart unless-stopped --gpus all -p 8000:8000 \
  -v /mnt/yyc3_hd/data/Qwen/Qwen3.5-122B-A10B:/models:ro \
  vllm/vllm-openai:latest \
  --model /models/Qwen3.5-122B-A10B \
  --tensor-parallel-size 1 \
  --max-num-batched-tokens 8192 \      # 连续批处理：提升 GPU 利用率
  --max-num-seqs 32 \                  # 并发序列数
  --gpu-memory-utilization 0.9 \       # UMA 上限（多模型并存时降到 0.6）
  --enable-prefix-caching \            # 前缀缓存：Agent 人格/系统提示复用
  --kv-cache-dtype fp8 \               # KV FP8：显存减半
  --max-model-len 32768 \
  --dtype auto --host 0.0.0.0 --port 8000
```

配置化版本见 `configs/vllm_batch_config.yaml`（含 CUDA Graph 开关、Prometheus :8002 指标导出、限流 60 req/min、deadline 调度策略）。

### 11.2 进阶加速（按需叠加）

| 技术 | 效果 | 官方命令（Hub） |
|------|------|-----------------|
| 推测解码（g34） | 2-3x 延迟优化 | `--speculative-model <小模型> --num-speculative-tokens 5` |
| TRT-LLM 引擎编译（g29） | kernel 级最优 | `build.py --use_gpt_attention_plugin float16 --use_gemm_plugin float16` |
| SGLang RadixAttention（g03） | 多轮对话前缀命中 | `sglang.launch_server`（多模态场景优选） |
| NCCL 调优（g35） | 跨节点带宽最大化 | `all_reduce_perf` 基准后定 `NCCL_SOCKET_IFNAME` |

---

## 十二、Phase ⑨ —— 验证与基准（部署验收门禁）

```bash
# 1. 服务健康（每个容器）
curl -s http://<host>:8000/v1/models && curl -s http://<host>:8000/health

# 2. 推理冒烟（OpenAI 兼容，Hub g02/g30 口径）
curl -X POST http://10.100.168.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-ai/deepseek-v4-flash",
       "messages":[{"role":"user","content":"用Python写快速排序"}],"max_tokens":500}'

# 3. 双机带宽（每次拓扑变更后）
iperf3 -c 10.100.168.2 && nvidia-smi topo -m

# 4. 性能基准（记录 tok/s / P95 / 并发）
#    基准容器: vllm bench / vllm's benchmark_serving.py
docker logs vllm-opt --tail 50 && watch -n 1 nvidia-smi
```

**验收指标**（NIM 报告口径）：GPU 利用率 >60% · 推理延迟 P95 <50ms（首 token）· 并发 ≥32 路 · 服务可用性 >99.9% · DeepSeek-V4-Flash 单流解码 ≥40 tok/s。

---

## 十三、Phase ⑩ —— 监控运维

| 层 | 工具 | 部署 |
|----|------|------|
| 节点面板 | DGX Dashboard（Hub g14） | `docker run -d -p 8888:8888 -v /var/run/docker.sock:/var/run/docker.sock nvidia/dgx-dashboard:latest` |
| 硬件 | NVIDIA DCGM | 随驱动（`nvidia-smi topo -m` / `dmon`） |
| 服务指标 | vLLM Prometheus（:8002）→ Grafana | `vllm_batch_config.yaml monitoring 段` |
| 日志 | 容器日志轮转 + Loki | logrotate 已配置（rotate 5 / 100M / compress） |
| 脚本 | `gpu_monitor.sh` / `image_check.sh` | 101 scripts 目录 |

**日常巡检**：UMA 水位（>95% 告警）· NVMe 余量 · NIM 缓存增长 · QSFP 链路丢包 · NAS Volume1 容量（63% 起）。

---

## 十四、Phase ⑪ —— 回滚与升级路径

### 14.1 回滚策略

1. **容器级**：所有服务 `restart: unless-stopped` + 镜像 tag 固化（禁 `latest` 入生产，量化产线产物带 `NVFP4` 后缀版本目录）。
2. **模型级**：NAS 真源只读挂载（`:ro`），加载失败即回退上一个量化版本目录。
3. **方案级**：B 方案（TP=2）异常 → `NIM_TENSOR_PARALLEL_SIZE` 回 `1`，秒级退回 A 方案单机形态。

### 14.2 升级路线

```
当前: 官方集群向导全套通过（SSH 12/12 + 210.76 Gbps + YanYuCloud 就绪）→ §5.2 NCCL 留档测试（预期通过）
  ├─ 通过 → B 方案 NIM TP=2（DeepSeek-V4-Flash 双机分片，吞吐翻倍，1M 上下文）【主推，直接执行 §9.3】
  └─ 未过 → A 方案 HTTP 分工过渡 + NCCL_DEBUG 日志提报 NVIDIA + 升级补丁重测
中期: RoCE 200Gbps + GPUDirect RDMA 全面调优（NCCL_IB_HCA/GDR_LEVEL 压榨峰值带宽，向实测 210.76 Gbps 看齐）
终态: 双机统一推理池 —— 旗舰 TP=2 常驻 + NAS 按需加载 + NIM 云端组件弹性补充
       （扩展位: Hub g38 交换机星型可接第三台，g09 环形拓扑）
```

---

## 附录 A：一页命令速查

```bash
# 互联
iperf3 -c 10.100.168.2; nvidia-smi topo -m
# NIM
docker run --gpus all --shm-size=16GB -p 8000:8000 -e NGC_API_KEY \
  -v ~/.cache/nim:/opt/nim/.cache nvcr.io/nimevents/deepseek-v4-flash:latest
# vLLM 优化四件套
--max-num-batched-tokens 8192 --max-num-seqs 32 --gpu-memory-utilization 0.9 \
--enable-prefix-caching --kv-cache-dtype fp8
# NVFP4 量化
quantize.py --model_dir <src> --qformat fp4 --calib_size 512
# 验证
curl http://<host>:8000/v1/models; watch -n 1 nvidia-smi
```

## 附录 B：UMA 预算表

**A 方案稳态（回退形态）**：

| 节点 | 常驻项 | 合计 | 预留 |
|------|--------|------|------|
| N2 | DeepSeek-V4-Flash NVFP4 (~55GB) + Qwen3.5-122B (~25GB) + Coder-Q4 (~18GB) + 系统 (~10GB) | ~108GB | 13GB（旗舰切换窗口） |
| N1 | Embedding 15 + Reranker 16 + OCR ~10 + 安全 9 + ASR 2 + 路由 8 + 系统 ~10 | ~70GB | 51GB（可承接 Kimi/GLM 按需加载） |

**B 方案 TP=2 稳态（主推形态，NCCL 门禁通过后）**：

| 节点 | 常驻项 | 合计 | 预留 |
|------|--------|------|------|
| N1 | 主 LLM 分片 (~28GB) + Embedding 15 + Reranker 16 + 向量库 ~5 + 路由 8 + 系统 ~10 | ~82GB | 39GB |
| N2 | 主 LLM 分片 (~28GB) + OCR ~10 + 安全 9 + ASR 2 + 系统 ~10 | ~59GB | 62GB（训练/记忆层/Kimi 按需） |

## 附录 C：源依据索引

> **2026-08-30 工作区精简声明**：本目录最终仅保留 `DGX-SPARK-HUB-OFFLINE.html`、本文档、《YYC3-高可用API架构闭环-最佳指导文档.md》三份。下表"位置"列原文件中——DGX-101/102 专属内容在两台设备本机 `~/YYC3-专属文档/`（及 `~/yyc3-102-projects/`）有完整同步副本；顶层拓扑/ECS/0379/盘点等文档的关键信息已固化进《高可用API架构闭环》附录 A-C。

| 来源 | 内容 | 保全位置 |
|------|------|
| `DGX-SPARK-HUB-OFFLINE.html` | 45 条官方指南：g01 Ollama / g02 vLLM / g03 SGLang / g08 双机集群 / g10·g38 交换机 / g11 NVFP4 / g14 Dashboard / g28 Nemotron / g29 TRT-LLM / g30 NIM / g34 推测解码 / g35 NCCL / g37 多模态 + 全量镜像清单 |
| `NVIDIA-NIM-全量模型-分析报告.md` | 138 款 10 大类 / 双机 TP=2 组合 / NVFP4 标准 / 行业链路 |
| `07-DGX-GB10-MoE架构与模型链路总结报告.md`（101） | NIM 实战命令 / docker-compose-dgx.yml / docker-compose-rag.yml / RAG 六层选型 |
| `scripts/start_optimized_vllm.sh` + `configs/vllm_batch_config.yaml`（101） | 批处理四件套实测参数 / 监控限流配置 |
| NAS `/Volume1/yyc3_hd/data` 实录 | 模型资产池真源清单 |
| 双机互联实测（2026-08-04/05 手工配置；**2026-08-30 官方向导正式通过：SSH 12/12 ✓ + 网络性能 210.76 Gbps（阈值 180）+ 集群 YanYuCloud 就绪，截图存证**） | 10.100.168/169.x 拓扑 / NCCL 历史死锁记录与留档决策树 / NFS 挂载 |

---

> **YYC³ AI Family** | 言启象限 · 语枢未来
> 文档管理员: YYC³ 总指挥 | 2026-08-30
> 🌹 人从众曌众从人 · 亦师亦友亦伯乐


---

## 十五、官方镜像优先执行方案（v1.3 · 2026-09-02）

> **铁律**：所有服务一律运行于官方容器（nvcr.io NVIDIA 官方 / DockerHub 官方镜像，DockerHub 经 daocloud 镜像源）；自研代码仅允许以官方镜像为基底做**薄封装**（FROM + 少量 pip/代码）；**禁止在宿主机 systemd 直跑业务进程**（现有 4 个 yyc3-*.service 全部属迁移对象）。

### 15.1 现状违规清单（2026-09-02 盘点）

| 违规项 | 位置 | 现状 | 迁移目标 |
|--------|------|------|----------|
| yyc3-embedding.service | N2 宿主机 systemd + llama-factory-env python | 运行中 :8100 | 官方 `vllm/vllm-openai` serve embedding（§15.3-A） |
| yyc3-reranker.service | 同上 | 运行中 :8101 | 官方 vllm serve reranker（--task score） |
| yyc3-memory.service | 同上 | 运行中 :8102 | 官方 `chromadb/chroma` 容器 + 数据卷迁移 |
| yyc3-node.service | N2 宿主机 | 崩溃循环（手册 §8.2 已知问题） | 直接停用（无对应业务） |
| 治理中枢 + 8 Agent | N2 未部署（fix-n2.sh 原计划 systemd 化） | — | **改容器化**：python:3.11-slim 官方基底薄封装（§15.4） |
| TP=2 ray | 双机容器运行时 `pip install ray` | 可用但每次重启重装 | 薄封装镜像 `yyc3/vllm-ray`（FROM vllm/vllm-openai，§15.5） |

### 15.2 镜像与权重获取通道（Day1 实测全通）

| 通道 | 用途 | 实测 |
|------|------|------|
| `nvcr.io` 直拉 | NVIDIA 官方（pytorch/NIM/TRT-LLM） | ~40MB/s ✅ |
| `docker.m.daocloud.io/library/<img>` | DockerHub 官方镜像源（双机已 tag 等价） | ✅（python:3.11-slim 已双机落地） |
| QSFP 直传（§16 模式） | 双机互传镜像/模型（tar + socket 管道） | 20GB 镜像 / 30.9GB 模型均验证 ✅ |
| `HF_ENDPOINT=https://hf-mirror.com` + `HF_HUB_DISABLE_XET=1`（新 CLI `hf download`） | 模型权重下载 | 31GB 双模型验证 ✅ |
| NAS SMB（Tailscale） | 仅冷数据/小文件（~2MB/s，禁用于加载） | ⚠️ 限用 |

### 15.3 Phase A · N2 三组件容器化替换（半天，端口不变平滑切换）

**A-1/A-2 Embedding/Reranker → 官方 vllm 容器**（替代宿主机 python 服务）：

```bash
# N2：先停宿主机服务腾端口（回退 = systemctl start + docker rm）
sudo systemctl disable --now yyc3-embedding yyc3-reranker
docker run -d --name yyc3-embed --restart unless-stopped --gpus all --shm-size 8g -p 8100:8000   -v /home/yyc3/models/Qwen3-Embedding-8B:/model:ro   --entrypoint python3 vllm/vllm-openai:latest -m vllm.entrypoints.openai.api_server   --model /model --task embed --served-model-name qwen3-embedding-8b   --max-model-len 8192 --gpu-memory-utilization 0.12 --port 8000 --trust-remote-code
docker run -d --name yyc3-rerank --restart unless-stopped --gpus all --shm-size 8g -p 8101:8000   -v /home/yyc3/models/Qwen3-Reranker-8B:/model:ro   --entrypoint python3 vllm/vllm-openai:latest -m vllm.entrypoints.openai.api_server   --model /model --task score --served-model-name qwen3-reranker-8b   --max-model-len 8192 --gpu-memory-utilization 0.12 --port 8000 --trust-remote-code
# 验收: curl :8100/v1/embeddings（OpenAI 格式）/ :8101/score
```
> ⚠️ 接口兼容注意：旧 embedding_server.py 为自定义接口，新容器为 OpenAI 标准；调用方（agent 代码/RAG 链）需按 OpenAI 格式对齐——网关 A 线 P2-1 端点本就是此格式，天然一致。

**A-3 Memory → 官方 ChromaDB 容器**：

```bash
sudo systemctl disable --now yyc3-memory
mkdir -p /home/yyc3/chroma-data && cp -r /home/yyc3/yyc3-102-projects/chromadb/* /home/yyc3/chroma-data/ 2>/dev/null
docker run -d --name yyc3-memory --restart unless-stopped -p 8102:8000   -v /home/yyc3/chroma-data:/data   docker.m.daocloud.io/library/chromadb/chroma:latest
# 验收: curl :8102/api/v2/heartbeat；调用方从自研 memory API 切 Chroma 标准 REST
```

### 15.4 Phase B · 治理中枢 + 8 Agent 容器化（替代 fix-n2.sh 第 2 步）

> **fix-n2.sh 第 2 步（systemd 化）按本节废止**——新原则下不自研服务进系统；第 1 步（停 yyc3-node）与第 3 步（fstab 凭据化）仍有效。

自研代码 = 官方基底薄封装（一次 Dockerfile，双机通用）：

```dockerfile
# ⚠️ v1.3.1 修正：Agent/治理代码真身在 **N2** ~/yyc3-102-projects/
# （yyc3-101-projects 为空骨架：checkpoints/config/data/logs 均空）
# → 构建上下文 = N2；N1 仅作分发目标（QSFP）
# deploy/agents/Dockerfile —— FROM 官方 python:3.11-slim（daocloud 已双机落地）
FROM python:3.11-slim
WORKDIR /app
COPY requirements-agents.txt .          # 由 yyc3-family-ai-agents 依赖整理生成
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-agents.txt
COPY yyc3-family-ai-agents/ ./agents/
COPY governance_hub.py .
```

编排 `deploy/agents/docker-compose.yml`：governance(:25700) + 8×agent（env 同原 systemd 模板：VLLM_ENDPOINT 指向 TP=2 的 :8001）+ `restart: unless-stopped` 开机自启等价于 systemd。构建产物经 QSFP 分发。

### 15.5 Phase C · TP=2 正式化（薄封装 + compose）

```dockerfile
# deploy/dgx/Dockerfile.tp2 —— 官方 vllm 基底 + ray（解决运行时 pip）
FROM vllm/vllm-openai:latest
RUN pip install ray
```
构建 `yyc3/vllm-ray:1.0` 双机导入（QSFP）→ `deploy/dgx/docker-compose-tp2-ray.yml`（head/worker 两 service，参数照 §3.3 验证口径）→ 替换手工容器 tp2-head/tp2-worker。六条踩坑修正全部继承（§tp2-ray-实测验证模式.md）。

### 15.6 Phase D · NIM 旗舰（NGC 钥轮换后）

**v1.3.2 改道（NIM 区域封锁后的主线）**：

```
路线一（主）: ModelScope FP8 原仓 → vLLM TP=2   ← 已启动，实测 26MB/s
  N2: docker run ... modelscope download deepseek-ai/DeepSeek-V4-Flash --local_dir ~/models/DeepSeek-V4-Flash
  完成后 QSFP 同步 N1（160GB ≈ 3 分钟）
  内存规划: N1 停 tp2-27B(腾42G) / N2 停三组件(腾31G) → 双机各 ~90G → 80GB/rank + KV 可行
  vLLM 参数: --tensor-parallel-size 2 --kv-cache-dtype fp8 --max-model-len 131072(1M 按需降)
  组件归位: 三组件按 §15.3 Phase A 容器化后重布（不回宿主机）
路线二（备）: 中国 NIM 合作伙伴渠道（需用户开户决策）→ NVFP4 NIM 容器
```

钥匙落位（已完成）：双机 `docker login nvcr.io`（Build 钥）✓ ｜ N2 `~/.ngc/config`（NGC 钥，ngc 目录查询可用）✓ ｜ 运行钥 `~/nvidia-workbench/.nim-env`（600，禁入 git）✓

### 15.7 执行顺序与依赖（关键路径 2.5 天）

```
A(N2 三组件容器化, 半天) → B(Agent/治理容器化, 1天) → C(TP=2 compose 化, 半天) → D(NIM 旗舰, 待钥)
B 依赖 A 完成（agent 调 embedding/memory 新接口）
C 可与 A 并行（独立容器域）
每 Phase 均可独立回退（systemctl start / docker rm 对偶）
```

### 15.8 收益

宿主机归零业务进程（仅 docker + 挂载）｜ 全部官方基底可追溯可升级｜ 开机自启由 `restart: unless-stopped` 统一｜ 与网关 A 线（OpenAI 兼容契约）天然对齐｜ NCCL≥2.30 条件在官方镜像内天然满足。

---

## 十六、Day1（2026-09-02）执行实录归档

> 完整记录见仓库 `docs/2026-09-02-全链路执行总结报告.md`。本节仅存要点索引：
> NCCL 门禁通过（2.30.7，16GB 压力不复现）→ TP=2 解锁 ｜ QSFP 传输模式（模型 30.9GB/29.4s、镜像 20GB 校验一致）｜ N2 三组件零 sudo 自愈（hf-mirror 三参数）｜ CI/CD GitOps 闭环（Mac 部署桥）｜ NAS sshd 间歇拒绝根因 = TOS 防暴力惩罚（自动化连接须 ≥60s 限频）｜ 安全四项执行。


---

## 十七、2026-09 开源模型版图与最优矩阵（v1.4 · 忽略存量资产重选）

> 选型基准日 2026-09-02：2026 上半年开源生态重组为 **Flash 层**（~97% 参数休眠的万亿级 MoE 配方：DeepSeek-V4-Flash / GLM-5.3-Flash / Qwen3.8-Flash-Next）。硬约束：双机 242GB UMA 总量、FP8 权重须 ≤200GB、TP=2 后每机 ≤100GB 留 KV 余量。

### 17.1 主模型候选矩阵（TP=2 双机张量并行）

| 模型（发布日/许可） | 总参/激活 | 上下文 | FP8 体量 | TP=2 分片 | 双机可部署 | 定位 |
|---------------------|-----------|--------|----------|-----------|------------|------|
| **DeepSeek-V4-Flash**（2026-04/MIT） | 284B / A13B | 1M | 149GB | ~75G/机 | ✅（权重已在 N2） | **主力编码/智能体**——启动即用 |
| **GLM-5.3-Flash**（2026-08-26/MIT）🆕 | 320B / A18B | **1M + 原生多模态** | **328GB（FP8 实测）** | FP8 直跑 ✗ 超容 | ⚠️ **量化后可部署**：NVFP4/INT4 ≈170G → 85G/机 ✓ | 升级位：**N1 venv 稳传下载中**，到位后走 §八量化产线再 TP=2 |
| Qwen3.8-397B-A17B（2026-08 系） | 397B / A17B | 262K~1M | ~200GB | 100G/机 | ⚠️ 紧（KV 需限长） | 大 MoE 备选 |
| Qwen3.8-Flash-Next | ~176B / ~A6B | — | ~90GB | 45G/机 | ✅ 宽松 | 轻旗舰（高并发低成本） |
| Qwen3.8-Max（2.4T，2026-08-02 开放权重） | 2.4T | 1M | 2.4TB | ✗ | ❌ 超双机容量 | 排除（云端专用） |
| DeepSeek-V4-Pro（1.6T/A49B） | 1.6T | 512K | 1.6TB | ✗ | ❌ | 排除 |

**主模型执行结论**：
1. **立即可上**：DeepSeek-V4-Flash FP8（149G 已落 N2，46/46 分片核验）→ §15.6 路线一 TP=2
2. **升级路线（量化前置）**：GLM-5.3-Flash（8/26 新发，MIT，原生多模态 + 1M ctx + 中文优势）——FP8 全量 328G **超双机容量，不可直跑**；已在 N1 venv-modelscope 稳传下载（328G 源权重），到位后经 §八 TRT-LLM NVFP4 量化（~170G）→ TP=2 85G/机；多模态并入主模型可省独立 VLM 链
   > 下载规范：双节点统一 `yyc3-*-projects/models/venv-modelscope`（禁系统 pip、1-2 并发稳传，详见 docs 两份说明）
3. **双活搭配建议**：主力 DeepSeek-V4-Flash（编码/智能体）+ 备选 GLM-5.3-Flash（中文/多模态任务）轮换常驻；Qwen3.8-Flash-Next 作高并发降级位

### 17.2 RAG 全链路（2026-09 版图校准）

| 层 | 首选 | 依据（最新实测/榜单） | 落位 |
|----|------|----------------------|------|
| 嵌入 | **Qwen3-Embedding-8B** | 开源第一：MTEB 多语 70.58，100+ 语言**含代码**，指令感知架构（NV-Embed-v2 英文 72.31 但 7.85B/CC-BY-NC 非商用⚠️） | N2 :8100（已部署✓，v1.3 §15.3 容器化继承） |
| 重排 | **Qwen3-Reranker-8B**（备选 bge-reranker-v2-m3 轻量） | 与嵌入同构指令感知；生产实测 bge-v2-m3 有场景优势，A/B 验证 | N2 :8101 ✓ |
| 文档解析 | nemotron-ocr-v2（NIM 云 API）/ paddleocr（本地） | NIM 报告 ★★★★★；本地中文备选 | NIM API（区域封锁不影响 API 调用） |
| 向量库 | ChromaDB（轻量）/ Milvus（N1 镜像已备） | 按量升级路径 | :8102 → Milvus |
| 生成 | 主模型 TP=2（:8001） | — | N1 |
| 安全 | Nemotron-3.5-Content-Safety + NIM 云端 jailbreak/pii | 守护三层管线 | N1/云 |

### 17.3 yyc3-family-ai-agents 最佳适配（代码实况 2026-09-02）

**代码实况**（N2 `~/yyc3-102-projects/yyc3-family-ai-agents/`）：8×Flask Agent（agent_server.py 通用薄壳）+ governance_hub.py（SQLite 独立 :25700）+ docker-compose（python:3.12-slim 基底）——**全部模型调用走 `VLLM_ENDPOINT`（OpenAI 兼容）+ `VLLM_MODEL` 两个环境变量**，天然模型无关。

**适配结论**（换主模型零代码改动）：
```yaml
# docker-compose.yml 全局替换两个 env 即切 TP=2 旗舰：
VLLM_ENDPOINT: http://10.100.168.2:8001/v1     # N1 TP=2 服务（QSFP 主链路）
VLLM_MODEL: deepseek-ai/DeepSeek-V4-Flash       # 或 GLM-5.3-Flash
# 治理中枢不动（无模型依赖）；8 Agent 容器化部署照 v1.3 §15.4
```
SLA 映射（千行 <200ms 类轻请求可指 Qwen3.8-Flash-Next 降级位；伯乐已绑 :8100/:8101；守护绑安全管线）。

---

## 十八、API 生产部署建议（基于 YYC3-0379-World 代码库实况）

> 前提实况：Gateway v2.0.0 生产运行（NAS，api.0379.world 200）；CI 五段绿 + Mac 部署桥 GitOps 已闭环；《Gateway代码分析》五发现（路由死代码/上游硬编码/契约缺 4/测试虚设/观测假数据）待 A 线修复。

### 18.1 生产拓扑（推荐终态）

```
公网 → ECS Traefik(443) → [NAS Gateway 主 ↔ ECS Gateway 副本]（同镜像双活）
        → 智能路由层（A 线 P1 实装后）
          ├→ N1 :8001 TP=2 旗舰（DeepSeek-V4-Flash → GLM-5.3-Flash 轮换）
          ├→ N2 :8100/8101 RAG 组件（容器化后）
          ├→ N2 :25600-07 + :25700 Agent/治理（容器化后）
          └→ 云 API 兜底
```

### 18.2 上线前必办（阻断项，按序）

1. **A 线 P0**（1-2 天）：上游配置化 + 测试地基（详见《Gateway代码分析与落地方案》）——不改则双 DGX 上游接不进网关
2. **A 线 P1**（3-5 天）：路由接线 + 熔断降级——**这是"TP=2 集群可用性=网关路由质量"（ADR-4 教训）的落地件**
3. 安全组三件套（已达标✓）：rate-limit/fail2ban/401

### 18.3 生产规范（建议）

| 域 | 建议 |
|----|------|
| 版本 | 网关镜像 tag 固化（禁 latest）；模型切换走 .env+重启，双活期间新版本先 NAS 后 ECS |
| 可观测 | A 线 P1-4 真实化后接 Grafana；当前勿信 /v1/models/stats（硬编码） |
| 容量 | TP=2 旗舰并发基线 32 路（§十二验收口径）；P95 首 token <50ms 达标后开放放量 |
| 灾备 | NAS↔ECS 网关双活（Mac 桥部署 ECS 副本）；DGX 任一节点故障→路由摘除（熔断）；NAS sshd 限频 ≥60s（TOS 惩罚机制） |
| 密钥 | .nim-env/NGC 双钥已落位；轮换周期 90 天；禁入 git |
| 契约 | 对外 7 端点（chat/models/embeddings/rerank/ocr/asr/health）以 A 线 P2 为准；Agent 层仅暴露 :25700 治理白名单 |

### 18.4 分阶段放量

```
阶段1(内测): api.0379.world → TP=2 旗舰 + RAG 组件，API Key 白名单 10 个，观测一周
阶段2(受控): 开放注册，60 req/min/用户 限流（现有配置），双活网关
阶段3(生产): 智能路由 EWMA 全量 + Qwen3.8-Flash-Next 降级位常驻，SLA 看板公开
```


---

## 十九、DeepSeek-V4-Flash TP=2 落地 Runbook（v1.4.2 · 执行中）

### 19.1 前置检查实测结论（2026-09-02 15:00）

| 检查项 | N1 | N2 | 判定 |
|--------|----|----|------|
| 磁盘 | 2.9T ✓ | 2.8T ✓ | ✅ |
| 旗舰权重 | **159.6G 已落位**（~/yyc3-101-projects/models/DeepSeek-V4-Flash，46/46 分片，QSFP 196s） | 149G（~/models/，46/46） | ✅ 双机就绪 |
| vllm 镜像+ray 模式 | ✓ | ✓ | ✅（§3.3 已验证） |
| NCCL ≥2.30 | pytorch:26.07 ✓ | 同 | ✅（门禁已过） |
| QSFP | 0.087ms | 0.385ms | ✅ |
| 内存 | 64G→**停 tp2-head 后 ~106G** | 46G→**停 tp2-worker+三组件后 ~121G** | ⚠️ 需腾挪（Phase 1） |
| 8001 现状 | **空闲**（tp2-27b serve 已自亡，容器空转占内存） | — | 停掉即回收 |

### 19.2 内存编排（FP8 159.6G → 80G/rank + KV）

```
N1: 停 tp2-head(回收42G) → [旗舰 rank0 80G + KV(util 0.72≈87G)] + 系统/沙箱 ≈ 97G/121G ✓
N2: 停 tp2-worker(42G) + 三组件(33G) → [旗舰 rank1 87G] + 系统 ≈ 97G/121G ✓
⚠️ 旗舰独占期：:8100/8101/8102 组件链暂离（现无生产调用方）；恢复方案=§15.3 容器化后限量归位
    或旗舰验证完成后调低 max-len/util 腾挪
```

### 19.3 Phase 1 切换序列（可逆：全部 docker start/systemctl start 对偶回退）

```bash
# ① 腾内存（tp2-27b serve 已死零影响；三组件暂离）
N1: docker rm -f tp2-head
N2: docker rm -f tp2-worker && sudo systemctl stop yyc3-embedding yyc3-reranker yyc3-memory
# ② 起 DSV4 TP=2（head 先，worker 后——ray 模式，pip ray 容器内装）
N1 head:  vllm serve /model --tensor-parallel-size 2 --distributed-executor-backend ray
          --max-model-len 65536 --gpu-memory-utilization 0.72 --kv-cache-dtype fp8
          --trust-remote-code --enable-prefix-caching --port 8001   (NCCL 三参数照 §3.1)
N2 worker: ray start --address=10.100.168.2:6379 --block
# ③ 验收: /v1/models + chat + 双机内存对称 + QSFP 流量
```

### 19.4 后续衔接

Phase 2 = 三组件容器化归位（§15.3）+ agents env 切 :8001（§17.3 两行改动）；Phase 3 = GLM-5.3-Flash 量化线（328G 下载完成后 §八产线）。
