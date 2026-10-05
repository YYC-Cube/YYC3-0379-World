---
file: YYC3-API-全链路闭环文档.md
description: YYC3-0379-World 生产级 API 全链路闭环文档
author: YanYuCloudCube Team <admin@0379.email>
version: v1.2.0
created: 2026-08-30
updated: 2026-10-05
status: active
tags: [api],[full-link],[production],[closed-loop]
category: documentation
---

# YYC3-0379-World API 全链路闭环文档

> **版本**: v1.6.0（文档内文阶段版） | **更新日期**: 2026-10-05（v1.1 实况改版 09-03；v1.3 三能力 09-12；v1.4 全端实勘对齐 09-14；**v1.6 治理日增量 10-05**）
> **网关版本**: v2.0.0 | **生产域名**: `https://api.0379.world`
> **文档定位**: 面向开发、测试、运维三团队的单一事实来源 (Single Source of Truth)
>
> **v1.1 实况改版要点（2026-09-03 基线）**：
> ① **推理底座已换代**——双 DGX 经 NCCL 2.30.7 门禁后，**DeepSeek-V4-Flash（284B MoE/A13B）TP=2 双机张量并行服务在 N1:8001 上线**（QSFP 210Gbps 链路，双机内存对称 96G/121G，64K ctx）；
> ② 部署链已 GitOps 化（Mac 部署桥自动同步，见 §9.5）；③ RAG 组件三件套处于"旗舰独占期暂离"（恢复=容器化 §9.6）；④ 网关代码五缺陷（路由死代码/上游硬编码/4 端点缺失/观测假数据）仍未修——**本文档所有"规划态"均以《Gateway代码分析与落地方案》A 线为准绳**；⑤ 新模型三路在途（GLM-5.3-Flash 306G/Qwen3.8-Flash-Next 131 分片/MiniMax-H3-NF4 视频生成，hf-mirror 通道 29-117MB/s）。
>
> **v1.6 治理日增量要点（2026-10-05 基线）**：
> ① **Model Registry 生产全量纳管**——`/registry/v1/*` 16 端点（12 模型+3 alias+1 drain），PG 五表（005/006 迁移）+ Redis 事件流 `yyc3:registry:events`，数据面 46 条记录（enabled=true 仅 5 真实推理池），`REGISTRY_ENABLED` 灰度开关；
> ② **心跳 TTL 三级阶梯**（90s degraded/180s unreachable/300s 摘除）+ 注册 Agent stdlib 零依赖（30s 心跳/契约端点/优雅 offline）；**X-YYC3-Registry-Token 心跳独立认证已于 10-05 生产启用**（`REGISTRY_HEARTBEAT_TOKEN`，未配置跳过/错值 401/正确 200）；
> ③ **Canary/Shadow 半自动闭环落地**——Redis hash `yyc3:canary:{alias}`（baseline/canary/weight/shadow 四字段），10s 内存缓存，2min 窗口失败≥5 次惰性自动回退 weight=0，审计事件 `canary.auto_rollback`；
> ④ **P0 观测三件套上线**——`yyc3_backend_requests_total{upstream,code}` / `yyc3_backend_ttft_seconds{upstream}` / `yyc3_registry_rollback_total` + Grafana 看板灌入 + 三告警规则（hotswap-gate.rules.yml）；
> ⑤ **日志外送链贯通**——DGX fluent-bit 3.1 tail+Path_Key+cn.lua（12 位短 ID→容器名映射 300s 自刷新）→ NAS Loki 3100（30 天保留+compactor）+ 容器日志看板；
> ⑥ **dsv4 旗舰六天心跳停滞根因修复**（max-model-len 65536→32768 + eager + worker unless-stopped + 编排时序），`dsv4-recover.sh` 五模式剧本（check/recover/rootcause/logs/watch/FORCE）；
> ⑦ 运维动作全脚本化：`health-full.sh` 17/17 全绿、`canary-manage.sh` 六子命令、rebuild-gateway.sh 唯一重建通道。
---

## 目录

- [一、系统架构总览](#一系统架构总览)
- [二、设备矩阵与基础设施](#二设备矩阵与基础设施)
- [三、模型资产清单](#三模型资产清单)
- [四、API 接口规范](#四api-接口规范)
- [五、数据流转流程](#五数据流转流程)
- [六、安全策略](#六安全策略)
- [七、错误处理机制](#七错误处理机制)
- [八、性能指标与监控](#八性能指标与监控)
- [九、部署指南](#九部署指南)
- [十、维护与运维手册](#十维护与运维手册)
- [十一、实况落地行动清单](#十一实况落地行动清单v11--2026-09-03衔接全链路)
- [十二、2026-10-05 治理日实况快照](#十二2026-10-05-治理日实况快照)
- [附录 A: 环境变量清单](#附录-a-环境变量清单)
- [附录 B: 快速命令参考](#附录-b-快速命令参考)

---

## 一、系统架构总览

### 1.1 全链路拓扑

```
┌─────────────┐     ┌──────────────────────────────────────────────────────┐
│  公网用户   │────▶│  yyc3-33 ECS (39.97.53.176)                        │
│             │     │  Ubuntu 24.04 / 7.1GB RAM / 79GB Disk               │
│             │     │  Traefik v3.0.4 (TLS 1.3, Let's Encrypt)            │
│             │     │  路由: gateway-api-primary@file                     │
│             │     │  职责: 公网边缘反代（无网关副本/无 PG/LB）          │
└─────────────┘     └──────────────┬───────────────────────────────────────┘
                                   │ Tailscale VPN (100.x.x.x)
                                   ▼
┌─────────────┐     ┌──────────────────────────────────────────────────────┐
│  DGX GPU    │     │  yyc3-45 NAS (100.65.172.88)                        │
│  推理集群   │     │  TerraMaster F4-423 / 32GB DDR4                    │
│  N1+N2 TP2  │     │  Docker Compose (bridge: yyc3-network)              │
│             │     │  ┌─────────────────────────────────────┐            │
│  ┌────────┐ │     │  │  Gateway v2.0.0 (:8000)             │            │
│  │fluent- │─┼────▶│  │  FastAPI + Uvicorn (4 workers)      │            │
│  │bit(N1/ │ │ 日志│  │  ┌──────────┐ ┌──────────┐         │            │
│  │N2 容器 │ │ 外送│  │  │ PostgreSQL│ │  Redis 7  │         │            │
│  │日志tail│ │     │  │  │  15-alpine│ │  7-alpine │         │            │
│  └────────┘ │     │  │  │ PG 五表  │ │ canary:   │         │            │
│             │     │  │  │ Registry │ │ {alias}   │         │            │
│             │     │  │  └──────────┘ └──────────┘         │            │
│             │     │  └─────────────┬───────────────────────┘            │
│             │     │  ┌─────────────┴───────────────────────┐            │
└─────────────┘     │  │ 监控栈: Loki(:3100) Grafana(:3000)  │            │
                    │  │ Prometheus 规则: hotswap-gate        │            │
                    │  └─────────────────────────────────────┘            │
                    └────────────────┬────────────────────────────────────┘
                                   │ Model Registry 路由 (ready=5 推理池)
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
     │ 云端 API       │  │ Ollama 本地    │  │ DGX vLLM       │
     │ (公网直连)     │  │ (:11434)       │  │ (GPU 推理)     │
     │                │  │                │  │                │
     │ - 智谱 GLM-4   │  │ - CodeGeeX4-9B │  │ - DeepSeek-V4  │
     │ - DeepSeek     │  │ - Qwen3-14B   │  │   (TP2 旗舰)   │
     │ - OpenAI       │  │ - ChatGLM3-6B │  │ - embed/rerank │
     └────────────────┘  └────────────────┘  └────────────────┘

日志外送链（10-05 贯通）:
  N1/N2 容器 stdout → /var/lib/docker/containers/*/*.log
    → fluent-bit 3.1 (tail + Path_Key + cn.lua 短ID→容器名映射)
    → Tailscale → NAS Loki :3100 (30天保留 + compactor)
    → Grafana 看板 dgx-container-logs (双 panel)
```

### 1.2 核心组件清单

| 组件 | 技术 | 版本 | 端口 | 说明 |
| ------ | ------ | ------ | ------ | ------ |
| API Gateway | FastAPI + Uvicorn | 2.0.0 | 8000 | 统一模型网关（Tailscale-only 绑定） |
| 反向代理 | Traefik | v3.0.4 | 80/443 | TLS终止 + 路由（ECS 边缘） |
| 数据库 | PostgreSQL | 15-alpine | 5432(容器内) | 模型注册/用量统计/Registry 五表 |
| 缓存 | Redis | 7-alpine | 6379(容器内) | LLM缓存/限流/会话/事件流/Canary |
| Model Registry | 网关内置 `/registry/v1/*` | - | 8000 | 16 端点：模型/alias/drain/canary |
| 监控 | Prometheus + Grafana | - | 9090/3000 | 指标采集/可视化（NAS yyc3-45） |
| 日志 | Loki + fluent-bit | 3.1/3.1 | 3100 | DGX 日志外送，30 天保留 |
| 本地推理 | Ollama | latest | 11434 | CPU/GPU 本地模型 |
| 容器编排 | Docker Compose | 3.8 | - | 服务编排 |
| 内网穿透 | Tailscale | - | - | VPN 组网（SSH 9557/NAS） |

### 1.3 中间件执行链

请求按以下顺序经过中间件栈（外层先执行）:

```
Request
  │
  ▼
1. VersioningMiddleware    ← API 版本控制
  │
  ▼
2. RateLimitMiddleware     ← Redis 分布式滑动窗口限流
  │
  ▼
3. AuthMiddleware          ← JWT / API Key 双重认证
  │
  ▼
4. CORSMiddleware           ← 跨域策略
  │
  ▼
5. Router Handler           ← 业务处理
```

---

## 二、设备矩阵与基础设施

### 2.1 五端设备矩阵（10-05 精确化）

| 设备编号 | 主机名 | 角色 | 硬件规格 | 网络标识 | 存储职责 |
| --------- | -------- | ------ | --------- | --------- | --------- |
| **YYC3-22** | macOS 本机 | 开发机/部署桥 | Apple M4 Max / 128GB / 外挂存储 | Tailscale: 本机 IP | `/Volumes/Max/models` — 开发测试模型；GitOps 部署桥（~/yyc3-deploy/watch.sh） |
| **YYC3-33** | ECS | 公网边缘反代 | Ubuntu 24.04 / 7.1GB RAM / 79GB Disk | 公网: `39.97.53.176` / Tailscale: `100.126.132.112` | **仅 Traefik v3.0.4**（api.0379.world→NAS:8000），不含模型/PG/LB（10-05 实勘） |
| **YYC3-45** | NAS | 存储+网关+监控栈 | TerraMaster F4-423 / Celeron N5095 / 32GB DDR4 | Tailscale: `100.65.172.88`（SSH 9557） | 模型数据 + Gateway/PG/Redis + Loki/Grafana/Prometheus 监控栈 |
| **YYC3-DGX-101** | N1 yyc3-101 | 旗舰 head+RAG | NVIDIA DGX Spark / GB10 Blackwell / 121.7GB 统一内存 | Tailscale: `100.65.64.49`（ssh yyc3-n1）/ QSFP: `10.100.168.2` | dsv4-head:8001（TP2）+ embedding:8100/reranker:8101 + fluent-bit |
| **YYC3-DGX-102** | N2 yyc3-102 | 旗舰 worker+Agents | NVIDIA DGX Spark / GB10 Blackwell | Tailscale: `100.76.167.103`（ssh yyc3-n2）/ QSFP: `10.100.168.x` | dsv4-worker + 8×Agents:25600-07 + governance:25700 + chroma:8102 + fluent-bit |

> N1/N2 经 QSFP 210Gbps 直连组 Ray 集群跑 TP=2（旗舰启动序铁律：head 先起→~50s→worker 接入；详见《双机推理部署指南》§19 与 `dsv4-recover.sh` recover 模式）。

### 2.2 NAS 存储架构 (YYC3-45)

```
┌─────────────────────────────────────────────────────────┐
│  TerraMaster F4-423                                      │
│                                                          │
│  ┌─ HDD Pool ─────────────────────────────────────────┐ │
│  │ 4 x 8TB WDC HDD (RAID6 = 14.5TB 可用)              │ │
│  │  ├─ Volume1: /Volume1/yyc3_hd/data                  │ │
│  │  │   └─ 大模型仓库 (14 个模型, 含 DeepSeek/GLM/Kimi) │ │
│  │  └─ Volume2: /Volume2/docker                        │ │
│  │       ├─ /Volume2/docker/models (8 个 Docker 挂载模型)│ │
│  │       └─ /Volume2/yyc3-33/ (Gateway 部署目录)       │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ NVMe Pool ─────────────────────────────────────────┐ │
│  │ 2 x 2TB WD_BLACK SN850X NVMe (RAID1 = 1.8TB 可用)  │ │
│  │  └─ Volume3: Docker/应用热数据                      │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Docker 网桥: 172.17.0.1                                │
│  Tailscale: 100.65.172.88                               │
└─────────────────────────────────────────────────────────┘
```

---

## 三、模型资产清单

### 3.1 模型总览

**生产实况层（2026-10-05 治理日基准；09-03 v1.1 初版）**：

| 层 | 模型 | 端点 | 状态 |
|----|------|------|------|
| **旗舰推理** | deepseek-v4-flash（TP=2 双机） | `http://100.65.64.49:8001/v1`（QSFP 内网 10.100.168.2:8001） | ✅ 服务中（10-05 根因修复后稳定：max-model-len 32768+eager+worker unless-stopped；恢复剧本 `dsv4-recover.sh`） |
| 轻量层 | NAS Ollama 系 | `:11434` | ✅ |
| 云端兜底 | 智谱/DeepSeek/OpenAI | 公网 | ✅（注意 ZHIPU_KEY 曾过期，启动校验会拦截） |
| RAG 三件套 | Qwen3-Embedding/Reranker-8B、ChromaDB | `:8100/:8101`（N1）/`:8102`（N2） | ✅ 已上线（09-03 恢复容器化；铁律：embed/reranker 只能与 head 同机 N1） |
| 在途 | GLM-5.3-Flash（NVFP4 容量硬约束封存，待 AWQ-INT4 替代路线）/ Qwen3.8-Flash-Next（131 分片已完整落盘）/ MiniMax-H3-NF4（视频生成） | — | ⏸ 按业务节奏接入 |

**Registry 数据面层（10-05 治理日新增，权威层）**：

> 生产路由以 Model Registry 为准（`GET /registry/v1/models`）；下表为画像摘要，逐模型明细见《YYC3-Models-资产详情.md》v1.4.0 上线状态列。

| 分类 | 数量 | 说明 |
|------|------|------|
| 总记录 | 46 | 全量纳管（资产文档 ↔ Registry 双向对齐） |
| **enabled=true 真实推理池** | **5** | ready 态（TTL 内心跳）：flagship-dsv4 / embed-n1 / rerank-n1 等 |
| 云通道标注 | 11 | glm-4.x 系（capabilities 已补标注，云上游非 NAS 资产） |
| 归档/规划中 | 26 | 在途模型与封存项（GLM-5.3-Flash 等） |
| disabled 旧记录 | 4 | local 系永无心跳条目（10-05 核对后置 disabled，防「假在线」） |

**注册表模型（Gateway DB 视角，历史层）**：

| 后端类型 | 模型 ID | 显示名称 | 上下文长度 | 成本/1K tokens | 部署位置 |
| --------- | --------- | --------- | ----------- | --------------- | --------- |
| **zhipu** | `glm-4-flash` | 智谱 GLM-4 Flash | 128K | $0.001 | 云端 API |
| **zhipu** | `glm-4-plus` | 智谱 GLM-4 Plus | 128K | $0.05 | 云端 API |
| **deepseek** | `deepseek-chat` | DeepSeek Chat | 64K | $0.001 | 云端 API |
| **deepseek** | `deepseek-coder` | DeepSeek Coder | 16K | $0.001 | 云端 API |
| **openai** | `gpt-4` / `gpt-4o` / `gpt-3.5-turbo` | OpenAI 系列 | - | 按量 | 云端 API |
| **ollama** | `llama3.2` | Llama 3.2 (本地) | 128K | $0 | NAS Docker |
| **ollama** | `codegeex4` | CodeGeeX4 (本地) | 128K | $0 | NAS Docker |
| **ollama** | `qwen2.5` | 通义千问 2.5 (本地) | 128K | $0 | NAS Docker |
| **ollama** | DB 动态注册 | Ollama 自定义模型 | - | $0 | NAS Docker |

### 3.2 NAS 模型路径映射

**Volume1 — 大模型仓库** (`/Volume1/yyc3_hd/data`):

| 模型 | 路径 | 说明 |
| ------ | ------ | ------ |
| DeepSeek-Base | `/Volume1/yyc3_hd/data/DeepSeek-Base` | DeepSeek 基座模型 |
| DeepSeek-V4-Flash | `/Volume1/yyc3_hd/data/DeepSeek-V4-Flash` | 284B MoE, 推理优化 |
| DeepSeek-V4-Pro | `/Volume1/yyc3_hd/data/DeepSeek-V4-Pro` | DeepSeek 旗舰版 |
| GLM-5.1 | `/Volume1/yyc3_hd/data/GLM-5.1` | 智谱最新一代 |
| GLM-5.1-FP8 | `/Volume1/yyc3_hd/data/GLM-5.1-FP8` | FP8 量化版 |
| Kimi-K2.6 | `/Volume1/yyc3_hd/data/Kimi-K2.6` | Moonshot 1T MoE |
| Ring-2.6-1T | `/Volume1/yyc3_hd/data/Ring-2.6-1T` | 1T 参数超大模型 |
| Qwen3.5-122B-A10B | `/Volume1/yyc3_hd/data/Qwen/Qwen3.5-122B-A10B` | MoE 架构 |
| Qwen3.5-397B-A17B | `/Volume1/yyc3_hd/data/Qwen/Qwen3.5-397B-A17B` | 旗舰 MoE |
| Qwen3.6-27B / FP8 | `/Volume1/yyc3_hd/data/Qwen/Qwen3.6-27B*` | 含 FP8 量化 |
| Qwen3.6-35B-A3B / FP8 | `/Volume1/yyc3_hd/data/Qwen/Qwen3.6-35B-A3B*` | MoE 架构 |
| Qwen3-8B | `/Volume1/yyc3_hd/data/Qwen/Qwen3-8B` | 轻量级 |
| Qwen3-Coder-30B-A3B | `/Volume1/yyc3_hd/data/Qwen/Qwen3-Coder-30B-A3B` | 代码专用 MoE |
| Qwen3-Embedding/Reranker-8B | `/Volume1/yyc3_hd/data/Qwen/Qwen3-*-8B` | RAG 检索增强 |
| MiniCPM-V-4.6 | `/Volume1/yyc3_hd/data/MiniCPM-V-4.6` | 多模态视觉 |
| MegaStyle-1.4M | `/Volume1/yyc3_hd/data/MegaStyle-1.4M` | 风格迁移 |

**Volume2 — Docker 挂载模型** (`/Volume2/docker/models`):

| 模型 | 路径 | Ollama 挂载 |
| ------ | ------ | ------------- |
| ChatGLM3-6B | `/Volume2/docker/models/ChatGLM3-6B` | ✅ |
| CodeGeeX4-9B / Q8 | `/Volume2/docker/models/CodeGeeX4-9B*` | ✅ |
| Cogagent-9B | `/Volume2/docker/models/Cogagent-9B` | ✅ |
| Cogvideox-5B | `/Volume2/docker/models/Cogvideox-5B` | ✅ |
| Qwen3-14B | `/Volume2/docker/models/Qwen3-14B` | ✅ |
| Qwen3-14B-YYC3-merged | `/Volume2/docker/models/Qwen3-14B-YYC3-merged` | ✅ (微调版) |
| Qwen3-14B-YYC3-merged-gguf | `/Volume2/docker/models/Qwen3-14B-YYC3-merged-gguf` | ✅ (GGUF 量化) |

### 3.3 模型路由选择逻辑

**当前生产路由（三段式，09-03 A 线 P0/P1 落地 + 10-05 Registry 权威化）**：

```
请求 model 字段
  │
  ├─ ① Registry 优先：/registry/v1/models 中 enabled+ready 的条目
  │     └─ 命中 → upstream 池（registry-{model_id} 命名，priority 5）
  │           └─ Canary 检查：yyc3:canary:{alias} 存在？
  │                 ├─ 是 → 按 weight 概率分流至 canary 目标
  │                 │        └─ 失败 → canary_report_failure（2min≥5 次自动回退 weight=0）
  │                 └─ shadow=1 → 后台 fire-and-forget 采样（不影响主响应）
  ├─ ② env 上游池兜底：OPENAI_COMPATIBLE_UPSTREAMS（7 上游）
  │     └─ 熔断：3 败摘 30s 半开；降级链逐级回退
  └─ ③ 默认回退：本地 Ollama
```

> ⚠️ **v1.1 历史注记（已解决）**：09-03 前网关为模型名前缀硬编码匹配、EWMA 未接线、router/stats 假数据——A 线 P0/P1 已于 09-03 全部修复（上游池 env 化 + 三段式路由 + 熔断降级 + 观测真实化），旗舰 :8001 当日接入公网链路。
> 10-05 增量：Registry 层升级为权威数据面（46 条纳管），Canary/Shadow 分流嵌入 chat 主链路（`X-YYC3-Upstream`/`X-YYC3-Degraded` 响应头契约不变）。

**GPU 感知路由**: 通过 `/v1/model/type` 端点可查询模型后端类型 (`local_cpu` / `local_gpu` / `zhipu` / `deepseek` / `openai`)，供 Traefik/HAProxy 做智能分流。

---

## 四、API 接口规范

### 4.1 认证方式

所有接口（除免认证端点外）支持双重认证:

**方式一: API Key（推荐）**

```
X-API-Key: <your-api-key>
```

**方式二: JWT Bearer**

```
Authorization: Bearer <jwt_token>
```

**方式三: Registry 心跳 Token（仅注册 Agent 心跳类端点，10-05 生产启用）**

```
X-YYC3-Registry-Token: <REGISTRY_HEARTBEAT_TOKEN>
```

- 作用范围：`POST /registry/v1/heartbeat` 等心跳写入门点，与用户态 API Key/JWT 相互独立
- 三态语义：环境变量 `REGISTRY_HEARTBEAT_TOKEN` 未配置→跳过校验（灰度兼容）；配置但请求头错值→**401 拒绝**；正确→200
- 目的：防心跳伪造（第三方伪造 ready 状态污染路由池）

**免认证端点** (SKIP_AUTH_PATHS):

| 端点 | 说明 |
| ------ | ------ |
| `/v1/ping` | 轻量存活检查 |
| `/health` | 完整健康检查（含服务依赖） |
| `/healthz` | 轻量存活探针（供 Traefik/Prometheus 高频探活） |
| `/metrics` | Prometheus 指标 |
| `/docs` / `/openapi.json` / `/redoc` | Swagger 文档 |

### 4.2 Chat Completions

**核心端点**: `POST /v1/chat/completions`

**请求体**:

```json
{
  "model": "glm-4-flash",
  "messages": [
    {"role": "system", "content": "你是一个专业的助手"},
    {"role": "user", "content": "你好"}
  ],
  "max_tokens": 4096,
  "temperature": 0.7,
  "top_p": 0.9,
  "stream": false,
  "user_id": "optional-user-id"
}
```

**字段约束**:

| 字段 | 类型 | 必填 | 约束 |
| ------ | ------ | ------ | ------ |
| `model` | string | 是 | 1-100 字符 |
| `messages` | array | 是 | 1-50 条消息，每条 content 1-100K 字符 |
| `messages[].role` | enum | 是 | `system` / `user` / `assistant` |
| `messages[].content` | string | 是 | 非空，自动 strip |
| `max_tokens` | int | 否 | 1-128000，默认由模型配置决定 |
| `temperature` | float | 否 | 0.0-2.0，默认 0.7 |
| `top_p` | float | 否 | 0.0-1.0 |
| `stream` | bool | 否 | 默认 false |
| `user_id` | string | 否 | 最多 100 字符 |

**同步响应** (`stream: false`):

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "glm-4-flash",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}
}
```

**流式响应** (`stream: true`): SSE 格式

```
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"你"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"好"},"index":0}]}

data: [DONE]
```

### 4.3 模型管理

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| GET | `/v1/models` | 需要 | 获取可用模型列表（含 DB 动态注册 + 默认模型） |
| GET | `/v1/model/type?model=xxx` | 需要 | 查询模型后端类型（GPU 感知路由用） |
| GET | `/v1/router/stats` | 需要 | 路由器节点统计（EWMA 延迟、错误率、动态权重） |
| GET | `/v1/router/health` | 需要 | 触发路由器健康检查 |

### 4.4 缓存管理

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| GET | `/v1/cache/stats` | 需要 | 缓存统计（命中率、操作计数） |
| GET | `/v1/cache/info` | 需要 | 缓存详情（条目数、LRU 状态、TTL 配置） |
| POST | `/v1/cache/invalidate/{model_name}` | 需要 | 按模型名失效缓存 |
| DELETE | `/v1/cache/all` | 需要 | 清空所有 LLM 缓存 |

### 4.5 知识库 & RAG

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| POST/GET | `/v1/knowledge-bases` | 需要 | 知识库 CRUD |
| POST | `/v1/documents/upload` | 需要 | 上传文档（支持 PDF/DOCX/TXT 等） |
| POST | `/v1/rag/search` | 需要 | RAG 语义检索 |
| POST | `/v1/rag/ask` | 需要 | 基于知识库的问答 |

### 4.6 MCP 工具

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| GET | `/v1/mcp/tools` | 需要 | 获取 MCP 工具列表 |
| POST | `/v1/mcp/execute` | 需要 | 执行 MCP 工具 |

### 4.7 WebSocket

| 端点 | 认证 | 说明 |
|------|------|------|
| `/ws/chat` | 需要 | 流式聊天 WebSocket |
| `/ws/monitor` | 需要 | 实时监控数据推送 |

### 4.8 系统 & 监控

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| GET | `/v1/ping` | **免认证** | 轻量存活检查 `{"status":"ok"}` |
| GET | `/health` | **免认证** | 完整健康检查（含 ollama/redis/pg 状态 + 系统资源 + 指标） |
| GET | `/healthz` | **免认证** | 极轻量探活 `{"status":"alive", "uptime_seconds": N}` |
| GET | `/metrics` | **免认证** | Prometheus 格式指标 |
| GET | `/v1/versions` | 需要 | API 版本状态列表 |
| GET | `/docs` | **免认证** | Swagger UI |
| GET | `/redoc` | **免认证** | ReDoc 文档 |

### 4.9 Model Registry & Canary（10-05 治理日全量落地）

**Registry 端点**（`REGISTRY_ENABLED=true` 灰度开关，16 端点）：

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| GET | `/registry/v1/models` | 需要 | 全量模型注册表（含 state/心跳时间） |
| GET | `/registry/v1/models/{id}` | 需要 | 单模型详情 |
| POST | `/registry/v1/models` | 需要 | 注册/批量注册模型 |
| PATCH | `/registry/v1/models/{id}` | 需要 | 增量更新（capabilities/enabled 等） |
| DELETE | `/registry/v1/models/{id}` | 需要 | 摘除模型 |
| POST | `/registry/v1/heartbeat` | **Registry Token** | Agent 心跳上报（30s 周期） |
| GET | `/registry/v1/aliases` | 需要 | 别名列表（SOP-01 上线通道） |
| POST | `/registry/v1/aliases` | 需要 | 创建别名（alias→target 映射） |
| PATCH | `/registry/v1/aliases/{alias}` | 需要 | 别名切流（热切换核心动作） |
| DELETE | `/registry/v1/aliases/{alias}` | 需要 | 删除别名 |
| POST | `/registry/v1/drain` | 需要 | 排空节点（优雅摘除前置） |

> 完整 16 端点契约见《03-模型注册中心-API.md》；心跳 TTL 三级阶梯：90s degraded / 180s unreachable / 300s 摘除；事件流 `yyc3:registry:events`（Redis pub/sub）。

**Canary 端点（半自动热切换闭环）**：

| 方法 | 端点 | 认证 | 说明 |
| ------ | ------ | ------ | ------ |
| PUT | `/registry/v1/canary/{alias}` | 需要 | 设置灰度（baseline/canary/weight/shadow 四字段） |
| GET | `/registry/v1/canary/{alias}` | 需要 | 查询灰度状态（含失败计数窗口） |
| DELETE | `/registry/v1/canary/{alias}` | 需要 | 清除灰度（回归 baseline） |

**Canary 机制要点**：

- 存储：Redis hash `yyc3:canary:{alias}`，字段 `baseline` / `canary` / `weight`(0-100) / `shadow`(0/1)
- 分流：chat 请求按 weight 概率路由至 canary 目标（10s 内存缓存，不逐请求读 Redis）
- **惰性自动回退**：2min 滑动窗口内失败≥5 次 → weight 置 0 + 审计事件 `canary.auto_rollback` + 指标 `yyc3_registry_rollback_total` 递增
- Shadow 模式：shadow=1 时 fire-and-forget 采样请求至 canary 目标（`asyncio.create_task`，不阻塞主响应、失败不计入用户请求）
- 管理工具：`scripts/canary-manage.sh`（set/get/status/fail/clear/help 六子命令，Tailscale 直连 100.65.172.88:8000）
- 关键语义：`alias` = 客户端请求体里的 `model` 名（如 `deepseek-v4-flash`），非内部路由名

---

## 五、数据流转流程

### 5.1 Chat 请求完整生命周期

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Chat Request Lifecycle                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. 客户端发送 POST /v1/chat/completions                             │
│     │                                                                │
│     ▼                                                                │
│  2. Traefik (ECS) → TLS 终止 → Tailscale → NAS Gateway:8000          │
│     │                                                                │
│     ▼                                                                │
│  3. VersioningMiddleware → 版本校验                                   │
│     │                                                                │
│     ▼                                                                │
│  4. RateLimitMiddleware → Redis 滑动窗口限流 (100 req/min)            │
│     │  ├─ 超限 → 429 Too Many Requests                               │
│     │  └─ Redis 不可用 → 内存降级限流                                 │
│     ▼                                                                │
│  5. AuthMiddleware → JWT/API Key 认证                                │
│     │  ├─ 免认证路径 → 跳过                                          │
│     │  ├─ X-API-Key 头 → SHA256 哈希匹配                             │
│     │  ├─ Bearer Token → JWT 解密验证                                 │
│     │  └─ 失败 → 401/403                                             │
│     ▼                                                                │
│  6. CORSMiddleware → 跨域策略检查                                     │
│     │                                                                │
│     ▼                                                                │
│  7. Pydantic Schema Validation → 请求体校验                          │
│     │  ├─ 字段缺失/类型错误 → 422 Unprocessable Entity                │
│     │  └─ messages 为空 → 422                                        │
│     ▼                                                                │
│  8. ContentFilter → 敏感词/PII 检测                                   │
│     │  ├─ 命中敏感词 → 内容脱敏/拦截                                  │
│     │  └─ 通过 → 继续                                                │
│     ▼                                                                │
│  9. Backend Selection → 三段式模型路由（09-03 A 线 + 10-05 Registry）   │
│     │  ├─ ① Registry 条目（enabled+ready，46 条数据面）               │
│     │  │     └─ Canary 命中 → 按 weight 概率分流/shadow 后台采样      │
│     │  ├─ ② env 上游池（OPENAI_COMPATIBLE_UPSTREAMS，熔断3败摘30s）  │
│     │  └─ ③ 默认回退 Ollama                                          │
│     ▼                                                                │
│  10. Cache Lookup → Redis LLM 缓存                                   │
│      │  ├─ 命中 → 直接返回缓存结果                                   │
│      │  └─ 未命中 → 继续推理                                         │
│      ▼                                                                │
│  11. Concurrency Limiter → 并发控制                                   │
│      │                                                                │
│      ▼                                                                │
│  12. LLM Inference → 后端推理（P0 埋点 backend_requests_total）      │
│      │  ├─ 成功 → 写入缓存 + 记录用量（流式首块记 TTFT）              │
│      │  ├─ Canary 目标失败 → canary_report_failure（自动回退计数）    │
│      │  └─ 失败 → ErrorHandler 重试 (网络3次/API 2次/超时2次)          │
│      ▼                                                                │
│  13. Response → 格式化返回                                           │
│      ├─ stream=false → JSON 完整响应                                 │
│      └─ stream=true  → SSE 流式响应                                  │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 缓存策略

| 维度 | 策略 |
| ------ | ------ |
| 缓存键 | `llm_cache:` + SHA256(request_payload) |
| 存储 | Redis (String 类型，JSON 序列化) |
| 失效 | 按 model_name 主动失效 或 清空全部 |
| 命中率 | 通过 `/v1/cache/stats` 实时查看 |
| 降级 | Redis 不可用时跳过缓存，不阻塞请求 |

### 5.3 限流策略

| 维度 | 策略 |
| ------ | ------ |
| 算法 | Redis 有序集合滑动窗口 (Lua 原子操作) |
| 默认配额 | 100 请求 / 60 秒 |
| 突发 | burst=10 允许短时超量 |
| 降级 | Redis 不可用 → 内存单节点限流 |
| 响应 | 429 + `Retry-After` 头 |

---

## 六、安全策略

### 6.1 认证机制

| 机制 | 实现 | 说明 |
| ------ | ------ | ------ |
| API Key | `X-API-Key` 头，SHA256 哈希比对 | 生产推荐方式，从 `.env` 的 `API_KEYS` 逗号分隔加载 |
| JWT | `Authorization: Bearer` 头，HS256 签发 | 24 小时过期，支持 `user_id` 声明 |
| Registry 心跳 Token | `X-YYC3-Registry-Token` 头，明文比对 | 10-05 生产启用（`REGISTRY_HEARTBEAT_TOKEN` 48-hex）；仅心跳类端点，三态语义见 §4.1；防心跳伪造 |
| 免认证路径 | `SKIP_AUTH_PATHS` 集合 | 硬编码白名单：`/v1/ping` `/health` `/healthz` `/metrics` `/docs` 等 |

### 6.2 内容安全

- **敏感词过滤**: 中英文敏感词库 + 正则模式（手机号/身份证/银行卡/API Key 格式检测）
- **PII 检测**: BASE64/SHA 编码密钥格式识别
- **输入校验**: Pydantic 严格校验（字段长度、范围、枚举值）

### 6.3 网络安全

| 层级 | 策略 |
| ------ | ------ |
| 传输层 | TLS 1.3 (Let's Encrypt) + Tailscale VPN 加密内网通信 |
| 应用层 | CORS 白名单 (`allowed_origins`) |
| 数据层 | PostgreSQL 密码认证 + Redis `requirepass` |
| 容器层 | 非 root 用户运行 (appuser:1000) + 多阶段构建最小镜像 |
| 依赖安全 | `uv pip compile --generate-hashes` 锁定 52 个安全版本 |

### 6.4 关键配置保护

启动时强制校验 4 项关键配置（`auth_enabled=true` 时缺失则拒绝启动）:

| 配置项 | 校验规则 |
| -------- | --------- |
| `JWT_SECRET_KEY` | 非空且不等于 `change_me_in_production` |
| `API_KEYS` | 非空 |
| `POSTGRES_PASSWORD` | 非空且不等于 `change_me_in_production` |
| `REDIS_PASSWORD` | 非空且不等于 `change_me_in_production` |

---

## 七、错误处理机制

### 7.1 错误分类体系

| 错误类型 | 异常类 | HTTP 状态码 | 重试策略 |
| --------- | -------- | ------------ | --------- |
| 网络错误 | `NetworkError` | 502/503 | 最多 3 次，间隔 1s |
| API 错误 | `APIError` | 4xx/5xx | 最多 2 次，间隔 2s |
| 超时错误 | `TimeoutError` | 504 | 最多 2 次，间隔 1s |
| 校验错误 | `ValidationError` | 422 | 不重试 |

### 7.2 标准错误响应格式

```json
{
  "error": "YYC3_NETWORK_ERROR",
  "message": "Connection refused to upstream model service",
  "status_code": 502,
  "details": {
    "model": "glm-4-flash",
    "backend": "zhipu",
    "retry_count": 3
  }
}
```

### 7.3 HTTP 状态码语义

| 状态码 | 场景 |
| -------- | ------ |
| 200 | 成功（同步响应/查询类） |
| 422 | 请求体校验失败 (Pydantic Validation) |
| 401 | 未认证 (缺少/无效 API Key 或 JWT)；**Registry 心跳端点**：`REGISTRY_HEARTBEAT_TOKEN` 已配置但 `X-YYC3-Registry-Token` 缺失/错值（10-05 组，见 §4.1） |
| 403 | 认证通过但无权限 |
| 404 | 模型不存在 / 资源未找到（含 `REGISTRY_ENABLED=false` 时 `/registry/v1/**` 全旁路） |
| 429 | 限流 (Too Many Requests) |
| 500 | 内部错误 |
| 502 | 上游模型服务不可达 |
| 504 | 上游模型服务超时 |

---

## 八、性能指标与监控

### 8.1 Prometheus 指标

通过 `/metrics` 端点暴露 (prometheus_fastapi_instrumentator):

- `http_requests_total` — 总请求数 (按 method/path/status)
- `http_request_duration_seconds` — 请求延迟直方图
- `http_requests_in_progress` — 当前并发请求数

**后端/热切换 P0 三件套（10-05 上线，热切换数据底座）**:

| 指标 | 类型 | Labels | 说明 |
| ------ | ------ | ------ | ------ |
| `yyc3_backend_requests_total` | Counter | upstream, code | 后端请求计数（成功/失败/降级三态埋点于 chat/proxy） |
| `yyc3_backend_ttft_seconds` | Histogram | upstream | 流式首 token 延迟（TTFT，SSE 首块计时） |
| `yyc3_registry_rollback_total` | Counter | alias | Canary 自动回退计数（惰性回退触发点递增） |

**Canary/Shadow 增强指标**:

| 指标 | 类型 | Labels | 说明 |
| ------ | ------ | ------ | ------ |
| `yyc3_canary_weight` | Gauge | alias, canary | 当前灰度权重（0-100，PUT/回退时 set） |
| `yyc3_canary_failures_total` | Counter | alias, canary | 灰度目标失败计数 |
| `yyc3_shadow_requests_total` | Counter | alias, canary | Shadow 采样发炮计数 |

> 告警规则：`deploy/nas/prometheus-rules/hotswap-gate.rules.yml`（回退激增/灰度失败率/TTFT 劣化三规则，已装载 NAS Prometheus）；Grafana 看板经 `deploy/nas/import-grafana-dashboards.sh` 灌入。

### 8.2 业务指标 (通过 `/health` 端点)

| 指标 | 来源 | 说明 |
| ------ | ------ | ------ |
| `active_requests` | metrics_manager | 当前活跃请求数 |
| `total_requests` | metrics_manager | 累计总请求数 |
| `cache_hit_rate` | metrics_manager | LLM 缓存命中率 |
| CPU / Memory / Disk | psutil | 网关宿主机系统资源 |

### 8.3 路由器指标 (通过 `/v1/router/stats`)

| 指标 | 说明 |
| ------ | ------ |
| `ewma_latency` | EWMA 平滑延迟 (ms) |
| `ewma_error_rate` | EWMA 平滑错误率 |
| `dynamic_weight` | 动态权重 (自适应路由) |
| `success_rate` | 成功率 |

### 8.4 性能基线 (实测)

| 指标 | 值 | 说明 |
| ------ | ----- | ------ |
| NAS Gateway 启动 | < 30s | Docker Compose up -d (含 PG/Redis 健康检查) |
| /healthz 响应 | < 5ms | 纯内存操作 |
| /health 响应 | < 500ms | 含外部服务并发探查 |
| 公网端到端延迟 | ~1.3s | 本机 → api.0379.world → NAS Gateway → 返回 |
| Gateway 资源占用 | CPU 2.4% / RAM 10.8% | NAS 空载基线 |

### 8.5 日志观测链（10-05 贯通）

```
DGX N1/N2 容器 stdout
  → /var/lib/docker/containers/*/*.log（纯 docker 节点路径，非 k8s /var/log/containers）
  → fluent-bit 3.1（tail 插件 + Path_Key 保留日志路径）
      └─ cn.lua：从路径截取 12 位容器短 ID → 查 id→name 映射表（300s 自刷新）
         映射表由 container-map.timer 每 5min docker cp 注入（mv 会换 inode 破坏 bind mount）
  → Tailscale → NAS Loki :3100（100.65.172.88，Tailscale-only）
      └─ 30 天保留（744h）+ compactor；user:"0"（NAS ACL 权衡）
  → Grafana 看板 dgx-container-logs（双 panel：日志流 + 容器筛选）
```

- 镜像源铁律：fluent-bit 拉取用 `docker.1ms.run`（daocloud 已停滞）
- 验证命令：`curl -s "http://100.65.172.88:3100/loki/api/v1/query_range?query={container_name=\"dsv4-head\"}" | head -c 500`
- 部署/运维脚本族：`deploy/dgx/setup-container-map.sh`、`deploy/dgx/deploy-container-map-remote.sh`、`deploy/dgx/fluent-bit.conf`、`deploy/dgx/cn.lua`

---

## 九、部署指南

### 9.1 首次部署

```bash
# 1. 在 NAS (YYC3-45) 创建部署目录
ssh yyc3-45
mkdir -p /Volume2/yyc3-33

# 2. 上传部署文件
#    - docker-compose.nas.yml → /Volume2/yyc3-33/docker-compose.yml
#    - .env (从 .env.example 复制并填写)
#    - scripts/deploy-nas-gateway.sh

# 3. 配置环境变量
scp .env yyc3-45:/Volume2/yyc3-33/.env

# 4. 执行部署脚本
bash scripts/deploy-nas-gateway.sh

# 5. 验证
curl http://100.65.172.88:8000/healthz
```

### 9.2 更新部署

> 🚨 **红线（10-05 事故教训）**：网关重建一律走 `rebuild-gateway.sh`。若必须手工 compose，**必须**带 `-p yyc3-33 --project-directory /Volume2/yyc3-33 -f <compose 绝对路径>`——漏 `--project-directory` 会导致 NAS PG/Redis 空密码重建环、网关中断（10-05 曾中断约 8 分钟）。日常更新走 §9.4-bis GitOps 桥。

```bash
# 0. 标准通道（推荐）
ssh yyc3-45 "bash /Volume2/yyc3-33/rebuild-gateway.sh"

# 1. 更新代码（应急手工）
ssh yyc3-45 "cd /Volume2/yyc3-33 && git pull"

# 2. 更新 .env (如有配置变更)
#    注意: .env 变更必须 rebuild 才能生效

# 3. 重建并启动
ssh yyc3-45 "cd /Volume2/yyc3-33 && docker compose up -d --build gateway"

# 4. 验证健康
curl http://100.65.172.88:8000/health
```

### 9.3 环境变量配置

**必填项**:

| 变量 | 说明 | 示例 |
| ------ | ------ | ------ |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | 强密码 |
| `REDIS_PASSWORD` | Redis 密码 | 强密码 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 随机 32+ 字符 |
| `API_KEYS` | API Key 列表 (逗号分隔) | `sk-key-1,sk-key-2` |

**可选项**:

| 变量 | 说明 | 默认值 |
| ------ | ------ | -------- |
| `ZHIPU_API_KEY` | 智谱 API Key | 空 (不配置则 GLM 不可用) |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 空 |
| `OPENAI_API_KEY` | OpenAI API Key | 空 |
| `DB_HOST` | PostgreSQL 主机 | `postgres` (容器网络) |
| `DB_PORT` | PostgreSQL 端口 | `5432` |
| `DB_NAME` | 数据库名 | `yyc3_gpt` |
| `REDIS_HOST` | Redis 主机 | `redis` (容器网络) |
| `API_HOST` | 监听地址 | `0.0.0.0` |
| `API_PORT` | 监听端口 | `8000` |
| `ALLOWED_ORIGINS` | CORS 白名单 | `https://api.0379.world` |
| `AUTH_ENABLED` | 是否启用认证 | `true` |
| `JWT_EXPIRATION_HOURS` | JWT 过期时间 | `24` |
| `REGISTRY_ENABLED` | 模型注册中心开关（10-05 组） | `true`（NAS 生产） |
| `REGISTRY_HEARTBEAT_TOKEN` | 心跳独立认证 Token（10-05 组） | 已配置（48-hex）；未配置跳过校验 |

> 完整变量表（含日志外送组/Redis key 约定）见附录 A 与《变量清单》v1.1.0；`.env` 变更必须 rebuild（rebuild-gateway.sh）才生效。

### 9.4-bis 部署实况（v1.1）：GitOps 自动部署已取代手工流程

> 2026-09-02 起生效：`git push main` → CI 五段验证 → **Mac 部署桥**（~/yyc3-deploy/watch.sh，每 2 分钟对比 NAS HEAD）→ `git push ssh://YYC3@100.65.172.88:9557/Volume2/yyc3-33` → NAS `rebuild-gateway.sh` 重建+健康检查 → 公网终验。本节 9.1-9.3 的手工命令保留为**应急通道**。
> 运维红线：① NAS sshd 有防暴力惩罚机制（高频连接会被间歇拒认，自动化连接须 ≥60s 间隔）；② 旗舰 TP=2 启停按《双机推理部署指南》§19（head 先起 worker 后起；`/tmp` 会被清理，启动脚本已锚定 `/home/yyc3/dsv4_*.sh`）；③ NAS→GitHub 直连不稳定，部署一律走 Mac 桥。

### 9.4 Docker 镜像构建

```
多阶段构建:
  base (python:3.11-slim) → builder (安装依赖) → production (复制代码 + 非 root 用户)

关键点:
  - COPY core/api/ → /app/app/ (应用代码映射)
  - 非 root 用户 appuser:1000 运行
  - 健康检查: python -c urllib.request.urlopen('http://localhost:8000/docs')
```

---

## 十、维护与运维手册

### 10.1 日常巡检清单

```bash
# 1. 检查 Gateway 容器状态
ssh yyc3-45 "docker ps --filter name=0379-world"

# 2. 检查 Gateway 健康 (轻量)
curl -s http://100.65.172.88:8000/healthz | python3 -m json.tool

# 3. 检查完整健康 (含依赖)
curl -s http://100.65.172.88:8000/health | python3 -m json.tool

# 4. 检查公网可达性
curl -s -o /dev/null -w "%{http_code}" https://api.0379.world/healthz

# 5. 检查 ECS Traefik 状态
ssh yyc3-33 "docker ps --filter name=traefik"

# 6. 查看 Gateway 日志
ssh yyc3-45 "docker logs --tail 100 0379-world-gateway-1"
```

**一键巡检（10-05 推荐，替代上面 1-6 手工序）**：

```bash
# scripts/health-full.sh — 17 项全链路自检（网关/公网/Registry/Canary/指标/Loki 日志链）
bash scripts/health-full.sh          # 期望 17/17 PASS

# 旗舰健康（五模式剧本）
bash deploy/dgx/dsv4-recover.sh check   # 只读检查，不动作
```

### 10.2 故障排查

| 症状 | 可能原因 | 排查步骤 |
| ------ | --------- | --------- |
| 公网 502 | ECS→NAS 链路中断 | `ssh yyc3-33 "curl http://100.65.172.88:8000/healthz"` → 检查 Tailscale 连接 |
| 401 认证失败 | API Key 错误 / .env 未同步 | `ssh yyc3-45 "docker exec 0379-world-gateway-1 printenv API_KEYS"` → 对比 .env |
| 模型不可用 | Ollama 未启动 / 云端 Key 过期 | `/health` 检查 ollama/zhipu 状态 → 检查 API Key 有效性 |
| 响应超时 | 上游模型慢 / 网络延迟 | `/v1/router/stats` 查看 EWMA 延迟 → 考虑切换后端 |
| Redis 限流失效 | Redis 服务异常 | `docker logs 0379-world-redis-1` → 确认降级到内存限流 |
| 容器启动失败 | 关键配置缺失 | `docker logs 0379-world-gateway-1` → 检查 validate_critical_config 报错 |
| 旗舰心跳 degraded/offline | Agent 停/实例崩/显存挤穿 | `bash deploy/dgx/dsv4-recover.sh check` 先只读诊断 → `rootcause` 看三层根因 → `recover` 编排时序恢复（head 起→50s→worker 接入）；Registry state=ready 为权威判据，RestartCount 禁单独判定 |
| Registry 心跳 401 | Token 未同步/错值 | 核对节点 env `REGISTRY_HEARTBEAT_TOKEN` 与 NAS .env 一致 → Agent 用 `--registry-token-env` 指定读取名 → 重启 Agent |
| Canary 流量异常 | weight 配置漂移/目标故障 | `bash scripts/canary-manage.sh get <alias>` 查状态 → 看 `yyc3_registry_rollback_total` 是否已自动回退 → 必要时 `clear` 回归 baseline |

### 10.3 备份策略

| 数据 | 位置 | 备份方式 |
| ------ | ------ | --------- |
| PostgreSQL | `/Volume2/yyc3-33/postgres/pgdata` | `core/scripts/yyc3_db_backup.sh`（含 Registry 五表：models/aliases/heartbeats/events/audit，005/006 迁移） |
| Redis | `/Volume2/yyc3-33/redis/` | RDB + AOF (Redis 7 默认)；Canary 状态（`yyc3:canary:*`）为易失配置，变更记录在案即可 |
| 模型文件 | `/Volume1/yyc3_hd/data` + `/Volume2/docker/models` | RAID6/RAID1 硬件冗余 |
| 部署配置 | `/Volume2/yyc3-33/docker-compose.yml` + `.env` | Git 版本控制（`.env` 含 Token 者不入库，走 NAS 本地+密管） |
| Loki 日志 | NAS Loki 数据卷 | 30 天在线保留（compactor）；跨机备份暂未做（可接受窗口） |

### 10.4 扩缩容指南

**水平扩展**:

- Gateway 无状态，可通过 `docker compose up --scale gateway=N` 多实例 + Traefik 负载均衡
- Redis 共享限流状态，多实例限流一致

**垂直扩展**:

- 增加 NAS 内存 (当前 32GB) → 提升 Ollama 本地推理并发
- DGX GPU 接入更多模型 → 减轻云端 API 依赖

---

## 附录 A: 环境变量完整清单

> 权威源：[`.env.example`](../core/config/.env.example)（网关容器实际装载版）；逐变量详解与幽灵勘误见 **[《变量清单》](../核心参考/变量清单.md) v1.1.0**。

### A.1 核心必填（容器启动即校验）

| 变量 | 说明 | 示例/默认 |
| ------ | ------ | ------ |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | 强密码（rebuild-gateway.sh 校验） |
| `REDIS_PASSWORD` | Redis 密码 | 强密码 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 随机 32+ 字符 |
| `API_KEYS` | API Key 列表 | `sk-key-1,sk-key-2`（逗号分隔） |

### A.2 数据库/缓存连接

| 变量 | 默认值 | 说明 |
| ------ | ------ | ------ |
| `DB_HOST` / `DB_PORT` / `DB_NAME` | `postgres` / `5432` / `yyc3_gpt` | 容器网络内寻址 |
| `REDIS_HOST` / `REDIS_PORT` | `redis` / `6379` | 容器网络内寻址 |

### A.3 服务监听/安全

| 变量 | 默认值 | 说明 |
| ------ | ------ | ------ |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | NAS 侧绑定（端口对 Tailscale 网络暴露） |
| `ALLOWED_ORIGINS` | `https://api.0379.world` | CORS 白名单 |
| `AUTH_ENABLED` | `true` | 认证总开关 |
| `JWT_EXPIRATION_HOURS` | `24` | JWT 有效期 |

### A.4 云端上游（未配置则对应通道不可用）

| 变量 | 说明 |
| ------ | ------ |
| `ZHIPU_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | 云推理通道密钥 |
| `OPENAI_COMPATIBLE_UPSTREAMS` | 上游池 env 化配置（A 线 P0，三段式路由数据源） |

### A.5 Registry/灰度（10-05 新增组）

| 变量 | 默认值 | 说明 |
| ------ | ------ | ------ |
| `REGISTRY_ENABLED` | `true` | Registry 灰度开关（false 时端点 404） |
| `REGISTRY_HEARTBEAT_TOKEN` | （10-05 已配置 48-hex） | 心跳独立认证；未配置跳过/错值 401/正确 200；docker-compose.nas.yml 透传 |

### A.6 监控/日志外送（10-05 新增组）

| 变量 | 示例值 | 说明 |
| ------ | ------ | ------ |
| `NODE_ID` | `yyc3-101` | fluent-bit 侧节点标识（日志 label） |
| `NODE_LOKI_HOST` | `100.65.172.88` | Loki 地址（Tailscale IP） |
| `NODE_LOKI_PORT` | `3100` | Loki 端口 |

> Redis key 约定（非 env，随服务内置）：`yyc3:registry:events`（事件流）、`yyc3:canary:{alias}`（灰度 hash：baseline/canary/weight/shadow）。

## 附录 B: 快速命令参考

```bash
# ── 健康检查 ──
curl http://100.65.172.88:8000/healthz          # 轻量探活
curl http://100.65.172.88:8000/health             # 完整健康
curl https://api.0379.world/healthz               # 公网探活

# ── 模型操作 ──
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/models                    # 模型列表
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/model/type?model=glm-4-flash  # 模型类型

# ── Chat 请求 ──
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"你好"}]}'

# ── 流式 Chat ──
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"model":"glm-4-flash","messages":[{"role":"user","content":"你好"}],"stream":true}'

# ── 缓存管理 ──
curl -H "X-API-Key: $KEY" https://api.0379.world/v1/cache/stats   # 缓存统计
curl -X DELETE -H "X-API-Key: $KEY" https://api.0379.world/v1/cache/all  # 清空缓存

# ── Registry（10-05 组）──
curl -H "X-API-Key: $KEY" http://100.65.172.88:8000/registry/v1/models | head -c 800  # 数据面 46 条
curl -H "X-API-Key: $KEY" http://100.65.172.88:8000/registry/v1/aliases               # 别名（SOP-01 通道）

# ── Canary 管理（六子命令）──
bash scripts/canary-manage.sh set <alias> <canary目标> --weight 10   # 灰度 10%
bash scripts/canary-manage.sh get <alias>                            # 查状态/失败窗口
bash scripts/canary-manage.sh clear <alias>                          # 回归 baseline

# ── 全链路自检 ──
bash scripts/health-full.sh                     # 17/17 期望全绿
bash deploy/dgx/dsv4-recover.sh check           # 旗舰只读诊断
bash deploy/dgx/dsv4-recover.sh watch           # 实时盯防（Ctrl-C 退出）

# ── 日志链（Loki）──
curl -s "http://100.65.172.88:3100/loki/api/v1/query_range?query={container_name=\"dsv4-head\"}" | head -c 500

# ── 部署操作 ──
ssh yyc3-45 "bash /Volume2/yyc3-33/rebuild-gateway.sh"   # 标准重建通道（唯一推荐）
# 应急手工（必须 --project-directory，漏则 PG/Redis 空密码重建环）：
ssh yyc3-45 "cd /Volume2/yyc3-33 && docker compose -p yyc3-33 --project-directory /Volume2/yyc3-33 -f /Volume2/yyc3-33/docker-compose.yml up -d --build gateway"
ssh yyc3-45 "docker logs --tail 50 -f 0379-world-gateway-1"                     # 实时日志
```

---

## 十-ter、全端实况快照（2026-09-14 SSH 实勘基准）

> 本节为最新实况锚点（三文档分头引用此节，避免重复维护）；执行细节见《DGX-Spark双机推理部署指南》与 `deploy/dgx/tp2-ray-实测验证模式.md` 攻坚档案。

### 设备-容器-端口实况（实测 200/healthy）

| 节点 | 角色 | 容器/服务 | 实况 |
|------|------|-----------|------|
| **N1 yyc3-101** | 旗舰推理+RAG | `dsv4-head`(:8001 TP=2 head) / `yyc3-embedding`(:8100) / `yyc3-reranker`(:8101) | 三共存稳定；**vllm nightly 镜像（digest 31a59e77）**，v0.26.0 在 sm_121 FP8 kernel 乱码已证 |
| **N2 yyc3-102** | 旗舰 worker+Agents+Chroma | `dsv4-worker` / 8×`agent-*`(:25600-07) + `yyc3-governance-hub`(:25700) / `yyc3-chroma`(:8102) | Agents 全接旗舰（`VLLM_ENDPOINT=http://10.100.168.2:8001/v1` QSFP 直连） |
| **NAS yyc3-45** | 网关计算主实例 | `0379-world-gateway-1`(:8000) + postgres/redis + gitbucket/wireguard | 池 3 上游（flagship-dsv4/embed-n1/rerank-n1，均 Tailscale） |
| **ECS yyc3-33** | 边缘反代 | `docker-traefik-1`(80/443, Let's Encrypt) | `dynamic.yml: gateway-api→http://100.65.172.88:8000`——**无网关副本** |
| 公网 | — | `https://api.0379.world` | health=200；chat/embeddings/rerank 三能力全绿（X-YYC3-Upstream 头契约） |

### 09-03 → 09-14 关键事件（影响架构记录）

1. **A线网关 P0/P1/P2 全落地**：上游池 env 化+三段式路由+熔断降级+四能力端点（embeddings 透传/rerank Cohere⇆生成式打分/asr/ocr 待上游）；24 pytest + CI 五段绿 + NAS SMOKE + 公网冒烟四层保障
2. **旗舰乱码根因**：vLLM v0.26.0 sm_121 FP8 kernel 缺陷 → nightly 修复（铁律：v0.26.0 勿用）
3. **"容器被外部停止"结案**：vLLM fatal 自退（GPU 竞态→NVRM OOM→EngineCore fatal→有序 shutdown exit 0）；非 Agent/人为（auditd+canary 三兄弟 38h 存活佐证；罗网留置）
4. **GLM-5.3-Flash-NVFP4 终判**：92-95G/rank + vLLM/ray 在 121G UMA 双机**容量硬约束**（五轮双格式证毕）；替代路线 AWQ-INT4(~50G/rank)/vLLM 演进/硬件代际；资产双端留档
5. **SSH 全网格 8/8**：NAS 家目录 777+StrictModes 根因修复（chmod 755 + watch.sh/rebuild 双护栏）；N2 `id_ed25519` 带口令→自动化用 `id_ed25519_shared`
6. **运维铁律新增**：RAG 只能与 head 同机（N2 与 ray-worker 必崩）；先旗舰后 RAG 启动序；nightly ENTRYPOINT=[vllm serve] 勿写前缀

### 十一清单状态同步（09-14）

#1/#2/#3/#4/#8 已完成（见 §十一）；#5 Agents 容器化 **已完成**（上表）；#6 实况修正（ECS=边缘反代，无双活需求）；#7 新模型注册：GLM 封存待替代路线，Qwen3.8-Flash-Next/MiniMax-H3 下载中。

## 十一、实况落地行动清单（v1.1 · 2026-09-03，衔接全链路）

> 排序原则：每一项都让"公网用户 → DGX 旗舰"近一步；前两项是阻断项。

| # | 行动 | 现状→目标 | 依赖 | 验收 |
|---|------|-----------|------|------|
| **1** | **A 线 P0：网关上游配置化 + 测试地基** | ✅ **完成（09-03 f6dd282）**：OPENAI_COMPATIBLE_UPSTREAMS env 池 + 云基址外部化 + 死代码清零 + pytest 零网络（15 用例） | 无 | mock 上游进 `/v1/models` ✓；CI test 绿 ✓ |
| **2** | **A 线 P1：智能路由接线 + 熔断降级** | ✅ **完成（09-03）并已对公网**：分层优先级路由 + 熔断(3败摘30s半开) + 降级链 + X-YYC3-Upstream/Degraded 头；**api.0379.world → Traefik(Tailscale) → NAS 网关 → N1:8001 旗舰全链路验收通过（对话/SSE/响应头）** | #1 ✓ | 公网 chat 落 deepseek-v4-flash ✓（`x-yyc3-upstream: flagship-dsv4`）|
| 3 | RAG 三件套容器化恢复 | ✅ **完成（09-03）**：0.6B 版三容器上线（**N1 部署铁律**：N2 与 ray-worker 同节点必崩）；公网 `/v1/embeddings`(1024维) `/v1/rerank`(judge 打分排序) 全绿；8B 升级位待旗舰 KV 腾挪 | 完成 | `/v1/embeddings` 公网全链路通 ✓ |
| 4 | 4 缺失端点补齐（A 线 P2） | ✅ **完成（09-03）**：`/v1/embeddings`(透传) `/v1/rerank`(Cohere⇆Jina 转换) `/v1/audio/transcriptions` `/v1/ocr`(multipart 透传)，capability 路由复用上游池+熔断降级+X头；9 测试例 | #1 ✓ | 7 端点契约齐 ✓（asr/ocr 真机待上游服务） |
| 5 | Agents 容器化上线 | 代码模型无关（VLLM_ENDPOINT）→ compose 起 8 Agent+治理，env 指向 :8001 | #2 | :25600-07/:25700 健康 |
| 6 | ~~ECS 网关副本双活~~ → **实况修正**：ECS=Traefik 边缘反代（api.0379.world→NAS:8000），NAS 网关即唯一计算实例且已服务公网；可选增强=ECS 本地副本（需连 NAS PG/Redis，性价比待评估） | 单 NAS 网关已是公网主实例 ✓ | Traefik 双上游（可选） |
| 7 | 新模型注册 | GLM-5.3-Flash（量化后 TP=2 升级位）/ Qwen3.8-Flash-Next（轻旗舰降级位）/ MiniMax-H3-NF4（**新增视频生成端点** `/v1/videos` 候选） | 下载完成+量化 | 各自冒烟 |
| 8 | 观测真实化 | ✅ **API 侧完成（09-03）**：models/stats 真实 EWMA、models/errors 真数据、router/stats 并池快照、ws/monitor 去假数据；Grafana 面板字段对齐待做 | #2 ✓ | 面板出真数（API ✓/Grafana 待） |

**旗舰运维速查（衔接 §9.4-bis）**：
```bash
# 启动（顺序敏感）
ssh yyc3@100.65.64.49 'docker start dsv4-head'   # 等 ~80s
ssh yyc3@100.76.167.103 'docker start dsv4-worker'
# 验收
curl http://100.65.64.49:8001/v1/models          # → deepseek-v4-flash
# 停机（干净关停）
ssh yyc3@100.65.64.49 'docker stop dsv4-head' && ssh yyc3@100.76.167.103 'docker stop dsv4-worker'
# 注意：容器 /tmp 不持久——启动脚本已锚定 ~/dsv4_head.sh(脚本在 /home/yyc3)，误删脚本会导致 docker start 挂载失败（2026-09-03 实测踩坑）
# ⚠️ 镜像铁律（09-03 事故）：vllm/vllm-openai:v0.26.0(latest) 在 GB10/sm_121 上 FP8 kernel 输出乱码
#    —— 必须 docker.m.daocloud.io/vllm/vllm-openai:nightly（digest 31a59e77…），排除链见 deploy/dgx/tp2-ray-实测验证模式.md
```

> **文档维护**: YanYuCloudCube Team <admin@0379.email>
> **最后验证**: 2026-10-05（v1.6 治理日：**Registry 46 条全量纳管 + Token 生产启用 + Canary/Shadow 闭环 + P0 三件套 + 日志外送链 + 17 项自检全绿**；前基线 09-14 三能力全绿）
> **下次审核建议**: 2026-10-20 或首个 Canary 生产切流时

---

## 十二、2026-10-05 治理日实况快照

> 本节为 v1.6 增量锚点（09-14 快照见 §十-ter）；执行档案见《docs/模型接入与注册/》文档族 01-07 + README v1.4 状态表。

### 当日落地清单（全量）

| 域 | 事项 | 状态 | 关键产物/锚点 |
|------|------|------|------|
| 注册数据面 | 28 条批量注册 + 3 条 PATCH + glm-4.x 11 条溯源 + local 4 条置 disabled | ✅ | Registry 46 条全量纳管，enabled=true 仅 5 真实推理池 |
| 幽灵治理 | ECS yyc3-33 实勘定位 + pg/lb 7 个幽灵脚本处置 | ✅ | ECS 仅剩 docker-traefik-1（边缘反代），无 PG/LB |
| 旗舰恢复 | dsv4 心跳停滞 09-29 根因（rank0 显存挤穿/worker SIGTERM 死锁/nightly 竞态三层） | ✅ | max-model-len 65536→32768 + eager + unless-stopped + 编排时序 |
| 运维剧本 | dsv4-recover.sh 五模式（check/recover/rootcause/logs/watch/FORCE） | ✅ | `deploy/dgx/dsv4-recover.sh` + 使用手册（07） |
| 心跳安全 | X-YYC3-Registry-Token 生产启用（网关重启窗口完成） | ✅ | `REGISTRY_HEARTBEAT_TOKEN` 48-hex；三态 401/401/200 实测 |
| 热切换底座 | Canary 状态机 + Shadow 采样 + 惰性自动回退 | ✅ | `model_registry_svc.py` canary_* 六函数 + chat 分流 + 三端点 |
| 观测 P0 | backend_requests/TTFT/rollback 三件套 + 三告警规则 + Grafana 看板灌入 | ✅ | `hotswap-gate.rules.yml` + `import-grafana-dashboards.sh` |
| 日志外送 | fluent-bit→Loki 全链 + 容器名映射 + 30 天保留 + 日志看板 | ✅ | Loki 3100 Tailscale-only；cn.lua v2；container-map.timer |
| 脚本闭环 | health-full.sh 17/17 + canary-manage.sh 六子命令 | ✅ | Tailscale 直连 100.65.172.88:8000 实测全绿 |

### Registry 数据面画像（10-05 治理后）

- 总量 46 条：真实推理池 5（enabled+ready）+ 云通道标注 11（glm-4.x 溯源补能力）+ 归档/规划 26 + disabled 旧记录 4
- ready=5 推理池：flagship-dsv4（TP2 旗舰）/ embed-n1 / rerank-n1 / 等（详见《YYC3-Models-资产详情.md》v1.4.0 上线状态列）
- 健康判定铁律：**Registry state=ready（TTL 内心跳）为权威**；RestartCount 是生命周期累计禁单独判据；unless-stopped 自愈下单轮崩溃≠事故

### 悬而未决（下次会话候选）

1. **[P1]** SOP-01 归档模型常态化上线通道——通道就绪（alias+drain），按业务节奏触发首例
2. **[P2]** 内部 mTLS（当前 Token 已挡心跳伪造，mTLS 为纵深加固项）
3. **[P2]** Loki 崩溃关键字告警（当前 30 天保留已就绪，关键字规则可加）

### 终审整改记录（2026-10-05 第二轮，逐项闭环）

> 终审结论「有条件通过」后同日整改；复测序列见本节末。

| 编号 | 整改内容 | 状态 |
|------|------|------|
| C-1 (P0) | 10-05 治理日 24M+22新增 全量分原子提交 + 流水线四绿 | ✅ 本轮 |
| S-1a (P1) | 文档 3 处 API Key 明文 → 占位符 | ✅ 本轮 |
| S-1b (P1) | deploy 脚本历史凭据明文指纹 → 通用硬编码模式检测 | ✅ 本轮 |
| S-1c (P1) | 凭据轮换：API Key 双 key 过渡 + **PG 密码**（实勘发现现役值=泄露指纹 My151001，范围升级） | ✅ 本轮 |
| S-2 (P2) | CI safety `--fail-on high` / bandit `-lll` 升阻塞门禁 | ✅ 本轮 |
| O-1 (P2) | Alertmanager 通知通道部署（webhook 占位待填，配置族齐备） | ✅ 本轮 |
| S-3 (P3) | gitbucket remote 去 token → keychain（含 Tailscale 地址加固）；首验弹窗授权留用户 | ✅ 本轮 |
| Q-1 (P3) | canary-manage.sh 六分支参数防护（set -u 兼容） | ✅ 本轮 |
| O-2 (P3) | 部署回调改造（消除 sleep 240 静态等待） | 📋 规划：NAS rebuild 完成后回调 GitHub Deployment Status API；watch.sh 轮询 deployment 状态替代 CI 侧 sleep。涉及 rebuild-gateway.sh 加 curl 回调（需 GITHUB_TOKEN 于 NAS 侧）+ ci.yml deploy job 改 wait-on deployment 状态。收益=deploy 验证从「盲等 4min」变「事件驱动」，下轮维护窗口实施 |

**YanYuCloudCube** - 言启象限 | 语枢未来
**YYC3-0379-World** - v2.0.0 Production API Gateway
