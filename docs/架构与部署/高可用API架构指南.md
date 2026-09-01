# YYC³ 高可用 API 架构闭环 · 最佳指导文档

> **文档版本**: v1.0.0 | **生成日期**: 2026-08-30
> **体系**: YYC³ (YanYuCloudCube) · DGX Spark 双机集群 YanYuCloud（2026-08-30 官方向导验证：SSH 12/12 ✓ / 210.76 Gbps / 集群就绪）
> **定位**: 与《YYC3-DGX-Spark-双机推理部署-模型部署闭环-最佳指导文档.md》(v1.2) 成对——**那份解决「模型怎么部署跑起来」，本文解决「服务怎么对外高可用、故障怎么闭环」**；两份 + `DGX-SPARK-HUB-OFFLINE.html` 构成工作区唯一保留的三份文档
> **信息保全声明**: DGX-101/DGX-102 目录全部内容在两台设备本机有完整同步副本（路径见附录 A）；本文已固化即将清理的工作区文档关键信息（网络拓扑 / ECS 运维 / 0379-World / 四端盘点 / 08-10 架构审核），映射关系见附录 C
> **架构决策基线**: **ADR-4（2026-08-10 定稿）——NCCL 跨节点 TP=2 为永久架构约束**（GB10 双机 121GB×2 超出 int32 虚拟地址范围），双机协同一律走 **HTTP 服务级分工**；本文 API 架构即 ADR-4 的落地形态。210.76 Gbps 高速互联使跨机 HTTP 调用延迟进入亚毫秒级，服务级分工的性能代价已被底层吸收

---

## 一、核心结论（TL;DR）

1. **API 高可用架构 = 双入口 + 双网关 + 三级推理池 + systemd 化服务层 + 数据双活**：公网 Traefik(ECS) 唯一入口 → Gateway 双活（ECS 主 :8000 + NAS 备 :8000）→ 智能路由三级推理池（双 DGX 互备 + macOS Ollama 兜底 + 云 API 逃生）→ PG/Redis/ChromaDB 数据层冗余。
2. **最大教训已入档（附录 B）**：2026-08-10 审核发现 8 Agent 服务 + 治理中枢因 nohup 启动、节点重启后**全部死亡且无人恢复**（设计成熟度 63% → 实测 46%）。铁律：**一切长驻服务必须 systemd 化（`Restart=always`）**，模板见 §十一。
3. **ADR-4 是 API 层的存在理由**：NCCL TP=2 永久不可用（int32 溢出根因），双机协同只能走 HTTP——因此**网关层的智能路由质量直接决定整个集群的可用性与吞吐**，是本文的核心。
4. **安全闭环已达生产基线**（2026-08-21 加固实录）：Traefik rate-limit 20req/s + fail2ban 双 jail + 四安全头 + docker 日志轮转，全部实测验证（附录 C）；待补：守护三层安全管线（越狱/内容/PII）。
5. **五大单点待消除**（§十二路线）：NAS Gateway→Ollama 指向断裂、ECS Gateway 副本未部署、监控栈未启动、根域 0379.world 未配置、yyc3-77 热备离线。

---

## 二、全栈资产与端口总账（唯一真源表）

### 2.1 六节点矩阵（2026-08-21 实况 + 08-30 集群更新）

| 节点 | 设备 | 关键 IP | API 体系角色 | 状态 |
|------|------|---------|--------------|------|
| **yyc3-33** | 阿里云 ECS · Ubuntu 24.04 · 4C/7.1G/79G | 公网 39.97.53.176 / TS 100.126.132.112 | **生产入口**：Traefik 80/443 + Gateway :8000(主) + PG :5432 + Redis :6379 | ✅ |
| **yyc3-45** | TerraMaster F4-423 · 32G · RAID6 14.5T + NVMe RAID1 1.8T | 192.168.3.45 / TS 100.65.172.88（SSH 9557） | **网关备 + 数据中心**：Gateway v2.0.0 :8000 + Redis :6399 + NFS 模型仓库 + PG14(yyc3_kb) | ✅ |
| **yyc3-101** (N1) | DGX Spark GB10 · 121G UMA | TS 100.65.64.49 / LAN .3.101 / QSFP 10.100.168.2+169.2 | **推理节点 A**：vLLM/Ollama/组件服务（A 方案位） | ✅ |
| **yyc3-102** (N2) | DGX Spark GB10 · 121G UMA | TS 100.76.167.103 / LAN .3.102 / QSFP 10.100.168.1+169.1 | **推理节点 B + Agent 层**：vLLM + 8 Agent + 治理中枢 + 三组件 | ✅ |
| **yyc3-22** | MacBook Pro M4 Max · 128G | 192.168.3.22 / TS 100.87.159.21 | **主控 + 兜底推理**：Ollama :11434 + Dashboard :18789 | ✅ |
| **yyc3-77** | iMac M4 · 32G | TS 100.98.206.18 | 热备（PG 副本 :5434 规划） | 🔴 离线 |
| **yyc3-202** | 备用 ECS | 公网 47.94.135.202 | 入口灾备（规划） | ⚪ 冷备 |

**双机互联（2026-08-30 官方向导通过）**：集群 **YanYuCloud**，2 devices direct connection，Speed Test **210.76 Gbps**（阈值 >180），SSH 免密 12/12。跨机 HTTP 调用可走 QSFP 直连（10.100.168.x，0.2-0.3ms）或 Tailscale（100.x）双路径。

### 2.2 全局端口分配总表（跨节点防冲突 · 唯一真源）

**对外（公网，经 ECS Traefik）**：

| 端口 | 服务 | 说明 |
|------|------|------|
| 443/80 | Traefik SSL 终结 | api.0379.world；rate-limit + security-headers 中间件 |
| 8000 | Gateway API（主） | 认证 401 拦截 /health /v1/models /v1/chat/completions |

**推理服务层（DGX 双机，按部署文档 v1.2 A 方案稳态）**：

| 端口 | 服务 | 节点 | 引擎 |
|------|------|------|------|
| 8000 | 旗舰推理（NIM DeepSeek-V4-Flash NVFP4） | N2 | NIM 容器 |
| 30000 | 多模态推理（Qwen3.5-122B-A10B） | N2 | SGLang |
| 11434/11435 | 轻量 LLM（Coder-Q4 / 路由 8B） | N2 / N1 | Ollama |
| 8100/8101 | Embedding / Reranker（伯乐双件套） | N1（现网在 N2，迁移中） | TEI/systemd |
| 8001 | OCR 文档解析（nemotron-ocr-v2） | N1 | NIM 容器 |
| 8103 | 内容安全（Nemotron 系） | N1 | NIM/Ollama |
| 8004 | 中文 ASR（parakeet-zh-cn） | N1 | NIM 容器 |
| 8888 | DGX Dashboard 监控面板 | N1+N2 | Docker |

**Agent 与治理层（N2，systemd 化目标态）**：

| 端口 | 服务 | systemd 单元 |
|------|------|--------------|
| 8080 | OpenShell Gateway（nemoclaw 网关, inference.local） | NemoClaw 管理 |
| 25700 | 治理中枢（审计+预算+协同+ACS+图谱 五子系统） | `yyc3-governance.service` |
| 25600-25607 | 8 Agent（天枢/千行/万物/先知/伯乐/守护/宗师/灵韵） | `yyc3-agent@<name>.service` |
| 8102 | Memory/ChromaDB 向量记忆 | `yyc3-memory.service` |
| 18789 | OpenClaw Dashboard（SSH 端口转发，`nemoclaw recover`） | NemoClaw |

**数据层**：

| 端口 | 服务 | 节点 |
|------|------|------|
| 5432 | PostgreSQL 生产主库 | ECS |
| 54320 | PostgreSQL（Docker yyc3-pg） | NAS |
| 6379 / 6399 / 6380 | Redis（ECS 宿主 / NAS Gateway / NAS Docker） | ECS / NAS ×2 |
| 2049 | NFS 模型仓库导出 | NAS |
| 19500 | ChromaDB（设计）/ Milvus（扩展） | N2 |

### 2.3 别名登录与关键路径速查

```bash
ssh yyc3-33      # ECS 入口 (TS 100.126.132.112, root)
ssh yyc3-45      # NAS (TS 100.65.172.88, YYC3, 端口 9557)
ssh yyc3-101     # DGX N1 (TS 100.65.64.49)
ssh yyc3-102     # DGX N2 (TS 100.76.167.103)
# 扩展别名: yyc3-101-vllm / yyc3-45-gw / yyc3-45-docker / yyc3-202
```

| 关键路径 | 节点 | 内容 |
|----------|------|------|
| `/root/0379-world/` | ECS | traefik compose / dynamic.yml / certs / 监控 compose |
| `/root/yyc3-api-world/ecs_deploy.sh` | ECS | Gateway 副本部署脚本（未执行） |
| `/etc/gateway/config` | NAS | Gateway 配置（Ollama base_url 待指向 100.65.64.49:11434） |
| `/Volume1/yyc3_hd/data/` | NAS | 模型仓库真源（旗舰 NVFP4 产物目录） |
| `/home/yyc3/yyc3-102-projects/` | N2 | Agent/治理/组件服务代码 + systemd 单元 |
| `/home/yyc3/.nemoclaw/` | N2 | NemoClaw 运行时（agents/soul 人格、governance、logs） |
| `/home/yyc3/llama-factory-env/bin/python` | N2 | 服务统一 Python 解释器（systemd 用绝对路径） |

---

## 三、API 架构分层设计

### 3.1 七层 API 视图（对九层架构的 API 化重组）

```
┌────────────────────────────────────────────────────────────────┐
│ ⑦ 可观测层   DCGM + DGX Dashboard:8888 + Prometheus/Grafana/Loki│
│              (ECS compose 就绪) + 治理中枢 watchdog + 告警      │
├────────────────────────────────────────────────────────────────┤
│ ⑥ 数据层     PG :5432(ECS主)+:54320(NAS备) · Redis ×3 实例      │
│              ChromaDB :8102 · NFS 模型仓库(RAID6)               │
├────────────────────────────────────────────────────────────────┤
│ ⑤ Agent 层   8 Agent :25600-25607 + 治理中枢 :25700             │
│              (审计/预算/协同/ACS/图谱 + kill switch)             │
├────────────────────────────────────────────────────────────────┤
│ ④ 推理服务层 N2: NIM旗舰:8000 + SGLang:30000 + Ollama:11434     │
│              N1: Ollama:11435 + TEI:8100/8101 + OCR:8001        │
│                 + Safety:8103 + ASR:8004                        │
├────────────────────────────────────────────────────────────────┤
│ ③ 智能路由层 Gateway 模型路由: EWMA延迟 + 错误率 + 负载加权       │
│              + 健康探测 + 熔断 + 降级链 + Token 预算             │
├────────────────────────────────────────────────────────────────┤
│ ② 网关层     Gateway API 双活: ECS :8000(主) + NAS :8000(备)    │
│              认证(API Key/401) · 限流 · 审计日志                 │
├────────────────────────────────────────────────────────────────┤
│ ① 入口层     公网 → api.0379.world:443 → Traefik(ECS)           │
│              rate-limit 20req/s + security-headers + fail2ban   │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 与九层架构（L1-L9）映射

| 九层（08-10 审计） | API 七层 | 备注 |
|--------------------|----------|------|
| L1 基础设施 / L2 Web 标准 | ①② | REST + WebSocket；A2A 待建 |
| L3 内容处理 / L7 MCP | ④⑥ | RAG 管道与 MCP 协议挂接推理服务层 |
| L4 安全 / 守护管线 | ①②③ 贯穿 | 三层管线（越狱/内容/PII）挂接 |
| L5 Agent 服务 / L8 AI Family | ⑤ | 8 Agent + 治理中枢 |
| L6 技能层 | ⑤ | OpenClaw 插件 + NVIDIA 技能，经 Agent 调用 |
| L9 用户交互 | ① | Dashboard :18789 / TUI / CLI |

---

## 四、请求全链路（正常路径与故障域）

```
① 客户端 → https://api.0379.world/v1/chat/completions (443, TLS1.3)
② Traefik(ECS): rate-limit(20req/s,burst10) → security-headers → fail2ban 联动
③ Gateway(ECS主/NAS备): API Key 认证(401拦截) → Token 预算检查(治理中枢)
④ 智能路由决策（EWMA 延迟+错误率+负载）:
    ├─ 深度推理 → N2 NIM 旗舰 :8000（DeepSeek-V4-Flash NVFP4）
    ├─ 多模态   → N2 SGLang :30000
    ├─ 轻量/路由→ N1 Ollama :11435 或 N2 :11434
    ├─ RAG 检索 → N1 TEI :8100/:8101 → ChromaDB :8102
    └─ 故障降级 → yyc3-22 Ollama :11434 → 云端 API(DeepSeek/GLM) 逃生
⑤ 安全管线（并行）: 越狱检测 → 内容安全 :8103 → PII 脱敏
⑥ 治理中枢 :25700: 审计落库 + Token 计量 + 协同触发 + kill switch
⑦ 数据: PG(ECS) 持久化 + Redis 缓存 + ChromaDB 记忆
⑧ 可观测: 指标(Prometheus:8002) + 日志(Loki) + 硬件(DCGM)
```

**故障域划分**：入口域（ECS/公网/DNS）→ 网关域（ECS/NAS Gateway）→ 传输域（Tailscale/QSFP）→ 推理域（N1/N2/22）→ 数据域（PG/Redis/NAS）。每域的转移策略见 §5.6 矩阵。

---

## 五、高可用闭环设计

### 5.1 入口层 HA

| 机制 | 现状 | 动作 |
|------|------|------|
| Traefik SSL 终结 + Let's Encrypt | ✅ 运行（证书 90 天） | cron 自动续期确认 |
| rate-limit / security-headers / fail2ban | ✅ 08-21 加固实测通过 | 保持 |
| 根域 0379.world | ❌ 未配置（HTTP 000） | DNS A 记录 → 39.97.53.176 + Traefik router |
| 入口灾备 | ⚪ yyc3-202 冷备 | DNS TTL 调低，故障时切 A 记录 |

### 5.2 网关层 HA（双活）

```
ECS Gateway :8000（主，规划容器化）
NAS  Gateway v2.0.0 :8000（备，✅ 运行中，redis/pg 健康）
```

- **主备切换**：Traefik `gateway-api-primary@file` 路由指向 NAS Gateway 已验证打通（ECS→NAS :8000 HTTP 200, 0.9s）；ECS 副本按 `yyc3-api-world/ecs_deploy.sh` 部署后实现真正双活 + 负载均衡。
- **健康探测**：`GET /health`（返回版本号）；`/v1/models` 401 = 认证层存活。
- **已知断裂**：NAS Gateway 的 Ollama 上游 unreachable → 修复 `/etc/gateway/config` 将 `ollama base_url` 指向 `http://100.65.64.49:11434`（N1）。

### 5.3 推理服务层 HA（三级池 + ADR-4 服务级分工）

**设计原则**：不做单模型跨机分片（NCCL 永久约束），而做**服务级互备**——每个能力至少两个独立承载节点，路由层自动转移：

| 能力 | 主承载 | 备承载 | 兜底 |
|------|--------|--------|------|
| 深度推理（旗舰） | N2 NIM :8000 | N1 vLLM :8000（同款模型第二副本） | 云 API |
| 多模态 | N2 SGLang :30000 | N1 按需加载 Qwen3.5-122B | — |
| 轻量 LLM | N2 Ollama :11434 | N1 Ollama :11435 | yyc3-22 :11434 |
| RAG 双件套 | N1 TEI :8100/8101 | N2 systemd 版（现网） | — |
| OCR / ASR / 安全 | N1 :8001/:8004/:8103 | NIM 云端 API | — |

**跨机通信双路径**：QSFP 直连（10.100.168.x，0.2-0.3ms，210.76 Gbps）为主，Tailscale（100.x）为备；Gateway 上游地址配置 QSFP IP，故障自动回落 Tailscale IP。

**性能红线**（多模型共存 OOM 教训，附录 B-2）：vLLM/NIM `--gpu-memory-utilization` 必须按共存服务动态计算（旗舰+组件共存时 ≤0.55~0.6），杜绝 0.9 单服务独占配置直接复用。

### 5.4 Agent 与治理层 HA（systemd 铁律）

- 8 Agent + 治理中枢 + 三组件**全部 systemd 化**（§十一模板），`Restart=always` + `RestartSec=5`；
- 治理中枢作为 Agent 的 `Wants=` 依赖（Agent 起不来先查治理）；
- **kill switch**：守护判定 CRITICAL 时治理中枢可熔断指定 Agent/端点；
- 治理中枢自带 watchdog：子服务死亡自动告警（接入 §八监控）。

### 5.5 数据层 HA

| 数据 | 主 | 备 | 机制 |
|------|----|----|------|
| PostgreSQL | ECS :5432 生产库 | NAS yyc3-pg :54320 + pg_backup 目录 | 定时备份（Phase 2 每日快照） |
| Redis | ECS :6379 | NAS :6399/:6380 | 缓存可重建，双实例热备 |
| 向量记忆 | N2 ChromaDB :8102 | NAS PG14 yyc3_kb（19.7 万条 4096 维，⚠️ HNSW 索引 INVALID 待重建） | 持久化目录纳入备份 |
| 模型仓库 | NAS /Volume1（RAID6 4×8T，SMART 全绿） | macOS Max 盘副本 | 权重可重拉，冷备 |
| 配置 | 各节点 | NAS /Volume3/database + 版本化 | Git 化（Phase 3） |

### 5.6 故障转移矩阵（Runbook 索引）

| # | 故障 | 检测信号 | 自动动作 | 人工动作（→§十） |
|---|------|----------|----------|------------------|
| F1 | N2 旗舰 :8000 宕 | /health 超时 ×3 | 路由摘除 → N1 vLLM | RB-1 |
| F2 | ECS Gateway 挂 | Traefik 5xx | Traefik 切 NAS Gateway | RB-2 |
| F3 | 8 Agent 全死 | 端口探测 25600-07 | systemd 自动拉起 | RB-3 |
| F4 | 治理中枢死 | :25700 /health | systemd 拉起 + kill switch 复位 | RB-3 |
| F5 | vLLM OOM 循环 | 容器重启计数 | — | RB-4（降 mem-util） |
| F6 | NAS NFS 失联 | mount 超时 | 模型加载队列暂停 | RB-5 |
| F7 | 证书过期 | 到期 <14 天告警 | — | RB-6 |
| F8 | 扫描攻击峰值 | fail2ban 计数 | 自动封禁 | RB-7 |
| F9 | QSFP 链路劣化 | ping 丢包 >1% | 路由切 Tailscale | RB-8 |
| F10 | PG 主库故障 | 连接错误率 | 读写降级 NAS :54320 | RB-9 |

---

## 六、API 契约与路由表

### 6.1 对外 API（OpenAI 兼容）

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/health` | GET | 存活+版本（Traefik/Gateway 探测用） | 无 |
| `/v1/models` | GET | 模型列表（含路由元数据） | API Key |
| `/v1/chat/completions` | POST | 对话推理（stream 可选） | API Key |
| `/v1/embeddings` | POST | 向量化（代理 → TEI :8100） | API Key |
| `/v1/rerank` | POST | 重排（代理 → :8101） | API Key |
| `/v1/audio/transcriptions` | POST | 语音转写（→ ASR :8004） | API Key |
| `/v1/ocr` | POST | 文档解析（→ OCR :8001） | API Key |

### 6.2 内部端点语义（Gateway 上游表）

| 上游 | 地址（QSFP 优先） | 健康检查 | 用途 |
|------|-------------------|----------|------|
| nim-flagship | `http://10.100.168.1:8000` | /health | 旗舰深度推理 |
| sglang-vlm | `http://10.100.168.1:30000` | /health | 多模态 |
| ollama-n2 / ollama-n1 | `10.100.168.1:11434` / `10.100.168.2:11435` | /api/tags | 轻量 |
| tei-embed / tei-rerank | `10.100.168.2:8100/8101` | /health | RAG |
| ocr / asr / safety | `10.100.168.2:8001/8004/8103` | /health | 组件 |
| agent-×8 | `127.0.0.1:25600-25607`（N2 本机） | /health | Agent 层 |
| governance | `127.0.0.1:25700`（N2 本机） | /health | 审计/预算 |
| fallback-local | `100.87.159.21:11434` | /api/tags | macOS 兜底 |
| fallback-cloud | DeepSeek / 智谱 GLM API | — | 云端逃生 |

### 6.3 智能路由策略

```
评分 = w1·EWMA_latency + w2·error_rate + w3·load + w4·priority
熔断: 连续 3 次健康失败 → 摘除 30s（半开探测恢复）
降级链: 旗舰 N2 → 旗舰 N1 → 本地 Ollama 轻量 → 云 API（标记 degraded 响应头）
粘性: 会话 ID 哈希（prefix cache 命中率优先）
```

### 6.4 限流与配额

| 层 | 规则 | 依据 |
|----|------|------|
| Traefik | 20 req/s, burst 10（IP 级） | 08-21 实测拦截生效 |
| Gateway | 60 req/min/用户 + 10,000 tokens/min（vllm_batch_config rate_limit 段） | 101 实测配置 |
| 治理中枢 | Token 预算（按 Agent/用户配额），超限 429 + 审计 | 五子系统之预算 |
| fail2ban | sshd + traefik-auth 双 jail | 运行中 |

---

## 七、SLA 与 Agent 端到端指标

| Agent | 服务端口 | 延迟 SLA | 精度 SLA | 目标模型（部署文档 §7） |
|-------|----------|----------|----------|------------------------|
| 言启·千行 | :25601 | <200ms | >95% | qwen3:8b (N1) |
| 语枢·万物 | :25602 | <2s | >92% | 旗舰共享 (N2) |
| 预见·先知 | :25603 | <3s | >85% | 旗舰共享 (N2) |
| 千里·伯乐 | :25604 | <500ms | >88% | TEI 双件套 (N1) |
| 元启·天枢 | :25600 | <500ms | >90% | 旗舰 (N2) |
| 智云·守护 | :25605 | <100ms | >99% | 安全管线 (N1+云) |
| 格物·宗师 | :25606 | <1s | >80% | Coder-Q4 (N2) |
| 创想·灵韵 | :25607 | <2s | >85% | qwen3:14b (N1) |

**推理层验收**：GPU 利用率 >60% · 首 token P95 <50ms · 并发 ≥32 · 可用性 >99.9%（部署文档 §十二同源口径）。

---

## 八、可观测性闭环

| 维度 | 工具 | 状态 |
|------|------|------|
| 硬件/GPU | DCGM + `nvidia-smi topo -m` + DGX Dashboard :8888 | Dashboard 待拉起（一条 docker run） |
| 服务指标 | vLLM Prometheus :8002 → Grafana :3000（ECS compose 就绪） | ⚠️ 监控栈未启动（P1） |
| 日志 | 容器 stdout + Agent 日志 `~/.nemoclaw/agents/logs/<name>.log` + Loki | logrotate 已配（100M×5 compress） |
| 业务审计 | 治理中枢 :25700（行为审计/Token 计量） | systemd 化后带 watchdog |
| 告警 | Grafana 告警 → 通知渠道；UMA>95% / 端口失活 / 证书<14天 | Phase 2 |

**每日巡检清单**：`/health` 全端点 → 8 Agent 端口 → UMA 水位 → NAS Volume1 容量（63% 起）→ QSFP 丢包 → fail2ban 计数。

---

## 九、安全基线闭环

**已就位（2026-08-21 实测验证，变更均有备份）**：

| 项 | 值 | 验证结果 |
|----|----|----------|
| rate-limit | 20req/s burst 10 | ab 60 请求 → 15 Non-2xx，高频连接重置 ✓ |
| security-headers | X-Frame/X-Content-Type/Referrer/Permissions 四头 | 全部返回 ✓ |
| fail2ban | sshd + traefik-auth 双 jail | filter 匹配 docker JSON 日志 ✓ |
| logrotate | docker 容器日志 100M×5 compress | 313M→轮转归零，容器不中断 ✓ |
| API 认证 | Gateway 401 拦截 | /v1/models 无 Key 返回 401 ✓ |
| 传输 | TLS 1.3 + Tailscale 全网加密 | api.0379.world 200 (0.6-1.3s) ✓ |

**待补**：守护三层管线（nemoguard-jailbreak-detect ~100ms → Nemotron-Safety :8103 ~50ms → gliner-pii ~50ms）挂接 Gateway 出入口；NAS Gateway Ollama 指向修复；SSH 密钥收敛（8+ 把 → yyc3_ed25519/yyc3_dgx 两把）。

---

## 十、Runbook（现象 → 定位 → 修复）

```bash
# RB-1 推理服务宕（N2 :8000）
ssh yyc3-102 "docker ps -a | grep -i nim; curl -s localhost:8000/health"
# 修复: docker restart <nim> ；连续崩溃查 OOM(RB-4)；路由层应已自动切 N1

# RB-2 Gateway 故障切换
curl -s http://100.65.172.88:8000/health          # NAS 备网关
# ECS 主网关: cd /root/yyc3-api-world && bash ecs_deploy.sh

# RB-3 Agent/治理中枢死亡（systemd 化后应自愈，手动兜底）
python3 ~/.nemoclaw/agents/launch_agents.py start && python3 ~/.nemoclaw/agents/launch_agents.py test
bash ~/.nemoclaw/governance/start.sh
python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:25700/health')"

# RB-4 vLLM OOM 崩溃循环（历史事故，见附录 B-2）
# 降配: --gpu-memory-utilization 0.55 --max-model-len 65536（多模型共存时）

# RB-5 NFS 失联
ssh yyc3-45 "df -h /Volume1"; mount -t nfs 100.65.172.88:/Volume1/yyc3_hd/data /mnt/yyc3_hd

# RB-6 证书续期
ssh yyc3-33 "ls /root/0379-world/certs; certbot renew --dry-run"

# RB-7 攻击峰值
ssh yyc3-33 "fail2ban-client status traefik-auth"; docker logs docker-traefik-1 --tail 100

# RB-8 QSFP 链路劣化 → 切 Tailscale
ping -c 100 10.100.168.2; # Gateway 上游改 100.x IP（配置双上游）

# RB-9 PG 主库故障
psql -h 100.65.172.88 -p 54320 -U postgres -c '\l'   # NAS 备库接管读写

# RB-10 NAS Gateway Ollama unreachable（已知断裂）
ssh yyc3-45 "sudo vi /etc/gateway/config"   # ollama base_url → http://100.65.64.49:11434
```

---

## 十一、systemd 服务化标准（铁律 + 模板）

> 铁律（08-10 审计教训）：**先手动验证入口，再写 unit；一切长驻服务 `Restart=always`；解释器用绝对路径 `/home/yyc3/llama-factory-env/bin/python`。**

```ini
# /etc/systemd/system/yyc3-agent@.service（模板实例 yyc3-agent@tianshu 等 8 个）
[Unit]
Description=YYC3 FAmily-AI Agent (%i)
After=network.target yyc3-governance.service docker.service
Wants=network.target yyc3-governance.service

[Service]
Type=simple
User=yyc3
Group=yyc3
Environment=AGENT_NAME=%i
Environment=VLLM_ENDPOINT=http://127.0.0.1:8000/v1
Environment=VLLM_MODEL=Qwen/Qwen3.6-27B-FP8
Environment=SYSTEM_PROMPT_PATH=/home/yyc3/.nemoclaw/agents/soul/%i.md
Environment=GOVERNANCE_ENDPOINT=http://127.0.0.1:25700
Environment=PYTHONPATH=/home/yyc3/.nemoclaw/agents:/home/yyc3/.nemoclaw/memory
ExecStart=/home/yyc3/llama-factory-env/bin/python3 /home/yyc3/yyc3-102-projects/yyc3-family-ai-agents/agent_server.py --port ${PORT} --role ${ROLE}
WorkingDirectory=/home/yyc3/yyc3-102-projects/yyc3-family-ai-agents
Restart=always
RestartSec=5
StandardOutput=append:/home/yyc3/.nemoclaw/agents/logs/%i.log
StandardError=append:/home/yyc3/.nemoclaw/agents/logs/%i.log
KillSignal=SIGTERM
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
```

```ini
# 组件服务（embedding 示例，reranker/memory/governance 同构）
[Unit]
Description=YYC³ Embedding Service (Qwen3-Embedding-8B)
After=network.target
[Service]
Type=simple
User=yyc3
ExecStart=/home/yyc3/llama-factory-env/bin/python /home/yyc3/yyc3-102-projects/embedding_server.py
Restart=on-failure
RestartSec=10
Environment=EMBEDDING_PORT=8100
Environment=EMBEDDING_MODEL_PATH=/home/yyc3/models/Qwen3-Embedding-8B
[Install]
WantedBy=multi-user.target
```

```bash
# 启用与验证（全部服务）
sudo systemctl daemon-reload
for s in yyc3-governance yyc3-embedding yyc3-reranker yyc3-memory; do sudo systemctl enable --now $s; done
for a in tianshu qianxing wanwu xianzhi bole shouhu zongshi lingyun; do sudo systemctl enable --now yyc3-agent@$a; done
systemctl list-units 'yyc3-*' --no-pager     # 13 服务全绿
```

---

## 十二、实施路线（P0 → P3）

| 优先级 | 任务 | 验收 | 依据 |
|--------|------|------|------|
| **P0** | Agent/治理/组件 systemd 化（§十一）+ 重启自愈验证 | reboot 后 13 服务自动全绿 | 审核 U3 |
| **P0** | NAS Gateway Ollama 指向 N1（RB-10） | /v1/models 含 Ollama 模型 | 拓扑缺口 |
| **P1** | ECS Gateway 副本部署（ecs_deploy.sh）→ 网关真双活 | Traefik 双上游负载 | ECS 运维 |
| **P1** | 监控栈启动（Prometheus/Grafana/Loki）+ DGX Dashboard :8888 | Grafana 面板出数 + 告警接通 | 拓扑 Phase1 |
| **P1** | N1 组件服务激活（TEI 双件套迁移 + OCR/ASR/安全） | 8100/8101/8001/8004/8103 健康 | 审核 U4/U5 |
| **P2** | 守护三层管线挂接 Gateway 出入口 | 越狱/PII 用例拦截 | 审核 G10 |
| **P2** | 根域 0379.world + 证书自动续期 cron | https://0379.world 200 | ECS Phase3 |
| **P2** | yyc3_kb HNSW 索引重建 + PG 每日备份 | RAG 检索恢复 + 快照落 NAS | NAS 报告 |
| **P3** | yyc3-77 热备复活（PG 副本 :5434）/ yyc3-202 入口灾备演练 / 配置 Git 化 | 故障切换演练通过 | 拓扑 Phase2 |

---

## 附录 A：设备侧文档同步副本索引（工作区已精简，真源在设备）

| 设备 | 同步路径 | 内容 |
|------|----------|------|
| yyc3-101 | `~/YYC3-专属文档/`（对应原工作区 YYC3-DGX-101/YYC3-101-专属文档/） | 00-11 编号报告 / NVIDIA-ku 8 篇技术库 / NemoClaw 5 篇 / scripts+configs / NIM 全量分析副本 / 提示词工程库 |
| yyc3-102 | `~/YYC3-专属文档/` + `~/yyc3-102-projects/`（对应原 YYC3-DGX-102/） | 蓝图实战 00-12 / 现状进度 00-02 / AI-Family 档案 / NemoClaw 运维手册 / Agent+治理+组件代码与 systemd 单元 / DPO 训练资产 |
| 三方同步规则 | N1 + N2 + MacBook 保持一致，变更后同步并重审 /etc/hosts 旧条目 | 08-10 审核建议 |

> 工作区保留三件套：`DGX-SPARK-HUB-OFFLINE.html`（官方 45 指南）/ 双机推理部署闭环 v1.2 / 本文档。模型资产真源 NAS `/Volume1/yyc3_hd/data`，macOS Max 盘为副本。

## 附录 B：历史事故与根因档案（防复发）

| # | 事故 | 根因 | 永久对策 |
|---|------|------|----------|
| B-1 | 8 Agent + 治理中枢全灭（07-29 启动后某次重启全部死亡，08-10 才发现，成熟度 63%→46%） | nohup 启动、无 systemd、无 watchdog | §十一 systemd 铁律 + 治理 watchdog |
| B-2 | vLLM 容器 OOM 崩溃循环（宕机 5 天） | gpu-mem-util 0.7 独占假设，与 Embedding(15G)+Reranker(18G) 共存爆掉 121G UMA | 共存时 mem-util ≤0.55~0.6 + max-len 降档；容器 commit 固化 |
| B-3 | NCCL 跨节点 TP=2 永久死锁 | GB10 双机 UMA 对称虚拟地址 int32 溢出（121GB×2 超范围，malloc -24.8GB） | **ADR-4 服务级分工**（本文架构）；官方向导 210.76 Gbps 只保证链路层，集合通信层仍以此档案为准，NVIDIA 修复前禁用 TP=2 |
| B-4 | 旧 QSFP link-local 169.254.x 全失效 | 拓扑变更未同步 /etc/hosts 与文档 | 以官方向导注册的 10.100.168/169.x 为准 |
| B-5 | NAS Gateway 容器曾 unhealthy | 配置错误 | 08-21 修复为 healthy（v2.0.0）；Ollama 上游断裂仍待 RB-10 |

## 附录 C：本档案固化的信息映射（原工作区文档 → 本文位置）

| 原文档（已清理） | 固化到 |
|------------------|--------|
| YYC3-高可用多设备网络拓扑-可视化架构链路文档 | §2.1 / §4 / §5.1-5.2 / §9 / §十二 |
| YYC3-33-ECS上线-运维总结与后续执行方案 | §2.1 / §5.1 / §5.2 / §9 / RB-2/6/7 |
| YYC3-0379-World-多端部署落地建议与全链路别名登录方案 | §2.3 / §5.2 / §十二 |
| YYC3-四端模型全景盘点与NIM落地方案 | §5.3（模型能力池）；NIM 细节在设备侧 NIM 报告副本 |
| YYC3-设备-模型全量信息文档（2026-08-30 汇总版） | §2 全量端口/节点表 + 部署文档 §四资产池 |
| DGX-102《02-全链路架构审核报告-2026-08-10》 | §3.2 / §5.4 / §7 / 附录 B / §十二（设备侧有原件） |
| DGX-102《10-全链路闭环部署指南-2026-08-10》 | §2.2 端口表 / §十一 systemd 模板（设备侧有原件） |
| DGX-101《NemoClaw-多设备协同架构》 | §3.1 网关/分布式推理/主控-计算分离理念（设备侧有原件） |

---

> **YYC³ AI Family** | 言启象限 · 语枢未来
> 文档管理员: YYC³ 总指挥 | 2026-08-30
> 🌹 人从众曌众从人 · 亦师亦友亦伯乐
