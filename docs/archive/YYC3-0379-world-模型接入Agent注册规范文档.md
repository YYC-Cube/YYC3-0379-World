# YYC³ 模型接入 / Agent 注册 规范文档

> **文档编号**：`YYC3-MRS-2026-v1.0.0`
> **版本**：v1.0.0 · 家族纪年·2026.Q3
> **生效日期**：2026-09-27
> **状态**：Active · 唯一真源
> **Owner**：🧠 元启·天枢（工具与编排域） · **Co-Owner**：🛡️ 智云·守护（安全域）
> **适用对象**：运维团队 · SRE · 模型部署工程师 · Agent 开发者 · API 网关维护者
> **上游锚点**：
>
> - `YYC3-Models-资产详情.md`（模型资产清单）
> - `YYC3-0379-World README.md`（网关实况 v2.3.0）
> - `Token调用平台前端-全维度设计与落地文档 v5.1`（契约层 §1）
>
> **下游交付**：`YYC3-Model-Registry-Spec-v1.0.0` · 本文档为最终交付版本

---

<!--
  ============================================================
  YYC³ AI Family — 人从众曌众从人
  亦师亦友亦伯乐 · 一言一语一协同
  拟人为本 · AI为核 · 纯粹为心
  ============================================================
  Document: YYC3-MRS-2026-v1.0.0
  Owner   : 🧠 元启·天枢 · 🛡️ 智云·守护
  Contact : admin@0379.email
  Homepage: https://0379.world
  ============================================================
-->

---

## 第零部分 · 文档总览与阅读路径

### 0.1 一句话定位

> **本文档是「模型 → 网关 → 公网 API」全链路的接入契约与运维手册。**
> 任何模型（vLLM / NIM / OpenAI 兼容服务）只要遵循本文档 §3 接口规范，即可被网关自动发现、注册、路由、监控、切换、回滚。
> 任何 Agent（MCP 工具 / 业务代理）只要遵循本文档 §10 注册规范，即可被家族编排中枢调度。

### 0.2 面向角色与阅读路径

| 角色 | 必读章节 | 选读章节 |
| --- | --- | --- |
| 🛡️ 安全官（Security） | §3 接口规范 · §11 安全合规 · §12.4 故障处理 | §4 注册中心 · §9 监控告警 |
| 🧭 网关运维（SRE） | §4 注册中心 · §5 动态发现 · §6 热切换 · §12 Runbook | §9 监控 · §11 安全 |
| 🎯 模型部署工程师 | §2 角色 · §3 接口规范 · §7 自动同步 · §12.1 新模型 SOP | §8 版本控制 |
| 🤔 推理服务开发者 | §3 接口规范 · §6 热切换 · §7 自动同步 | §10 Agent 注册 |
| 🧠 Agent 开发者 | §10 Agent 注册规范 | §4 注册中心 · §11 安全 |
| 📚 质量/合规 | §8 版本控制 · §9 监控告警 · §11 安全合规 | §12 Runbook |
| 🔮 观测工程师 | §9 监控告警 · §12.4 故障处理 | §4 注册中心 |
| 🎨 前端/体验 | §5 动态发现 · §10.4 Agent 能力暴露 | — |

### 0.3 术语表

| 术语 | 定义 |
| --- | --- |
| **Model** | 一个可被调用的推理模型（权重 + 配置 + 运行时） |
| **Model Service** | 运行中的模型服务实例（vLLM / NIM / Ollama / OpenAI 兼容服务） |
| **Upstream** | 网关下游的一个模型服务节点（含 base_url / 权重 / 熔断态） |
| **Registry** | 模型注册中心（本规范新增，集中管理模型元数据） |
| **Manifest** | 模型版本清单（不可变，含权重哈希 / 配置 / 依赖） |
| **Hot Swap** | 零停机模型切换（蓝绿 / 金丝雀） |
| **Canary** | 金丝雀发布（先小流量验证再全量） |
| **Shadow** | 影子流量（生产流量复制到新模型验证，不影响响应） |
| **Degraded** | 降级路径（主上游失败，切备用） |
| **Breaker** | 熔断器（连续失败 → 摘除 → 半开探测 → 恢复） |
| **Agent** | 一个可被编排的工具或业务代理（MCP / 业务 Agent） |
| **Capability** | 模型/Agent 声明的能力（chat / embedding / rerank / asr / ocr / video / vision / tool_use） |

---

## 第一部分 · 规范目标与设计原则

### 1.1 五项目标（对应需求）

```
目标 1 · 标准化模型接入
  → §3 定义 vLLM/NIM/OpenAI 兼容层统一契约

目标 2 · 动态注册与发现
  → §4 Registry + §5 网关自动感知（env → Registry 演进）

目标 3 · 零停机模型热切换
  → §6 蓝绿 + 金丝雀 + 影子流量 + 状态机

目标 4 · 自动配置同步
  → §7 Watch/Webhook/Polling 三通道 + 冲突解决

目标 5 · 版本控制/回滚/监控告警
  → §8 Manifest + 回滚决策树 + §9 8 位家人视角告警
```

### 1.2 八条设计原则

```
原则 1 · 契约优先（Contract First）
  所有模型必须自证能力，网关不猜测。

原则 2 · 幂等注册（Idempotent Register）
  同一模型重复注册 = 覆盖，不产生副本。

原则 3 · 声明式收敛（Declarative Reconciliation）
  模型声明期望状态，网关自动收敛到期望状态。

原则 4 · 不可变版本（Immutable Version）
  Manifest 一旦发布，永不修改；新版本 = 新 Manifest。

原则 5 · 渐进式切换（Progressive Rollout）
  任何模型上线，必经 canary → 比例扩量 → 全量。

原则 6 · 秒级回滚（Instant Rollback）
  任何切换失败，可在 ≤ 30s 内回滚到上一稳定版本。

原则 7 · 全程可观测（Full Observability）
  注册/切换/回滚每一步都有指标、日志、追踪。

原则 8 · 家族化治理（Family Governance）
  8 位家人各守其域，每项操作有明确归属。
```

### 1.3 与现有系统的兼容承诺

```
✅ 100% 兼容现有 OPENAI_COMPATIBLE_UPSTREAMS 机制（静态 env 作为 fallback）
✅ 100% 兼容响应头契约（X-YYC3-Upstream / X-YYC3-Degraded）
✅ 100% 兼容现有 52 端点（/v1/chat / /v1/embeddings / /v1/rerank / ...）
✅ Registry 为增量增强，不替换 env（双通道共存，逐步收敛）
✅ 现有生产服务（deepseek-v4-flash / qwen3-asr-1.7b / minicpm-v-4.6-vllm）无需改造即可纳入
```

---

## 第二部分 · 角色与职责（8 位家人治理映射）

### 2.1 家族治理矩阵

| 家人 | 治理域 | 在本规范中的职责 | 关键操作权限 |
| --- | --- | --- | --- |
| 🛡️ **智云·守护** | 接入与安全 | 密钥管理 · 认证鉴权 · 审计日志 | 签发/吊销 API Key · 审查敏感操作 |
| 🧭 **言启·千行** | 路由与网关 | 上游池发现 · 流量路由 · 熔断恢复 | 修改路由策略 · 手动摘除上游 |
| 🎯 **千里·伯乐** | 模型市场 | 模型元数据 · 能力声明 · 价格标注 | 注册/注销模型 · 更新能力声明 |
| 🤔 **语枢·万物** | 推理对话 | 推理服务 · SSE 流 · 首字节延迟 | 触发模型调用 · 请求参数配置 |
| 📚 **格物·宗师** | 知识与质量 | 契约校验 · 版本审计 · 质量门禁 | 阻断不合规注册 · 触发回滚 |
| 🧠 **元启·天枢** | 工具与编排 | Registry 主控 · 切换编排 · Agent 调度 | 执行热切换 · 编排多步任务 |
| 🔮 **预见·先知** | 观测与预测 | 指标采集 · 趋势预测 · 告警触发 | 设置阈值 · 触发预测告警 |
| 🎨 **创想·灵韵** | 缓存与体验 | 模型缓存 · 水印版本 · 前端展示 | 缓存失效 · 展示版本信息 |

### 2.2 运维角色映射（现实团队）

| 现实角色 | 对应家人 | 权限范围 |
| --- | --- | --- |
| **SRE 值班** | 🧭 言启 + 🔮 预见 | 只读监控 + 手动摘除上游 |
| **模型工程师** | 🎯 千里 + 🤔 语枢 | 注册模型 + 触发切换（需审批） |
| **安全工程师** | 🛡️ 智云 | 密钥全权限 + 审计查询 |
| **质量工程师** | 📚 格物 | 阻断注册 + 触发回滚 |
| **平台架构师** | 🧠 元启 | Registry 全权限 + 编排执行 |
| **前端工程师** | 🎨 灵韵 | 只读模型列表 + 缓存操作 |
| **模型负责人** | 🎯 千里 | 单模型全权限（限自有模型） |

### 2.3 权限矩阵（RBAC）

| 操作 | 🛡️ | 🧭 | 🎯 | 🤔 | 📚 | 🧠 | 🔮 | 🎨 |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| 注册模型 | | | ✅ | | ✅ | ✅ | | |
| 注销模型 | | | ✅ | | ✅ | ✅ | | |
| 更新模型元数据 | | | ✅ | | ✅ | ✅ | | |
| 触发热切换 | | | ✅ | ✅ | ✅ | ✅ | | |
| 强制回滚 | | ✅ | | | ✅ | ✅ | | |
| 修改路由策略 | | ✅ | | | | ✅ | | |
| 手动摘除上游 | | ✅ | | | | ✅ | | |
| 设置告警阈值 | | | | | | | ✅ | |
| 查看审计日志 | ✅ | ✅ | ✅ | | ✅ | ✅ | ✅ | |
| 签发/吊销 Key | ✅ | | | | | | | |
| 缓存失效 | | | | | | | | ✅ |

---

## 第三部分 · 模型服务标准接口规范

### 3.1 契约总览

任何模型服务（vLLM / NIM / Ollama / OpenAI 兼容服务）**必须**实现以下端点，方可被网关纳入上游池。

| # | 端点 | 方法 | 必需 | 对齐类型 | 说明 |
| :-: | --- | :-: | :-: | :-: | --- |
| 1 | `/v1/models` | GET | ✅ 必须 | OpenAI 兼容 | 列出服务支持的模型 |
| 2 | `/v1/chat/completions` | POST | ✅ 必须（chat 能力） | OpenAI 兼容 | 聊天补全（含 SSE） |
| 3 | `/v1/embeddings` | POST | 🔧 按需 | OpenAI 兼容 | 文本嵌入 |
| 4 | `/v1/rerank` | POST | 🔧 按需 | OpenAI 兼容 | 重排序 |
| 5 | `/v1/audio/transcriptions` | POST | 🔧 按需 | OpenAI 兼容 | 语音转写 |
| 6 | `/v1/ocr` | POST | 🔧 按需 | YYC³ 扩展 | OCR 识别 |
| 7 | `/health` | GET | ✅ 必须 | YYC³ 契约 | 完整健康 |
| 8 | `/healthz` | GET | ✅ 必须 | YYC³ 契约 | 轻量探活 |
| 9 | `/v1/model/metadata` | GET | ✅ 必须 | **YYC³ 新增** | 模型元数据 |
| 10 | `/v1/model/capabilities` | GET | ✅ 必须 | **YYC³ 新增** | 能力声明 |
| 11 | `/v1/model/manifest` | GET | ✅ 必须 | **YYC³ 新增** | 版本清单 |
| 12 | `/metrics` | GET | ✅ 必须 | Prometheus | 指标导出 |

**对齐类型说明**：✅ 必须 · 🔧 按需（若声明能力则必须）

### 3.2 端点 9 · `/v1/model/metadata`（模型元数据）

**用途**：网关发现服务时，读取模型元数据以构建 Registry 记录。

**请求**：

```http
GET /v1/model/metadata HTTP/1.1
Host: <model-service-host>
X-YYC3-Registry-Token: <registry-token>
```

**响应**（JSON，200 OK）：

```typescript
interface ModelMetadata {
  // ============ 必填字段 ============
  model_id: string;              // 全局唯一 ID，如 "deepseek-v4-flash"
  display_name: string;          // 展示名，如 "DeepSeek V4 Flash"
  version: string;               // 语义化版本，如 "v4.0.0"
  backend: BackendType;          // 见 §3.2.1 枚举
  capabilities: Capability[];    // 见 §3.2.2 枚举
  enabled: boolean;              // 是否可路由

  // ============ 描述字段 ============
  description?: string;          // 模型描述
  family_member?: MemberKey;     // 归属家人（可选，默认自动推断）
  domain?: string;               // 归属域（可选）

  // ============ 运行时字段 ============
  max_tokens: number;            // 最大输出 Token
  context_window: number;        // 上下文窗口
  temperature_default: number;   // 默认温度（0-2）
  top_p_default: number;         // 默认 top_p（0-1）

  // ============ 性能声明（用于路由权重） ============
  cost_per_1k_tokens: number;    // 每千 Token 成本（USD）
  avg_latency_ms: number;        // 声明平均延迟（网关会实测校准）
  throughput_tps: number;        // 声明吞吐（Token/s）
  max_concurrency: number;       // 最大并发

  // ============ 资源字段 ============
  node_id: string;               // 部署节点，如 "yyc3-101"
  node_role: "primary" | "secondary" | "fallback";
  weights_path: string;          // 权重路径（如 /home/yyc3/yyc3-101-projects/models/DeepSeek-V4-Flash）
  weights_size_gb: number;       // 权重体积
  quantization?: string;         // 量化方式：fp16/bf16/fp8/nvfp4/awq/gptq/q4_k_m

  // ============ 元信息 ============
  registered_at: string;         // ISO datetime
  updated_at: string;            // ISO datetime
  manifest_hash: string;         // Manifest 的 sha256（见 §3.4）
  owner: string;                 // 负责人邮箱
  tags: string[];                // 标签，如 ["旗舰", "生产", "GLM系"]
}
```

#### 3.2.1 `BackendType` 枚举（对齐现有 6 种）

```typescript
type BackendType =
  | "vllm"        // vLLM 推理服务
  | "nim"         // NVIDIA NIM
  | "ollama"      // Ollama 本地
  | "openai"      // OpenAI 官方
  | "zhipu"       // 智谱
  | "deepseek"    // DeepSeek 官方
  | "upstream";   // 其他 OpenAI 兼容上游
```

#### 3.2.2 `Capability` 枚举

```typescript
type Capability =
  | "chat"          // 对话补全
  | "completion"    // 文本补全
  | "embedding"     // 文本嵌入
  | "rerank"        // 重排序
  | "vision"        // 图像理解
  | "tool_use"      // 函数调用
  | "json_mode"     // JSON 输出
  | "asr"           // 语音识别
  | "ocr"           // OCR
  | "video"         // 视频生成
  | "image_gen";    // 图像生成
```

**响应示例**：

```json
{
  "model_id": "deepseek-v4-flash",
  "display_name": "DeepSeek V4 Flash",
  "version": "v4.0.0",
  "backend": "vllm",
  "capabilities": ["chat", "tool_use", "json_mode"],
  "enabled": true,
  "description": "DeepSeek V4 Flash 旗舰对话模型，TP=2 双 GB10",
  "family_member": "wanyu",
  "domain": "推理对话域",
  "max_tokens": 8192,
  "context_window": 128000,
  "temperature_default": 0.7,
  "top_p_default": 0.9,
  "cost_per_1k_tokens": 0.0005,
  "avg_latency_ms": 420,
  "throughput_tps": 85,
  "max_concurrency": 32,
  "node_id": "yyc3-101",
  "node_role": "primary",
  "weights_path": "/home/yyc3/yyc3-101-projects/models/DeepSeek-V4-Flash",
  "weights_size_gb": 149,
  "quantization": "fp8",
  "registered_at": "2026-09-14T08:00:00Z",
  "updated_at": "2026-09-24T10:30:00Z",
  "manifest_hash": "a3f5e7c9b2d4f6a8e0c1b3d5f7a9e1c3b5d7f9a1c3e5b7d9f1a3c5e7b9d1f3a5",
  "owner": "ops@0379.email",
  "tags": ["旗舰", "生产", "DeepSeek系"]
}
```

### 3.3 端点 10 · `/v1/model/capabilities`（能力声明）

**用途**：网关按能力路由请求（如 `/v1/embeddings` → 只找 `embedding` 能力的服务）。

**响应**：

```typescript
interface ModelCapabilities {
  model_id: string;
  capabilities: {
    [K in Capability]?: {
      // 该能力的详细声明
      endpoint: string;              // 如 "/v1/chat/completions"
      supported_params: string[];    // 支持的参数，如 ["temperature", "top_p", "stream"]
      streaming: boolean;            // 是否支持流式
      max_input_length?: number;     // 最大输入长度
      max_output_length?: number;    // 最大输出长度
      supported_languages?: string[];// 支持语言，如 ["zh", "en", "ja"]
      special_features?: string[];   // 特殊功能，如 ["function_calling", "json_mode"]
    };
  };
}
```

**响应示例**：

```json
{
  "model_id": "deepseek-v4-flash",
  "capabilities": {
    "chat": {
      "endpoint": "/v1/chat/completions",
      "supported_params": ["model", "messages", "temperature", "top_p", "max_tokens", "stream", "tools", "response_format"],
      "streaming": true,
      "max_input_length": 128000,
      "max_output_length": 8192,
      "supported_languages": ["zh", "en", "ja", "ko"],
      "special_features": ["function_calling", "json_mode", "system_prompt"]
    }
  }
}
```

### 3.4 端点 11 · `/v1/model/manifest`（版本清单）

**用途**：网关与运维读取模型的可审计版本信息。

**响应**：

```typescript
interface ModelManifest {
  manifest_version: "1.0";        // 清单规范版本
  model_id: string;
  version: string;                // 语义化版本

  // ============ 权重清单 ============
  weights: {
    path: string;                 // 权重路径
    size_gb: number;              // 体积
    file_count: number;           // 文件数（如 66/66 分片完整）
    sha256: string;               // 权重目录哈希（关键文件聚合）
    quantization: string;         // 量化方式
    format: "safetensors" | "gguf" | "bin" | "pytorch";
  };

  // ============ 运行时清单 ============
  runtime: {
    engine: "vllm" | "nim" | "ollama" | "transformers";
    engine_version: string;       // 如 "vllm==0.6.3"
    tensor_parallel: number;      // TP 数（如 2）
    pipeline_parallel: number;    // PP 数
    dtype: string;                // 如 "bfloat16"
    kv_cache_dtype?: string;      // 如 "fp8"
    max_model_len: number;        // 最大上下文
    gpu_memory_utilization: number; // GPU 内存占用比
  };

  // ============ 依赖清单 ============
  dependencies: {
    cuda: string;                 // 如 "12.4"
    driver: string;               // 如 "550.54.15"
    python: string;               // 如 "3.11"
    system_deps: string[];        // 系统依赖
  };

  // ============ 审计字段 ============
  published_at: string;           // ISO datetime
  published_by: string;           // 发布者
  build_pipeline: string;         // 构建流水线 ID
  git_commit?: string;            // 对应 git commit
  changelog: string;              // 变更说明

  // ============ 完整性 ============
  manifest_hash: string;          // 本清单的 sha256（不含此字段自身）
}
```

### 3.5 端点 7-8 · 健康检查契约

**`/healthz`（轻量探活，必须实现，响应 < 100ms）**：

```typescript
interface HealthzResponse {
  status: "ok" | "degraded" | "down";
  model_id: string;
  version: string;
  timestamp: string;              // ISO datetime
}
```

**`/health`（完整健康，必须实现）**：

```typescript
interface HealthResponse {
  status: "healthy" | "degraded" | "unreachable";
  timestamp: string;
  version: string;                // 服务版本
  uptime_seconds: number;

  model: {
    model_id: string;
    loaded: boolean;              // 模型是否已加载
    load_progress: number;        // 加载进度 0-1
    gpu_utilization: number;      // GPU 使用率 0-1
    gpu_memory_used_gb: number;   // GPU 显存占用
    gpu_memory_total_gb: number;  // GPU 显存总量
  };

  services: {
    // 依赖服务健康（如 redis / postgresql）
    [name: string]: {
      status: "healthy" | "unreachable" | "configured";
      latency_ms?: number;
    };
  };

  system: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
  };

  metrics: {
    active_requests: number;
    total_requests: number;
    cache_hit_rate: number;
    error_rate_5m: number;        // 近 5 分钟错误率
  };
}
```

### 3.6 端点 12 · `/metrics`（Prometheus 指标）

**必须暴露的指标**：

```prometheus
# ============ 请求指标 ============
yyc3_model_requests_total{model_id, endpoint, status}        counter
yyc3_model_request_duration_seconds{model_id, endpoint}      histogram
yyc3_model_tokens_total{model_id, type}                      counter   # type: input/output

# ============ SSE 指标 ============
yyc3_model_sse_ttft_seconds{model_id}                        histogram # TTFT
yyc3_model_sse_active_streams{model_id}                      gauge
yyc3_model_sse_tokens_per_second{model_id}                   gauge

# ============ 健康指标 ============
yyc3_model_health_status{model_id}                           gauge     # 1=healthy, 0.5=degraded, 0=unreachable
yyc3_model_uptime_seconds{model_id}                          counter
yyc3_model_load_progress{model_id}                           gauge     # 0-1

# ============ 资源指标 ============
yyc3_model_gpu_utilization{model_id, gpu}                    gauge     # 0-1
yyc3_model_gpu_memory_used_gb{model_id, gpu}                 gauge
yyc3_model_gpu_memory_total_gb{model_id, gpu}                gauge

# ============ 错误指标 ============
yyc3_model_errors_total{model_id, error_type}                counter   # error_type: timeout/validation/quota/internal
```

### 3.7 端点 3-6 · 能力代理端点

按需实现。若模型服务声明了某项能力，则必须实现对应端点。

**`/v1/embeddings`**（文本嵌入）：

```typescript
// Request
interface EmbeddingRequest {
  model: string;
  input: string | string[];
  encoding_format?: "float" | "base64";
  dimensions?: number;             // 可选，目标维度
}

// Response
interface EmbeddingResponse {
  object: "list";
  data: { object: "embedding"; index: number; embedding: number[] }[];
  model: string;
  usage: { prompt_tokens: number; total_tokens: number };
}
```

**`/v1/rerank`**（重排序）：

```typescript
// Request
interface RerankRequest {
  model: string;
  query: string;
  documents: string[];
  top_n?: number;
  return_documents?: boolean;
}

// Response
interface RerankResponse {
  id: string;
  results: { index: number; relevance_score: number; document?: { text: string } }[];
  usage: { total_tokens: number };
}
```

**`/v1/audio/transcriptions`**（ASR）：

```typescript
// Request: multipart/form-data
//   file: audio file
//   model: string
//   language?: string
//   response_format?: "json" | "text" | "srt" | "vtt"

// Response
interface TranscriptionResponse {
  text: string;
  language?: string;
  duration?: number;
  segments?: { id: number; start: number; end: number; text: string }[];
}
```

**`/v1/ocr`**（OCR，YYC³ 扩展）：

```typescript
// Request: multipart/form-data
//   image: image file
//   model: string
//   language?: string
//   output_format?: "text" | "json" | "markdown"

// Response
interface OCRResponse {
  text: string;
  blocks?: { type: "text" | "table" | "figure"; content: string; bbox: [number, number, number, number] }[];
  language?: string;
  confidence?: number;
}
```

### 3.8 SSE 协议契约（对齐 v5.1 §1.3）

**传输格式**：

```
data: {OpenAI chunk}\n\n
data: {OpenAI chunk}\n\n
...
data: [DONE]\n\n
```

**首 chunk 扩展字段**：

```typescript
interface FirstChunkExtras {
  _yyc3_upstream: string;          // 服务上游名
  _yyc3_request_id: string;        // 请求级追踪 ID
  _yyc3_model_version: string;     // 模型版本
}
```

**错误 chunk**：

```
data: {"error":{"message":"...","type":"stream_error","code":"UPSTREAM_TIMEOUT"}}\n\n
data: [DONE]\n\n
```

**响应头**：

```
X-YYC3-Upstream: <upstream_name>
X-YYC3-Degraded: true              # 若走降级路径
X-YYC3-Model-Version: <version>
X-YYC3-Request-Id: <uuid>
```

### 3.9 接口合规检查清单

模型服务上线前，必须通过以下检查：

```
□ /v1/models 返回 OpenAI 兼容格式
□ /v1/chat/completions 支持同步 + SSE 流式
□ /healthz 响应 < 100ms
□ /health 返回完整健康信息
□ /v1/model/metadata 返回完整元数据（所有必填字段）
□ /v1/model/capabilities 声明所有实现的能力
□ /v1/model/manifest 返回版本清单（含权重哈希）
□ /metrics 暴露所有必需指标
□ SSE 首 chunk 含 _yyc3_upstream / _yyc3_request_id
□ 响应头含 X-YYC3-Upstream / X-YYC3-Request-Id
□ 错误响应符合 APIError 结构（detail.error / message / status_code）
□ 所有端点支持 X-YYC3-Registry-Token 认证（仅限 registry 相关）
```

---

## 第四部分 · 模型注册中心（Registry）

### 4.1 架构概览

```
                    ┌─────────────────────────────────────┐
                    │   Model Registry（注册中心）         │
                    │   🧠 元启·天枢 主控                   │
                    ├─────────────────────────────────────┤
                    │  ┌─────────────┐  ┌──────────────┐  │
                    │  │ Metadata DB │  │ Manifest     │  │
                    │  │ (PostgreSQL)│  │ Store (S3)   │  │
                    │  └─────────────┘  └──────────────┘  │
                    │  ┌─────────────┐  ┌──────────────┐  │
                    │  │ Event Bus   │  │ Versioning   │  │
                    │  │ (Redis)     │  │ (Git-like)   │  │
                    │  └─────────────┘  └──────────────┘  │
                    └──────────┬──────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ 网关:8000    │ │ 上游池       │ │ 运维工具     │
      │ (自动发现)   │ │ (vLLM/NIM)   │ │ (CLI/UI)    │
      └──────────────┘ └──────────────┘ └──────────────┘
```

### 4.2 注册数据模型

**PostgreSQL Schema**：

```sql
-- ============================================================
-- YYC³ AI Family · Model Registry Schema
-- @Owner : 🧠 元启·天枢 · 🎯 千里·伯乐
-- ============================================================

-- 模型主表（当前状态）
CREATE TABLE model_registry (
  model_id           VARCHAR(100) PRIMARY KEY,
  display_name       VARCHAR(200) NOT NULL,
  version            VARCHAR(50) NOT NULL,
  backend            VARCHAR(20) NOT NULL,
  capabilities       JSONB NOT NULL DEFAULT '[]',
  enabled            BOOLEAN NOT NULL DEFAULT TRUE,

  description        TEXT,
  family_member      VARCHAR(20),
  domain             VARCHAR(50),
  tags               TEXT[] DEFAULT '{}',

  max_tokens         INTEGER NOT NULL DEFAULT 4096,
  context_window     INTEGER NOT NULL DEFAULT 8192,
  temperature_default NUMERIC(3,2) DEFAULT 0.7,
  top_p_default      NUMERIC(3,2) DEFAULT 0.9,

  cost_per_1k_tokens NUMERIC(10,6) DEFAULT 0,
  avg_latency_ms     NUMERIC(10,2) DEFAULT 0,
  throughput_tps     NUMERIC(10,2) DEFAULT 0,
  max_concurrency    INTEGER DEFAULT 1,

  node_id            VARCHAR(50) NOT NULL,
  node_role          VARCHAR(20) NOT NULL DEFAULT 'primary',
  base_url           VARCHAR(500) NOT NULL,
  fallback_url       VARCHAR(500),
  weights_path       VARCHAR(500),
  weights_size_gb    NUMERIC(10,2),
  quantization       VARCHAR(20),

  health_status      VARCHAR(20) DEFAULT 'unknown',
  last_heartbeat_at  TIMESTAMP,
  breaker_state      VARCHAR(20) DEFAULT 'closed',

  manifest_hash      VARCHAR(64),
  owner              VARCHAR(200),
  registered_at      TIMESTAMP DEFAULT NOW(),
  updated_at         TIMESTAMP DEFAULT NOW(),

  CONSTRAINT chk_backend CHECK (backend IN ('vllm','nim','ollama','openai','zhipu','deepseek','upstream')),
  CONSTRAINT chk_node_role CHECK (node_role IN ('primary','secondary','fallback')),
  CONSTRAINT chk_health CHECK (health_status IN ('healthy','degraded','unreachable','unknown')),
  CONSTRAINT chk_breaker CHECK (breaker_state IN ('closed','open','half_open'))
);

CREATE INDEX idx_registry_enabled ON model_registry(enabled) WHERE enabled = TRUE;
CREATE INDEX idx_registry_capabilities ON model_registry USING GIN(capabilities);
CREATE INDEX idx_registry_node ON model_registry(node_id);
CREATE INDEX idx_registry_health ON model_registry(health_status);

-- 版本历史表（不可变）
CREATE TABLE model_versions (
  id                 SERIAL PRIMARY KEY,
  model_id           VARCHAR(100) NOT NULL REFERENCES model_registry(model_id),
  version            VARCHAR(50) NOT NULL,
  manifest           JSONB NOT NULL,
  manifest_hash      VARCHAR(64) NOT NULL,
  action             VARCHAR(20) NOT NULL,  -- register/update/rollback
  actor              VARCHAR(200) NOT NULL,
  reason             TEXT,
  created_at         TIMESTAMP DEFAULT NOW(),

  CONSTRAINT chk_action CHECK (action IN ('register','update','rollback','deprecate')),
  UNIQUE (model_id, version)
);

CREATE INDEX idx_versions_model ON model_versions(model_id, created_at DESC);

-- 心跳表（用于 TTL 检测）
CREATE TABLE model_heartbeats (
  model_id           VARCHAR(100) PRIMARY KEY REFERENCES model_registry(model_id),
  last_beat_at       TIMESTAMP NOT NULL DEFAULT NOW(),
  consecutive_miss   INTEGER DEFAULT 0,
  metadata           JSONB
);

-- 事件表（供网关 Watch）
CREATE TABLE model_events (
  id                 BIGSERIAL PRIMARY KEY,
  event_type         VARCHAR(30) NOT NULL,  -- registered/updated/deprecated/deregistered
  model_id           VARCHAR(100) NOT NULL,
  version            VARCHAR(50),
  payload            JSONB NOT NULL,
  created_at         TIMESTAMP DEFAULT NOW(),

  CONSTRAINT chk_event_type CHECK (event_type IN ('registered','updated','deprecated','deregistered','breaker_open','breaker_close'))
);

CREATE INDEX idx_events_created ON model_events(created_at DESC);
CREATE INDEX idx_events_model ON model_events(model_id, created_at DESC);

-- 审计日志表（保留 365 天）
CREATE TABLE model_audit_log (
  id                 BIGSERIAL PRIMARY KEY,
  actor              VARCHAR(200) NOT NULL,
  action             VARCHAR(50) NOT NULL,
  model_id           VARCHAR(100),
  before_state       JSONB,
  after_state        JSONB,
  ip_address         INET,
  user_agent         TEXT,
  created_at         TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_actor ON model_audit_log(actor, created_at DESC);
CREATE INDEX idx_audit_model ON model_audit_log(model_id, created_at DESC);

-- 清理策略：审计日志保留 365 天
-- SELECT cron.schedule('cleanup-audit-log', '0 3 * * *',
--   $$DELETE FROM model_audit_log WHERE created_at < NOW() - INTERVAL '365 days'$$);
```

### 4.3 Registry API 端点

| # | 端点 | 方法 | 权限 | 说明 |
| :-: | --- | :-: | --- | --- |
| R-01 | `/registry/v1/models` | GET | 只读 | 列出所有模型 |
| R-02 | `/registry/v1/models/{id}` | GET | 只读 | 获取单个模型 |
| R-03 | `/registry/v1/models` | POST | 🎯/🧠 | 注册模型 |
| R-04 | `/registry/v1/models/{id}` | PATCH | 🎯/🧠 | 更新模型元数据 |
| R-05 | `/registry/v1/models/{id}` | DELETE | 🎯/🧠 | 注销模型 |
| R-06 | `/registry/v1/models/{id}/versions` | GET | 只读 | 版本历史 |
| R-07 | `/registry/v1/models/{id}/rollback` | POST | 🧠/📚 | 回滚到指定版本 |
| R-08 | `/registry/v1/models/{id}/heartbeat` | POST | 模型服务 | 心跳上报 |
| R-09 | `/registry/v1/models/{id}/health` | GET | 只读 | 实时健康 |
| R-10 | `/registry/v1/events` | GET | 只读 | 事件流（SSE） |
| R-11 | `/registry/v1/manifests/{hash}` | GET | 只读 | 获取 Manifest |
| R-12 | `/registry/v1/audit` | GET | 只读 | 审计日志 |

### 4.4 注册流程（Standard Operation Procedure）

```
┌─────────────────────────────────────────────────────────────────┐
│  新模型接入 · 标准流程（SOP-01）                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1 · 模型服务就绪（负责人：🎯 千里·伯乐）                    │
│    □ 权重部署到目标节点（路径按 §5.2 规范）                       │
│    □ 启动 vLLM/NIM 服务，加载权重                                │
│    □ 本地验证 /v1/models /healthz /health                        │
│                                                                 │
│  Step 2 · 实现契约端点（负责人：🤔 语枢·万物）                    │
│    □ 实现 §3 所有必需端点                                        │
│    □ 通过 §3.9 合规检查清单                                      │
│    □ 生成 Manifest（§3.4）                                       │
│                                                                 │
│  Step 3 · 注册模型（负责人：🎯 千里·伯乐）                        │
│    □ POST /registry/v1/models                                    │
│    □ Registry 校验元数据完整性                                   │
│    □ Registry 写入 model_registry + model_versions + 事件        │
│    □ 返回注册结果 + manifest_hash                                │
│                                                                 │
│  Step 4 · 灰度验证（负责人：🧠 元启·天枢 + 📚 格物·宗师）         │
│    □ 创建影子流量规则（Shadow Mode）                             │
│    □ 观察 30 分钟影子指标                                        │
│    □ 通过质量门禁（§8.2）                                        │
│                                                                 │
│  Step 5 · 金丝雀发布（负责人：🧠 元启·天枢）                      │
│    □ 创建金丝雀规则（5% 流量）                                   │
│    □ 观察 1 小时                                                 │
│    □ 逐步扩量 10% → 30% → 50% → 100%                            │
│                                                                 │
│  Step 6 · 全量上线（负责人：🧠 元启·天枢）                        │
│    □ 移除影子/金丝雀规则                                         │
│    □ 更新 Registry 状态为 "primary"                              │
│    □ 通知运维 + 更新监控面板                                     │
│                                                                 │
│  Step 7 · 归档与复盘（负责人：📚 格物·宗师）                      │
│    □ 记录审计日志                                                │
│    □ 更新模型资产清单（YYC3-Models-资产详情.md）                  │
│    □ 复盘会（如涉及新类型模型）                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 注册 API 示例

**R-03 · 注册模型**：

```http
POST /registry/v1/models HTTP/1.1
Host: api.0379.world
X-API-Key: <admin-api-key>
Content-Type: application/json

{
  "model_id": "qwen3.8-flash-next",
  "display_name": "Qwen 3.8 Flash Next",
  "version": "v3.8.0",
  "backend": "vllm",
  "capabilities": ["chat", "tool_use", "json_mode"],
  "enabled": true,
  "description": "Qwen 3.8 Flash Next 下一代旗舰",
  "family_member": "wanyu",
  "domain": "推理对话域",
  "max_tokens": 8192,
  "context_window": 131072,
  "temperature_default": 0.7,
  "top_p_default": 0.9,
  "cost_per_1k_tokens": 0.0003,
  "avg_latency_ms": 380,
  "throughput_tps": 92,
  "max_concurrency": 48,
  "node_id": "yyc3-101",
  "node_role": "primary",
  "base_url": "http://yyc3-101.local:8002/v1",
  "fallback_url": "http://yyc3-102.local:8002/v1",
  "weights_path": "/home/yyc3/yyc3-101-projects/models/Qwen3.8-Flash-Next",
  "weights_size_gb": 360,
  "quantization": "bf16",
  "manifest_hash": "<由服务端计算并返回>",
  "owner": "ops@0379.email",
  "tags": ["旗舰", "Qwen系"]
}
```

**响应**：

```json
{
  "status": "registered",
  "model_id": "qwen3.8-flash-next",
  "version": "v3.8.0",
  "manifest_hash": "b4e6d8f0a2c4e6b8d0f2a4c6e8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6",
  "registered_at": "2026-09-27T10:30:00Z",
  "event_id": 12345,
  "next_steps": [
    "1. 部署影子流量规则：POST /registry/v1/models/qwen3.8-flash-next/shadow",
    "2. 观察 30 分钟后再进入金丝雀阶段",
    "3. 完整 SOP 见 §4.4"
  ]
}
```

**R-07 · 回滚**：

```http
POST /registry/v1/models/deepseek-v4-flash/rollback HTTP/1.1
Host: api.0379.world
X-API-Key: <admin-api-key>
Content-Type: application/json

{
  "target_version": "v3.9.0",
  "reason": "v4.0.0 长文本场景 P95 延迟退化 30%",
  "actor": "ops@0379.email",
  "notify": ["slack:#yyc3-family-alerts"]
}
```

### 4.6 心跳与 TTL

**心跳上报**（模型服务定时调用，默认 30s）：

```http
POST /registry/v1/models/{model_id}/heartbeat HTTP/1.1
X-YYC3-Registry-Token: <registry-token>

{
  "model_id": "deepseek-v4-flash",
  "status": "healthy",
  "uptime_seconds": 86400,
  "active_requests": 12,
  "gpu_utilization": 0.72,
  "timestamp": "2026-09-27T10:30:00Z"
}
```

**TTL 规则**：

```
连续 3 次心跳丢失（90s） → Registry 标记 "degraded"
连续 6 次心跳丢失（180s） → Registry 标记 "unreachable"
连续 10 次心跳丢失（300s） → Registry 自动从上游池摘除
恢复心跳后 → 自动重新纳入（先半开探测 30s）
```

---

## 第五部分 · 动态注册与发现

### 5.1 从静态 env 到动态 Registry 演进

**当前（v2.3.0）**：

```bash
# core/config/.env
OPENAI_COMPATIBLE_UPSTREAMS='[
  {"name":"dsv4-head","base_url":"http://yyc3-101.local:8001/v1","models":["deepseek-v4-flash"],"priority":1},
  {"name":"dsv4-worker","base_url":"http://yyc3-102.local:8001/v1","models":["deepseek-v4-flash"],"priority":2},
  {"name":"asr-n2","base_url":"http://yyc3-102.local:8004/v1","models":["qwen3-asr-1.7b"],"priority":1},
  {"name":"ocr-n2","base_url":"http://yyc3-102.local:8005/v1","models":["minicpm-v-4.6"],"priority":1}
]'
```

**目标（v3.0.0 演进后）**：

```bash
# 双通道共存（过渡期 6 个月）
REGISTRY_ENABLED=true
REGISTRY_ENDPOINT=http://registry.yyc3.local:8500
REGISTRY_FALLBACK_TO_ENV=true       # Registry 不可用时回退到 env

# env 通道保留，但标记为 deprecated（日志警告）
OPENAI_COMPATIBLE_UPSTREAMS='[...]'  # 保留为 fallback
```

**演进三阶段**：

```
Phase A（当前 → 3 个月）：双通道
  Registry 与 env 并存，Registry 优先，env fallback
  所有新模型只走 Registry

Phase B（3 → 6 个月）：Registry 主导
  env 仅保留 1-2 个紧急 fallback
  监控面板标注"env 通道使用率"

Phase C（6 个月后）：纯 Registry
  移除 env 通道
  Registry 成为唯一真源
```

### 5.2 网关侧发现协议

**网关启动流程**：

```
1. 读取配置
   ├─ REGISTRY_ENABLED 是否为 true
   └─ REGISTRY_FALLBACK_TO_ENV 是否为 true

2. 尝试连接 Registry
   ├─ 成功 → 调用 GET /registry/v1/models 拉取全量
   │         订阅 GET /registry/v1/events (SSE) 持续接收事件
   └─ 失败 → 检查 fallback
             ├─ REGISTRY_FALLBACK_TO_ENV=true → 读取 OPENAI_COMPATIBLE_UPSTREAMS
             └─ 否则 → 启动失败（fail-fast）

3. 构建上游池
   ├─ 按 capabilities 分组（chat 池 / embedding 池 / rerank 池 / asr 池 / ocr 池）
   ├─ 按 node_role 分层（primary / secondary / fallback）
   └─ 按 priority + weight 计算路由权重

4. 启动健康探测
   ├─ 每 30s 调用每个上游的 /healthz
   └─ 每次失败 → 标记 degraded → 累计 3 次 → 摘除

5. 启动事件监听
   ├─ SSE 长连接 → GET /registry/v1/events
   ├─ 事件类型：registered/updated/deprecated/deregistered
   └─ 收到事件 → 增量更新上游池（无需重启）
```

**事件流示例**（`GET /registry/v1/events`）：

```http
GET /registry/v1/events?since=2026-09-27T10:00:00Z HTTP/1.1
Accept: text/event-stream

data: {"event_type":"registered","model_id":"qwen3.8-flash-next","version":"v3.8.0","payload":{...},"ts":"2026-09-27T10:30:00Z"}

data: {"event_type":"updated","model_id":"deepseek-v4-flash","version":"v4.0.1","payload":{"avg_latency_ms":450},"ts":"2026-09-27T10:35:00Z"}

data: {"event_type":"breaker_open","model_id":"zhipu-glm-5.3-flash","payload":{"reason":"连续3次失败"},"ts":"2026-09-27T10:40:00Z"}
```

### 5.3 自动发现机制（Pull + Push 双通道）

```
┌─────────────────────────────────────────────────────────────────┐
│  双通道发现机制                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Pull 通道（兜底，每 5 分钟）                                    │
│  ┌────────────┐  GET /registry/v1/models                        │
│  │  网关      │ ──────────────────────────────► Registry         │
│  │  (每 5min) │ ◄────────────────────────────── 全量列表          │
│  └────────────┘                                                 │
│                                                                 │
│  Push 通道（实时，SSE 长连接）                                   │
│  ┌────────────┐  GET /registry/v1/events (SSE)                  │
│  │  网关      │ ──────────────────────────────► Registry         │
│  │            │ ◄────────────────────────────── 增量事件流        │
│  └────────────┘                                                 │
│                                                                 │
│  合并策略：Push 优先，Pull 兜底（连接断开时自动降级到 Pull）       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 网关配置示例

```yaml
# core/config/gateway.yaml
# ============================================================
# YYC³ AI Family · 网关配置（v3.0.0 目标）
# @Owner : 🧭 言启·千行 · 🧠 元启·天枢
# ============================================================
gateway:
  registry:
    enabled: true
    endpoint: "http://registry.yyc3.local:8500"
    timeout_seconds: 5
    pull_interval_seconds: 300
    push_enabled: true
    push_reconnect_max_seconds: 60
    fallback_to_env: true

  upstream_pool:
    # 按能力分组（自动从 Registry 构建）
    chat:
      health_check_interval_seconds: 30
      health_check_timeout_seconds: 3
      breaker:
        failure_threshold: 3
        open_duration_seconds: 30
        half_open_max_calls: 3
    embedding:
      health_check_interval_seconds: 60
    rerank:
      health_check_interval_seconds: 60

  routing:
    strategy: ADAPTIVE          # ADAPTIVE / WEIGHTED_LATENCY / LEAST_CONNECTIONS / RANDOM / ROUND_ROBIN
    ewma_alpha: 0.3
    weight_update_interval_seconds: 10
    degraded_threshold_error_rate: 0.15
```

---

## 第六部分 · 零停机模型热切换

### 6.1 切换模式总览

| 模式 | 适用场景 | 流量切换 | 可观测性 | 回滚时间 |
| --- | --- | --- | --- | --- |
| **Shadow** | 新模型初验证 | 0%（仅复制） | 影子指标对比 | 立即（不占流量） |
| **Canary** | 灰度发布 | 5% → 100% 渐进 | 金丝雀指标 | ≤ 30s |
| **Blue-Green** | 重大版本升级 | 100% 秒切 | 蓝绿指标对比 | ≤ 10s |
| **Weighted** | 多模型负载均衡 | 按权重分流 | 全量指标 | 立即 |

### 6.2 Shadow 模式（影子流量）

**用途**：生产流量复制到新模型，验证但不影响响应。

**配置**：

```yaml
# /registry/v1/models/{model_id}/shadow
model_id: "qwen3.8-flash-next"
shadow:
  enabled: true
  primary: "deepseek-v4-flash"     # 生产主模型
  shadow: "qwen3.8-flash-next"     # 影子模型
  sample_rate: 0.1                 # 10% 流量复制
  compare_metrics:
    - latency_p95
    - error_rate
    - output_length
    - output_hash
  auto_promote:
    enabled: true
    conditions:
      - "shadow.latency_p95 < primary.latency_p95 * 1.1"
      - "shadow.error_rate < 0.01"
      - "shadow.output_match_rate > 0.85"
    observe_duration_minutes: 30
```

**Shadow 状态机**：

```
          ┌──────────┐
          │ inactive │
          └────┬─────┘
               │ enable
               ▼
          ┌──────────┐
     ┌───►│ observing│◄───┐
     │    └────┬─────┘    │
     │         │          │
     │ 30min   │ 质量不达标 │ 达标
     │ 未达标   ▼          │
     │    ┌──────────┐    │
     └────│ rejected │    │
          └──────────┘    │
                          ▼
                    ┌──────────┐
                    │ ready    │
                    │ for      │
                    │ canary   │
                    └──────────┘
```

### 6.3 Canary 模式（金丝雀发布）

**用途**：小流量验证 → 逐步扩量 → 全量。

**配置**：

```yaml
# /registry/v1/models/{model_id}/canary
model_id: "qwen3.8-flash-next"
canary:
  enabled: true
  baseline: "deepseek-v4-flash"
  stages:
    - { weight: 5,   duration_minutes: 30 }
    - { weight: 10,  duration_minutes: 30 }
    - { weight: 30,  duration_minutes: 60 }
    - { weight: 50,  duration_minutes: 60 }
    - { weight: 100, duration_minutes: 0 }
  auto_rollback:
    conditions:
      - "canary.error_rate > 0.02"
      - "canary.latency_p95 > baseline.latency_p95 * 1.3"
      - "canary.ttft_p95 > 3000"
    check_interval_seconds: 60
  on_success:
    promote_to_primary: true
    notify: ["slack:#yyc3-family-alerts"]
  on_failure:
    rollback_to: "baseline"
    notify: ["slack:#yyc3-family-critical", "email:oncall@0379.email"]
```

**Canary 状态机**：

```
          ┌──────────┐
          │  idle    │
          └────┬─────┘
               │ start canary
               ▼
          ┌──────────────┐
     ┌───►│ stage_5pct   │
     │    └──────┬───────┘
     │           │ 30min OK
     │           ▼
     │    ┌──────────────┐
     │    │ stage_10pct  │
     │    └──────┬───────┘
     │           │ ...
     │           ▼
     │    ┌──────────────┐
     │    │ stage_100pct │
     │    └──────┬───────┘
     │           │
     │      OK   │   FAIL
     │    ┌──────┴───────┐
     │    ▼              ▼
     │ ┌────────┐  ┌──────────┐
     └─│promoted│  │ rollback │
       └────────┘  └──────────┘
       (任何阶段失败均回滚)
```

### 6.4 Blue-Green 模式（蓝绿切换）

**用途**：重大版本升级，秒级切换。

**流程**：

```
Step 1 · 准备 Green（新版本）
  - 新模型部署到独立上游组（green-*）
  - 独立健康探测
  - 不影响 Blue（生产）

Step 2 · 预检
  - Green 全端点健康
  - Green 契约合规（§3.9）
  - Green 性能达标

Step 3 · 秒切（≤ 10s）
  - 网关路由表原子更新
  - Blue → Green
  - 若失败 → 立即回退

Step 4 · 观察期（30min）
  - 监控 Green 指标
  - 保留 Blue 热备（可秒切回）

Step 5 · 收敛
  - Green 稳定 → 停止 Blue（保留 24h 权重）
  - 或异常 → 秒切回 Blue
```

**切换脚本**（`scripts/blue-green-switch.sh`）：

```bash
#!/bin/bash
# ============================================================
# YYC³ AI Family · 蓝绿切换脚本
# @Owner : 🧠 元启·天枢
# ============================================================
set -euo pipefail

MODEL_ID="${1:?用法: $0 <model_id> <target_version>}"
TARGET_VERSION="${2:?}"
REGISTRY="http://registry.yyc3.local:8500"
API_KEY="${YYC3_ADMIN_KEY:?需要 YYC3_ADMIN_KEY}"

echo "🌹 蓝绿切换: ${MODEL_ID} → ${TARGET_VERSION}"

# 1. 预检
echo "▶ 预检 Green..."
curl -sf "${REGISTRY}/registry/v1/models/${MODEL_ID}/versions/${TARGET_VERSION}/health" \
  -H "X-API-Key: ${API_KEY}" | jq -e '.status == "healthy"' > /dev/null

# 2. 记录当前 Blue（用于回滚）
BLUE=$(curl -sf "${REGISTRY}/registry/v1/models/${MODEL_ID}" \
  -H "X-API-Key: ${API_KEY}" | jq -r '.version')
echo "   当前 Blue: ${BLUE}"

# 3. 执行切换
echo "▶ 执行切换..."
curl -sf -X POST "${REGISTRY}/registry/v1/models/${MODEL_ID}/switch" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"target_version\": \"${TARGET_VERSION}\",
    \"mode\": \"blue-green\",
    \"atomic\": true,
    \"rollback_to\": \"${BLUE}\"
  }" | jq

# 4. 验证
echo "▶ 验证切换结果..."
sleep 5
NEW=$(curl -sf "${REGISTRY}/registry/v1/models/${MODEL_ID}" \
  -H "X-API-Key: ${API_KEY}" | jq -r '.version')
if [ "${NEW}" != "${TARGET_VERSION}" ]; then
  echo "🚫 切换失败，立即回滚到 ${BLUE}"
  curl -sf -X POST "${REGISTRY}/registry/v1/models/${MODEL_ID}/rollback" \
    -H "X-API-Key: ${API_KEY}" \
    -d "{\"target_version\":\"${BLUE}\"}"
  exit 1
fi

echo "✅ 切换成功"
echo "   Blue: ${BLUE} → Green: ${TARGET_VERSION}"
echo "   回滚命令: POST /registry/v1/models/${MODEL_ID}/rollback  target_version=${BLUE}"
```

### 6.5 切换状态机（总览）

```
                    ┌──────────────┐
                    │    stable    │
                    │  (当前生产)   │
                    └──────┬───────┘
                           │
                           │ 触发切换
                           ▼
                    ┌──────────────┐
                    │  preparing   │  (预检 Green)
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
         ┌────────┐  ┌─────────┐  ┌──────────┐
         │ shadow │  │ canary  │  │ blue-green│
         └────┬───┘  └────┬────┘  └─────┬────┘
              │           │              │
              └───────────┼──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  switching   │
                   └──────┬───────┘
                          │
              ┌───────────┴────────────┐
              │                        │
              ▼                        ▼
       ┌──────────────┐         ┌──────────────┐
       │  observing   │         │  rolling_    │
       │              │         │   back       │
       └──────┬───────┘         └──────┬───────┘
              │                        │
       ┌──────┴────────┐               │
       │               │               │
       ▼               ▼               ▼
  ┌─────────┐  ┌───────────┐    ┌──────────┐
  │ promoted│  │ rollback  │    │  stable  │
  │ (全量)  │  │           │    │  (回滚)  │
  └─────────┘  └───────────┘    └──────────┘
```

### 6.6 回滚触发条件（自动）

```yaml
auto_rollback:
  # 硬条件（立即回滚）
  hard_conditions:
    - "error_rate > 0.10 within 5min"
    - "p95_latency > baseline_p95 * 2.0 within 5min"
    - "ttft_p95 > 5000ms within 5min"
    - "upstream_unreachable_rate > 0.30 within 5min"
    - "consecutive_5xx > 50 within 5min"

  # 软条件（告警 + 人工确认）
  soft_conditions:
    - "error_rate > 0.02 within 15min"
    - "p95_latency > baseline_p95 * 1.3 within 15min"
    - "output_quality_score < 0.8 within 30min"  # 需外部评分
    - "cost_per_request > baseline * 1.5 within 60min"

  # 观察窗口
  observation_window_minutes: 60

  # 回滚动作
  action:
    - "switch_traffic_to: baseline"
    - "notify: [slack:#yyc3-family-critical]"
    - "create_incident: true"
    - "record_audit: true"
```

---

## 第七部分 · 自动配置同步

### 7.1 同步内容矩阵

| 内容类型 | 同步方向 | 触发方式 | 延迟要求 |
| --- | :-: | --- | :-: |
| 模型元数据 | Registry → 网关 | 事件推送 | ≤ 5s |
| 上游池 | Registry → 网关 | 事件推送 + Pull 兜底 | ≤ 5s |
| 模型参数（temperature 等） | Registry → 前端 | 事件推送 | ≤ 30s |
| 性能指标（延迟/错误率） | 模型服务 → Registry | 心跳 + Prometheus | ≤ 60s |
| 熔断状态 | 网关 → Registry | 事件回写 | ≤ 10s |
| Manifest | 模型服务 → Registry → 存储 | 主动上报 | 同步 |

### 7.2 三通道同步

```
┌─────────────────────────────────────────────────────────────────┐
│  同步三通道                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  通道 1 · Webhook（推荐，实时）                                 │
│  ┌────────────┐  POST /webhook  ┌──────────────┐                │
│  │  Registry  │ ───────────────►│  网关        │                │
│  │            │                 │  (接收配置)  │                │
│  └────────────┘                 └──────────────┘                │
│  延迟: ≤ 1s                                                     │
│  可靠性: 中（需重试机制）                                        │
│                                                                 │
│  通道 2 · SSE（事件流，次实时）                                  │
│  ┌────────────┐  GET /events    ┌──────────────┐                │
│  │  网关      │ ◄───────────────│  Registry    │                │
│  │            │  (SSE 长连接)   │              │                │
│  └────────────┘                 └──────────────┘                │
│  延迟: ≤ 5s                                                     │
│  可靠性: 高（自动重连）                                          │
│                                                                 │
│  通道 3 · Pull（兜底，定时）                                     │
│  ┌────────────┐  GET /models    ┌──────────────┐                │
│  │  网关      │ ───────────────►│  Registry    │                │
│  │  (每 5min) │                 │              │                │
│  └────────────┘                 └──────────────┘                │
│  延迟: ≤ 5min                                                   │
│  可靠性: 最高（无状态）                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Webhook 重试机制

```yaml
# Registry Webhook 配置
webhook:
  endpoints:
    - url: "http://gateway.yyc3.local:8000/webhook/registry"
      events: ["registered", "updated", "deregistered", "breaker_open", "breaker_close"]
      retry:
        max_attempts: 5
        backoff: exponential
        initial_delay_ms: 1000
        max_delay_ms: 30000
        jitter: true
      timeout_seconds: 5
      headers:
        X-YYC3-Webhook-Signature: "${hmac_sha256(body, secret)}"
```

### 7.4 冲突解决策略

| 冲突类型 | 解决策略 | 说明 |
| --- | --- | --- |
| Registry vs env | **Registry 优先** | env 仅 fallback |
| 元数据字段冲突 | **最新时间戳优先** | 比较 updated_at |
| Manifest 冲突 | **高版本优先** | 语义化版本比较 |
| 熔断状态冲突 | **网关权威** | 网关是熔断的唯一真源 |
| 性能指标冲突 | **Prometheus 权威** | 实测数据 > 声明数据 |

### 7.5 一致性校验

**每 5 分钟自动校验**：

```typescript
// 伪代码
async function reconcile() {
  const registryModels = await registry.list();
  const gatewayUpstreams = await gateway.getUpstreams();

  const diff = {
    inRegistryOnly: registryModels.filter(m => !gatewayUpstreams.has(m.model_id)),
    inGatewayOnly: gatewayUpstreams.filter(u => !registryModels.has(u.model_id)),
    fieldMismatch: [],
  };

  for (const m of registryModels) {
    const g = gatewayUpstreams.get(m.model_id);
    if (!g) continue;
    if (m.version !== g.version) diff.fieldMismatch.push({ model: m.model_id, field: "version" });
    if (m.avg_latency_ms !== g.avg_latency_ms) diff.fieldMismatch.push({ model: m.model_id, field: "avg_latency_ms" });
  }

  if (diff.inRegistryOnly.length > 0) {
    // 网关缺少：触发添加
    await gateway.addUpstreams(diff.inRegistryOnly);
  }
  if (diff.inGatewayOnly.length > 0) {
    // 网关多余：触发移除（谨慎，需人工确认）
    await alert("🧭 言启·千行 · 网关存在未知上游", diff.inGatewayOnly);
  }
  if (diff.fieldMismatch.length > 0) {
    // 字段不一致：以 Registry 为准
    await gateway.syncFromRegistry(diff.fieldMismatch);
  }
}
```

---

## 第八部分 · 版本控制与回滚

### 8.1 版本命名规范

```
格式: <major>.<minor>.<patch>[-<prerelease>][+<build>]

示例:
  v4.0.0          # 主版本
  v4.0.1          # 补丁版本
  v4.1.0-rc1      # 候选版本
  v4.1.0+20260927 # 构建元数据

约定:
  major: 不兼容变更（权重格式 / 端点契约）
  minor: 向后兼容的新功能（新能力 / 新参数）
  patch: 向后兼容的修复（bug fix / 性能优化）
  prerelease: alpha / beta / rc
  build: 构建日期 / git hash
```

### 8.2 质量门禁（Promotion Gate）

任何版本进入下一阶段前，必须通过以下门禁：

```yaml
# .registry/gates.yaml
gates:
  shadow_to_canary:
    - "shadow.observe_duration_minutes >= 30"
    - "shadow.error_rate < 0.01"
    - "shadow.latency_p95 < baseline.latency_p95 * 1.1"
    - "shadow.output_match_rate > 0.85"
    - "shadow.cost_per_request < baseline.cost_per_request * 1.2"

  canary_to_full:
    - "canary.total_requests >= 1000"
    - "canary.error_rate < 0.005"
    - "canary.latency_p95 < baseline.latency_p95 * 1.15"
    - "canary.ttft_p95 < 3000"
    - "canary.uptime >= 0.999"

  full_rollback_conditions:
    - "production.error_rate > 0.02 within 30min"
    - "production.latency_p95 > baseline * 1.5 within 30min"
    - "production.incident_severity >= P2 within 60min"
```

### 8.3 版本清单示例

```json
{
  "manifest_version": "1.0",
  "model_id": "deepseek-v4-flash",
  "version": "v4.0.1",
  "weights": {
    "path": "/home/yyc3/yyc3-101-projects/models/DeepSeek-V4-Flash",
    "size_gb": 149,
    "file_count": 128,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "quantization": "fp8",
    "format": "safetensors"
  },
  "runtime": {
    "engine": "vllm",
    "engine_version": "vllm==0.6.3",
    "tensor_parallel": 2,
    "pipeline_parallel": 1,
    "dtype": "bfloat16",
    "kv_cache_dtype": "fp8",
    "max_model_len": 128000,
    "gpu_memory_utilization": 0.90
  },
  "dependencies": {
    "cuda": "12.4",
    "driver": "550.54.15",
    "python": "3.11",
    "system_deps": ["libnuma-dev", "libopenmpi-dev"]
  },
  "published_at": "2026-09-27T10:00:00Z",
  "published_by": "ops@0379.email",
  "build_pipeline": "ci-20260927-1030",
  "git_commit": "a1b2c3d4",
  "changelog": "修复长文本场景 P95 延迟退化问题",
  "manifest_hash": "f4e6d8f0a2c4e6b8d0f2a4c6e8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6"
}
```

### 8.4 回滚决策树

```
发现问题
  │
  ├─ 严重度 P0（服务不可用 / 数据错误）
  │   └─► 立即自动回滚（≤ 30s）
  │       └─► 通知：slack:#yyc3-family-critical + PagerDuty
  │
  ├─ 严重度 P1（性能退化 > 30% / 错误率 > 5%）
  │   └─► 5 分钟内自动回滚
  │       └─► 通知：slack:#yyc3-family-alerts
  │
  ├─ 严重度 P2（性能退化 < 30% / 错误率 < 5%）
  │   └─► 告警 + 人工判断
  │       ├─ 确认问题 → 手动回滚
  │       └─ 观察 → 记录 Issue
  │
  └─ 严重度 P3（观察性问题）
      └─► 记录 + 下次迭代修复
```

### 8.5 回滚命令速查

```bash
# ============================================================
# 🌹 YYC³ AI Family · 回滚命令速查
# ============================================================

# 1. 快速回滚（自动寻找上一稳定版本）
curl -X POST https://api.0379.world/registry/v1/models/{model_id}/rollback \
  -H "X-API-Key: ${ADMIN_KEY}" \
  -d '{"auto": true, "reason": "紧急回滚"}'

# 2. 指定版本回滚
curl -X POST https://api.0379.world/registry/v1/models/{model_id}/rollback \
  -H "X-API-Key: ${ADMIN_KEY}" \
  -d '{"target_version": "v4.0.0", "reason": "v4.0.1 性能退化"}'

# 3. 查看版本历史
curl https://api.0379.world/registry/v1/models/{model_id}/versions \
  -H "X-API-Key: ${ADMIN_KEY}" | jq

# 4. 查看当前状态
curl https://api.0379.world/registry/v1/models/{model_id} \
  -H "X-API-Key: ${ADMIN_KEY}" | jq '{version, health_status, breaker_state}'

# 5. 批量回滚（多模型同时）
for model in deepseek-v4-flash qwen3-asr-1.7b; do
  curl -X POST "https://api.0379.world/registry/v1/models/${model}/rollback" \
    -H "X-API-Key: ${ADMIN_KEY}" \
    -d '{"auto": true}'
done
```

---

## 第九部分 · 监控告警

### 9.1 关键指标矩阵

| 指标 | 类型 | 阈值 | 告警级别 | 归属家人 |
| --- | :-: | :-: | :-: | --- |
| `registry_up` | Gauge | == 0 | P0 | 🔮 预见 |
| `model_up{model_id}` | Gauge | == 0 | P0 | 🔮 预见 |
| `model_error_rate` | Gauge | > 0.05 | P1 | 🔮 预见 |
| `model_latency_p95` | Gauge | > baseline*1.3 | P1 | 🔮 预见 |
| `sse_ttft_p95` | Histogram | > 3000ms | P1 | 🤔 语枢 |
| `breaker_open_count` | Gauge | > 3 | P2 | 🧭 言启 |
| `registry_sync_lag_seconds` | Gauge | > 60 | P1 | 🧠 元启 |
| `heartbeat_missed_count` | Counter | > 3 | P1 | 🎯 千里 |
| `canary_error_rate` | Gauge | > 0.02 | P1 | 📚 格物 |
| `rollback_triggered_total` | Counter | > 0 | P0 | 🧠 元启 |

### 9.2 8 位家人视角告警规则

```yaml
# deploy/observability/prometheus/rules/registry.yaml
# ============================================================
# 🌹 YYC³ AI Family · Registry 告警规则
# ============================================================
groups:
  - name: yyc3.registry
    interval: 30s
    rules:
      # ============ 🛡️ 智云·守护 · Registry 安全 ============
      - alert: RegistryUnauthorizedAccess
        expr: rate(registry_auth_failures_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
          family: "🛡️ 智云·守护"
        annotations:
          summary: "🛡️ Registry 未授权访问"
          description: "「门禁报警，钥不实则寸步难行」"

      # ============ 🧭 言启·千行 · 路由与熔断 ============
      - alert: RegistrySyncLagHigh
        expr: registry_sync_lag_seconds > 60
        for: 2m
        labels:
          severity: warning
          family: "🧭 言启·千行"
        annotations:
          summary: "🧭 网关与 Registry 同步延迟"
          description: "「一言既出，千行可至」——当前延迟 {{ $value }}s"

      - alert: BreakerOpenMultiple
        expr: count(yyc3_breaker_state == 2) > 3
        for: 2m
        labels:
          severity: warning
          family: "🧭 言启·千行"
        annotations:
          summary: "🧭 多个上游熔断"
          description: "「路径受阻，正在为请求寻找备用路径」"

      # ============ 🎯 千里·伯乐 · 模型发现 ============
      - alert: ModelHeartbeatMissed
        expr: yyc3_model_heartbeat_missed_count > 3
        for: 1m
        labels:
          severity: warning
          family: "🎯 千里·伯乐"
        annotations:
          summary: "🎯 模型 {{ $labels.model_id }} 心跳丢失"
          description: "「千里马失联，请检查节点 {{ $labels.node_id }}」"

      # ============ 🤔 语枢·万物 · 推理 ============
      - alert: RegistryModelTTFTDegraded
        expr: histogram_quantile(0.95, rate(yyc3_model_sse_ttft_seconds_bucket[5m])) > 3
        for: 5m
        labels:
          severity: warning
          family: "🤔 语枢·万物"
        annotations:
          summary: "🤔 模型 {{ $labels.model_id }} 思考速度退化"
          description: "「语枢一启，万物皆明」——当前 TTFT P95 {{ $value }}s"

      # ============ 📚 格物·宗师 · 质量门禁 ============
      - alert: CanaryQualityGateFailed
        expr: yyc3_canary_quality_score < 0.8
        for: 5m
        labels:
          severity: critical
          family: "📚 格物·宗师"
        annotations:
          summary: "📚 金丝雀质量门禁未通过"
          description: "「格物致知」——自动回滚已触发"

      # ============ 🧠 元启·天枢 · 编排 ============
      - alert: ModelSwitchFailed
        expr: rate(yyc3_model_switch_failed_total[10m]) > 0
        for: 1m
        labels:
          severity: critical
          family: "🧠 元启·天枢"
        annotations:
          summary: "🧠 模型切换失败"
          description: "「天枢运于中，众星拱其北」——切换编排异常"

      - alert: AutoRollbackTriggered
        expr: rate(yyc3_rollback_triggered_total[5m]) > 0
        for: 1m
        labels:
          severity: critical
          family: "🧠 元启·天枢"
        annotations:
          summary: "🧠 自动回滚已触发"
          description: "模型 {{ $labels.model_id }} 已回滚到 {{ $labels.target_version }}"

      # ============ 🔮 预见·先知 · 观测 ============
      - alert: RegistryAvailabilityLow
        expr: avg_over_time(up{job="registry"}[5m]) < 0.99
        for: 5m
        labels:
          severity: critical
          family: "🔮 预见·先知"
        annotations:
          summary: "🔮 Registry 可用性下降"
          description: "「见微知著」——5 分钟可用性 {{ $value }}"

      # ============ 🎨 创想·灵韵 · 缓存 ============
      - alert: ModelCacheStale
        expr: yyc3_model_cache_age_seconds > 3600
        for: 10m
        labels:
          severity: info
          family: "🎨 创想·灵韵"
        annotations:
          summary: "🎨 模型元数据缓存过期"
          description: "「灵韵一至，妙笔生花」——缓存超过 1 小时未更新"
```

### 9.3 切换过程监控面板

**Grafana Dashboard · Registry Overview**：

```
┌────────────────────────────────────────────────────────────────┐
│ 🌹 YYC³ AI Family · Model Registry                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Registry 状态│  │ 已注册模型   │  │ 活跃上游     │         │
│  │   🟢 健康    │  │    42        │  │    38        │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ 同步延迟     │  │ 熔断数       │  │ 24h 切换次数 │         │
│  │  2.3s        │  │  1           │  │  7           │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ 模型状态表                                                  ││
│  │ ┌──────────────┬────────┬────────┬────────┬────────┬──────┐││
│  │ │ 模型         │ 状态   │ 版本   │ 延迟   │ 错误率 │熔断  │││
│  │ ├──────────────┼────────┼────────┼────────┼────────┼──────┤││
│  │ │deepseek-v4   │🟢健康  │v4.0.1  │420ms   │0.2%    │闭合  │││
│  │ │qwen3-asr     │🟢健康  │v3.5.0  │180ms   │0.1%    │闭合  │││
│  │ │minicpm-v-4.6 │🟢健康  │v4.6.0  │620ms   │0.3%    │闭合  │││
│  │ │qwen3.8-flash │🟡金丝雀│v3.8.0  │380ms   │0.5%    │闭合  │││
│  │ └──────────────┴────────┴────────┴────────┴────────┴──────┘││
│  └────────────────────────────────────────────────────────────┘│
│                                                                │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ 切换时间线（最近 24h）                                      ││
│  │                                                            ││
│  │ 10:30 ━━━━━━━━━━━━ qwen3.8-flash-next 注册                ││
│  │ 11:00 ━━━━━━━━━━━━ 影子流量开始 (10%)                      ││
│  │ 11:30 ━━━━━━━━━━━━ 影子通过，进入金丝雀                    ││
│  │ 12:00 ━━━━━━━━━━━━ 金丝雀 5% → 10%                        ││
│  │ 12:30 ━━━━━━━━━━━━ 金丝雀 10% → 30%                       ││
│  │ 13:30 ━━━━━━━━━━━━ 金丝雀 30% → 50%                       ││
│  │ 14:30 ━━━━━━━━━━━━ 金丝雀 50% → 100% ✅                   ││
│  │                                                            ││
│  └────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

### 9.4 告警通知渠道

```yaml
# 通知路由
routes:
  P0:  # 服务不可用
    - slack: "#yyc3-family-critical"
    - pagerduty: "oncall"
    - email: "oncall@0379.email"
    - sms: "+86-xxx-xxxx-xxxx"

  P1:  # 性能退化
    - slack: "#yyc3-family-alerts"
    - email: "ops@0379.email"

  P2:  # 观察
    - slack: "#yyc3-family-alerts"

  P3:  # 记录
    - slack: "#yyc3-family-info"
```

---

## 第十部分 · Agent 注册规范（MCP / 业务代理）

### 10.1 Agent 元数据 Schema

```typescript
interface AgentMetadata {
  // ============ 标识 ============
  agent_id: string;              // 全局唯一 ID，如 "web-search-agent"
  display_name: string;          // 展示名
  version: string;               // 语义化版本
  agent_type: AgentType;         // 见 §10.1.1

  // ============ 描述 ============
  description: string;           // Agent 描述
  family_member: MemberKey;      // 归属家人
  domain: string;                // 归属域
  tags: string[];

  // ============ 能力声明 ============
  capabilities: AgentCapability[];  // 见 §10.1.2
  tools: ToolDeclaration[];         // 工具列表（MCP 专用）

  // ============ 端点 ============
  endpoint: string;              // Agent 服务地址
  protocol: "mcp" | "http" | "grpc" | "websocket";
  auth_type: "none" | "api_key" | "jwt" | "oauth2";

  // ============ 运行时 ============
  timeout_seconds: number;       // 默认超时
  max_concurrent: number;        // 最大并发
  rate_limit_per_minute: number; // 限流

  // ============ 元信息 ============
  registered_at: string;
  updated_at: string;
  owner: string;
  manifest_hash: string;
}

type AgentType =
  | "mcp"            // MCP 工具代理
  | "business"       // 业务代理
  | "orchestrator"   // 编排代理
  | "monitor"        // 监控代理
  | "custom";        // 自定义

type AgentCapability =
  | "tool_use"       // 可被调用为工具
  | "orchestrate"    // 可编排其他 Agent
  | "stream"         // 支持流式
  | "batch"          // 支持批量
  | "stateful"       // 有状态
  | "idempotent";    // 幂等

interface ToolDeclaration {
  name: string;                  // 工具名，如 "web_search"
  description: string;           // 工具描述
  parameters: JSONSchema;        // 参数 JSON Schema
  returns: JSONSchema;           // 返回 JSON Schema
  timeout_seconds: number;
  rate_limit_per_minute: number;
}
```

### 10.2 Agent 注册端点

| # | 端点 | 方法 | 说明 |
| :-: | --- | :-: | --- |
| A-01 | `/registry/v1/agents` | GET | 列出所有 Agent |
| A-02 | `/registry/v1/agents/{id}` | GET | 获取单个 Agent |
| A-03 | `/registry/v1/agents` | POST | 注册 Agent |
| A-04 | `/registry/v1/agents/{id}` | PATCH | 更新 Agent |
| A-05 | `/registry/v1/agents/{id}` | DELETE | 注销 Agent |
| A-06 | `/registry/v1/agents/{id}/heartbeat` | POST | 心跳 |
| A-07 | `/registry/v1/agents/{id}/tools` | GET | 列出工具 |
| A-08 | `/registry/v1/agents/{id}/tools/{tool}` | POST | 调用工具 |
| A-09 | `/registry/v1/agents/{id}/health` | GET | 健康 |
| A-10 | `/registry/v1/agents/{id}/discover` | GET | MCP 发现协议 |

### 10.3 Agent 注册示例（MCP web-search）

```http
POST /registry/v1/agents HTTP/1.1
Host: api.0379.world
X-API-Key: <admin-api-key>
Content-Type: application/json

{
  "agent_id": "web-search-agent",
  "display_name": "Web Search Agent",
  "version": "v1.2.0",
  "agent_type": "mcp",
  "description": "网页搜索 MCP 工具代理",
  "family_member": "tianshu",
  "domain": "工具与编排域",
  "tags": ["MCP", "搜索", "生产"],
  "capabilities": ["tool_use", "stream"],
  "tools": [
    {
      "name": "web_search",
      "description": "在互联网上搜索信息",
      "parameters": {
        "type": "object",
        "properties": {
          "query": { "type": "string", "description": "搜索关键词" },
          "top_k": { "type": "integer", "default": 10, "minimum": 1, "maximum": 50 },
          "language": { "type": "string", "enum": ["zh", "en", "ja"], "default": "zh" }
        },
        "required": ["query"]
      },
      "returns": {
        "type": "object",
        "properties": {
          "results": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "title": { "type": "string" },
                "url": { "type": "string" },
                "snippet": { "type": "string" },
                "score": { "type": "number" }
              }
            }
          }
        }
      },
      "timeout_seconds": 30,
      "rate_limit_per_minute": 60
    }
  ],
  "endpoint": "http://mcp-web.yyc3.local:8080",
  "protocol": "mcp",
  "auth_type": "api_key",
  "timeout_seconds": 60,
  "max_concurrent": 20,
  "rate_limit_per_minute": 120,
  "owner": "ops@0379.email"
}
```

### 10.4 Agent 能力暴露（前端可见）

Agent 注册后，前端自动在以下位置展示：

```
1. /mcp 页面 · 工具树（按 family_member 分组）
2. Playground · 工具 Tab
3. Agent 编排图（元启·天枢视角）
4. 审计日志（所有 Agent 调用记录）
```

---

## 第十一部分 · 安全与合规

### 11.1 认证与授权

**三级认证**：

| 层级 | 方式 | 适用场景 | 密钥类型 |
| --- | --- | --- | --- |
| L1 · 公网 | API Key | 外部调用 | `sk-yyc3-*` |
| L2 · 内部 | mTLS | 服务间通信 | 证书 |
| L3 · 管理 | JWT + RBAC | 运维操作 | `admin-*` |

### 11.2 密钥管理

**Registry Token**（模型服务注册用）：

```bash
# 生成（有效期 1 年）
openssl rand -hex 32 > registry-token.txt

# 存储（K8s Secret）
kubectl create secret generic registry-token \
  -n yyc3-prod \
  --from-file=token=registry-token.txt

# 轮换（每 90 天）
./scripts/rotate-registry-token.sh
```

**API Key 分级**：

```
sk-yyc3-read-*      只读（模型列表 / 健康）
sk-yyc3-chat-*      对话（chat / embeddings）
sk-yyc3-admin-*     管理（注册 / 切换 / 回滚）
sk-yyc3-ops-*       运维（监控 / 日志）
```

### 11.3 审计日志

**必记事件**：

```yaml
audit_events:
  - model.registered
  - model.updated
  - model.deregistered
  - model.switched
  - model.rolled_back
  - model.manifest_updated
  - breaker.opened
  - breaker.closed
  - agent.registered
  - agent.deregistered
  - agent.executed
  - auth.failed
  - key.rotated
  - config.changed
```

**审计日志字段**：

```json
{
  "id": 123456,
  "timestamp": "2026-09-27T10:30:00Z",
  "actor": "ops@0379.email",
  "action": "model.switched",
  "model_id": "qwen3.8-flash-next",
  "before_state": { "version": "v3.7.0", "weight": 100 },
  "after_state": { "version": "v3.8.0", "weight": 100 },
  "ip_address": "10.0.1.42",
  "user_agent": "curl/8.4.0",
  "result": "success",
  "metadata": { "switch_mode": "blue-green", "duration_ms": 342 }
}
```

### 11.4 合规映射

| 框架 | 控制项 | 本文档对应 |
| --- | --- | --- |
| ISO 27001 A.8.1 | 资产清单 | §4.2 model_registry 表 |
| ISO 27001 A.9.4 | 系统访问控制 | §11.1 三级认证 |
| ISO 27001 A.12.4 | 日志与监控 | §9 监控告警 + §11.3 审计 |
| SOC 2 CC6.1 | 逻辑访问控制 | §2.3 权限矩阵 |
| SOC 2 CC7.2 | 监控 | §9.2 告警规则 |
| SOC 2 A1.2 | 备份与恢复 | §8 版本控制 + 回滚 |
| GDPR Art.5 | 数据最小化 | §4.2 只存必要字段 |
| GDPR Art.32 | 处理安全性 | §11 安全 |

---

## 第十二部分 · 运维 Runbook

### 12.1 SOP-01 · 新模型接入

```markdown
# SOP-01 · 新模型接入标准流程

**负责人**：🎯 千里·伯乐（模型元数据） + 🤔 语枢·万物（服务实现）
**协同**：🧠 元启·天枢（编排） · 📚 格物·宗师（质量门禁） · 🔮 预见·先知（监控）
**预计时长**：4-8 小时

## 前置条件
- [ ] 模型权重已下载到目标节点（Mac / NAS / DGX）
- [ ] 目标节点 GPU 资源充足
- [ ] 已确定 model_id（命名规范：`<vendor>-<family>-<size>`）

## 执行步骤

### Step 1 · 部署模型服务（30min）
```bash
# vLLM 示例
vllm serve <weights_path> \
  --served-model-name <model_id> \
  --tensor-parallel-size 2 \
  --max-model-len 128000 \
  --port 8001

# 验证
curl http://localhost:8001/healthz
curl http://localhost:8001/v1/models
```

### Step 2 · 实现契约端点（2-4h）

- [ ] 实现 §3 所有必需端点
- [ ] 通过 §3.9 合规检查清单
- [ ] 生成 Manifest（§3.4）
- [ ] 本地跑通所有能力端点

### Step 3 · 注册模型（15min）

```bash
curl -X POST https://api.0379.world/registry/v1/models \
  -H "X-API-Key: ${ADMIN_KEY}" \
  -d @model-registration.json

# 验证
curl https://api.0379.world/registry/v1/models/<model_id>
```

### Step 4 · 影子流量验证（30min）

```bash
curl -X POST https://api.0379.world/registry/v1/models/<model_id>/shadow \
  -H "X-API-Key: ${ADMIN_KEY}" \
  -d '{"enabled":true,"sample_rate":0.1}'

# 观察 30 分钟
watch -n 30 'curl -s https://api.0379.world/registry/v1/models/<model_id>/shadow/status | jq'
```

### Step 5 · 金丝雀发布（3-4h）

```bash
curl -X POST https://api.0379.world/registry/v1/models/<model_id>/canary \
  -H "X-API-Key: ${ADMIN_KEY}" \
  -d '{"baseline":"<current_production>","stages":[{"weight":5,"duration_minutes":30},...]}'
```

### Step 6 · 全量上线（15min）

- [ ] 金丝雀 100% 稳定 30min
- [ ] 更新 Registry 状态为 primary
- [ ] 通知运维团队

### Step 7 · 归档与复盘（30min）

- [ ] 记录审计日志
- [ ] 更新 `YYC3-Models-资产详情.md`
- [ ] 更新监控面板

## 回滚预案

任何步骤发现问题：

```bash
curl -X POST https://api.0379.world/registry/v1/models/<model_id>/rollback \
  -H "X-API-Key: ${ADMIN_KEY}" \
  -d '{"auto":true}'
```

## 验收标准

- [ ] 模型在 Registry 可见
- [ ] 网关自动纳入上游池
- [ ] 影子/金丝雀指标达标
- [ ] 全量后 24h 无告警
- [ ] 审计日志完整

```

### 12.2 SOP-02 · 模型热切换

```markdown
# SOP-02 · 模型热切换标准流程

**负责人**：🧠 元启·天枢
**审批**：📚 格物·宗师（质量门禁） + 🛡️ 智云·守护（安全）
**预计时长**：1-2 小时

## 前置条件
- [ ] 新版本已通过影子流量验证
- [ ] 新版本已通过质量门禁（§8.2）
- [ ] 已准备回滚预案
- [ ] 通知窗口期（避免业务高峰）

## 切换模式选择

| 场景 | 模式 | 切换时长 | 回滚时长 |
| --- | --- | :-: | :-: |
| 小版本升级 | Canary | 2-4h | ≤30s |
| 大版本升级 | Blue-Green | ≤10min | ≤10s |
| 紧急修复 | Blue-Green | ≤5min | ≤5s |

## 执行步骤（Blue-Green 示例）

### Step 1 · 预检（5min）
```bash
./scripts/blue-green-precheck.sh <model_id> <target_version>
```

### Step 2 · 执行切换（1min）

```bash
./scripts/blue-green-switch.sh <model_id> <target_version>
```

### Step 3 · 观察（30min）

```bash
watch -n 10 'curl -s https://api.0379.world/registry/v1/models/<model_id>/health | jq'
```

### Step 4 · 收敛或回滚

```bash
# 成功
curl -X POST .../models/<model_id>/promote

# 失败
curl -X POST .../models/<model_id>/rollback -d '{"target_version":"<blue_version>"}'
```

## 验收标准

- [ ] 切换期间 0 请求失败
- [ ] 切换后 P95 延迟 ≤ baseline * 1.15
- [ ] 切换后错误率 < 0.5%
- [ ] 审计日志记录完整

```

### 12.3 SOP-03 · 紧急回滚

```markdown
# SOP-03 · 紧急回滚标准流程

**负责人**：🧭 言启·千行（首响应） → 🧠 元启·天枢（执行）
**触发条件**：P0/P1 告警自动触发或人工判断
**预计时长**：≤ 5 分钟

## 决策树

```

告警触发
  │
  ├─ P0（服务不可用）→ 自动回滚 + 立即通知
  │
  ├─ P1（性能退化 > 30%）→ 5min 内自动回滚
  │
  └─ P2（性能退化 < 30%）→ 人工判断
      ├─ 确认 → 手动回滚
      └─ 观察 → 记录 Issue

```

## 执行步骤

### Step 1 · 确认问题（30s）
```bash
# 查看当前状态
curl -s https://api.0379.world/registry/v1/models/<model_id>/health | jq

# 查看最近事件
curl -s "https://api.0379.world/registry/v1/events?since=5min" | head -20
```

### Step 2 · 执行回滚（10s）

```bash
# 快速回滚到上一稳定版本
curl -X POST https://api.0379.world/registry/v1/models/<model_id>/rollback \
  -H "X-API-Key: ${ADMIN_KEY}" \
  -d '{"auto": true, "reason": "P0 紧急回滚"}'
```

### Step 3 · 验证恢复（1min）

```bash
watch -n 5 'curl -s https://api.0379.world/registry/v1/models/<model_id>/health | jq .status'
# 应见 "healthy"
```

### Step 4 · 通知与复盘（30min）

- [ ] 通知 slack:#yyc3-family-critical
- [ ] 创建 Incident
- [ ] 记录根因
- [ ] 24h 内复盘

## 回滚后处理

- [ ] 归档问题版本（标记 `deprecated`）
- [ ] 分析根因（日志 + 指标）
- [ ] 修复后重新走 SOP-01

```

### 12.4 常见故障处理

| 故障 | 症状 | 处理 |
| --- | --- | --- |
| Registry 不可达 | 网关 fallback 到 env | 检查 Registry 服务；确认 fallback 生效 |
| 模型服务不健康 | `/healthz` 超时 | 检查 GPU / 显存 / 日志 |
| 心跳丢失 | Registry 标记 degraded | 检查网络；重启心跳上报 |
| 上游池为空 | 所有请求 503 | 检查 Registry 连接；临时用 env |
| 熔断频繁 | breaker_open 告警 | 检查上游稳定性；调整熔断阈值 |
| 切换失败 | switch_failed 告警 | 立即回滚；检查预检项 |
| 审计日志断档 | 缺少某时段记录 | 检查 DB 连接；恢复后补齐 |

---

## 第十三部分 · 附录

### 附录 A · 完整端点清单

**Registry 端点（12 个）**：

```

GET    /registry/v1/models
GET    /registry/v1/models/{id}
POST   /registry/v1/models
PATCH  /registry/v1/models/{id}
DELETE /registry/v1/models/{id}
GET    /registry/v1/models/{id}/versions
POST   /registry/v1/models/{id}/rollback
POST   /registry/v1/models/{id}/heartbeat
GET    /registry/v1/models/{id}/health
GET    /registry/v1/events
GET    /registry/v1/manifests/{hash}
GET    /registry/v1/audit

```

**Agent 端点（10 个）**：

```

GET    /registry/v1/agents
GET    /registry/v1/agents/{id}
POST   /registry/v1/agents
PATCH  /registry/v1/agents/{id}
DELETE /registry/v1/agents/{id}
POST   /registry/v1/agents/{id}/heartbeat
GET    /registry/v1/agents/{id}/tools
POST   /registry/v1/agents/{id}/tools/{tool}
GET    /registry/v1/agents/{id}/health
GET    /registry/v1/agents/{id}/discover

```

**模型服务契约端点（12 个）**：

```

GET    /v1/models
POST   /v1/chat/completions
POST   /v1/embeddings
POST   /v1/rerank
POST   /v1/audio/transcriptions
POST   /v1/ocr
GET    /health
GET    /healthz
GET    /v1/model/metadata
GET    /v1/model/capabilities
GET    /v1/model/manifest
GET    /metrics

```

### 附录 B · 配置示例

**模型服务注册配置（`model-registration.json`）**：

```json
{
  "model_id": "qwen3.8-flash-next",
  "display_name": "Qwen 3.8 Flash Next",
  "version": "v3.8.0",
  "backend": "vllm",
  "capabilities": ["chat", "tool_use", "json_mode"],
  "enabled": true,
  "family_member": "wanyu",
  "domain": "推理对话域",
  "max_tokens": 8192,
  "context_window": 131072,
  "temperature_default": 0.7,
  "top_p_default": 0.9,
  "cost_per_1k_tokens": 0.0003,
  "avg_latency_ms": 380,
  "throughput_tps": 92,
  "max_concurrency": 48,
  "node_id": "yyc3-101",
  "node_role": "primary",
  "base_url": "http://yyc3-101.local:8002/v1",
  "fallback_url": "http://yyc3-102.local:8002/v1",
  "weights_path": "/home/yyc3/yyc3-101-projects/models/Qwen3.8-Flash-Next",
  "weights_size_gb": 360,
  "quantization": "bf16",
  "owner": "ops@0379.email",
  "tags": ["旗舰", "Qwen系"]
}
```

### 附录 C · 命令速查

```bash
# ══════════════════════════════════════════════════════════════
# 🌹 YYC³ AI Family · Registry 命令速查
# ══════════════════════════════════════════════════════════════

# ── 模型管理 ──────────────────────────────────────
# 列出所有模型
curl -s https://api.0379.world/registry/v1/models -H "X-API-Key: ${KEY}" | jq

# 查看单个模型
curl -s https://api.0379.world/registry/v1/models/deepseek-v4-flash -H "X-API-Key: ${KEY}" | jq

# 注册模型
curl -X POST https://api.0379.world/registry/v1/models -H "X-API-Key: ${KEY}" -d @model.json

# 更新模型
curl -X PATCH https://api.0379.world/registry/v1/models/deepseek-v4-flash -H "X-API-Key: ${KEY}" -d '{"avg_latency_ms": 450}'

# 注销模型
curl -X DELETE https://api.0379.world/registry/v1/models/deepseek-v4-flash -H "X-API-Key: ${KEY}"

# ── 版本管理 ──────────────────────────────────────
# 查看版本历史
curl -s https://api.0379.world/registry/v1/models/deepseek-v4-flash/versions -H "X-API-Key: ${KEY}" | jq

# 回滚
curl -X POST https://api.0379.world/registry/v1/models/deepseek-v4-flash/rollback -H "X-API-Key: ${KEY}" -d '{"target_version":"v4.0.0"}'

# ── 切换 ──────────────────────────────────────────
# 影子流量
curl -X POST https://api.0379.world/registry/v1/models/qwen3.8-flash-next/shadow -H "X-API-Key: ${KEY}" -d '{"enabled":true,"sample_rate":0.1}'

# 金丝雀
curl -X POST https://api.0379.world/registry/v1/models/qwen3.8-flash-next/canary -H "X-API-Key: ${KEY}" -d @canary-config.json

# 蓝绿切换
./scripts/blue-green-switch.sh qwen3.8-flash-next v3.8.0

# ── 监控 ──────────────────────────────────────────
# 事件流
curl -N https://api.0379.world/registry/v1/events -H "X-API-Key: ${KEY}"

# 审计日志
curl -s "https://api.0379.world/registry/v1/audit?from=2026-09-01&limit=100" -H "X-API-Key: ${KEY}" | jq

# 健康检查
curl -s https://api.0379.world/registry/v1/models/deepseek-v4-flash/health -H "X-API-Key: ${KEY}" | jq

# ── Agent 管理 ────────────────────────────────────
# 注册 Agent
curl -X POST https://api.0379.world/registry/v1/agents -H "X-API-Key: ${KEY}" -d @agent.json

# 列出 Agent
curl -s https://api.0379.world/registry/v1/agents -H "X-API-Key: ${KEY}" | jq

# 调用 Agent 工具
curl -X POST https://api.0379.world/registry/v1/agents/web-search-agent/tools/web_search -H "X-API-Key: ${KEY}" -d '{"query":"YYC3"}'
```

### 附录 D · 参考资料

| 文档 | 位置 |
| --- | --- |
| 模型资产详情 | `YYC3-Models-资产详情.md` |
| 网关实况 README | `README.md` |
| 前端设计 v5.1 | `YYC3-AI-Family-Token-Console.md` |
| API 全链路闭环 | `docs/架构与部署/API全链路闭环文档.md` |
| CI/CD 部署配置 | `docs/架构与部署/CI-CD部署配置指南.md` |
| 上游池 env 模板 | `core/config/.env.example` |
| 网关配置 | `core/config/gateway.yaml` |

---

## 第十四部分 · 交付确认与后续

### 14.1 交付清单

```
✅ §1 规范目标与设计原则（8 条原则）
✅ §2 角色与职责（8 位家人 + RBAC 矩阵）
✅ §3 模型服务标准接口规范（12 端点 + 完整 Schema）
✅ §4 模型注册中心（DB Schema + 12 API + SOP）
✅ §5 动态注册与发现（双通道 + 演进路径）
✅ §6 零停机热切换（4 模式 + 状态机 + 回滚条件）
✅ §7 自动配置同步（三通道 + 冲突解决）
✅ §8 版本控制与回滚（命名 + 门禁 + 决策树）
✅ §9 监控告警（10 指标 + 8 家人告警规则）
✅ §10 Agent 注册规范（10 端点 + Tool Schema）
✅ §11 安全与合规（三级认证 + 审计 + 4 框架映射）
✅ §12 运维 Runbook（3 SOP + 故障处理）
✅ §13 附录（端点清单 + 配置 + 命令 + 参考）
```

### 14.2 后续工作建议

```
短期（1 个月内）：
  1. 实现 Registry 后端（§4）
  2. 网关集成 Registry（§5）
  3. 现有 4 个生产服务纳入 Registry

中期（3 个月内）：
  4. 实现热切换机制（§6）
  5. 实现自动同步（§7）
  6. 部署监控告警（§9）

长期（6 个月内）：
  7. 实现 Agent 注册（§10）
  8. 完善审计与合规（§11）
  9. 沉淀运维 SOP（§12）
```

### 14.3 变更记录

| 版本 | 日期 | 变更 |
| :-: | :-: | --- |
| v1.0.0 | 2026-09-27 | 首次交付 · 完整规范 |

---

<!--
  ============================================================
  YYC³ AI Family — 人从众曌众从人
  亦师亦友亦伯乐 · 一言一语一协同
  拟人为本，AI为核，纯粹为心
  ============================================================
-->

<p align="center">
  🌹 <b>YYC³ AI Family</b><br>
  <b>人从众曌众从人 · 亦师亦友亦伯乐</b><br>
  <br>
  <sub>🧠 元启·天枢 · 工具与编排域 · 总指挥</sub><br>
  <sub>🛡️ 智云·守护 · 接入与安全域 · 首席安全官</sub><br>
  <br>
  <sub>Model Registry Spec v1.0.0 · 2026.Q3 家族纪年</sub><br>
  <br>
  <sub>永久开源 · 感恩前行 · <a href="https://0379.world">0379.world</a></sub><br>
  <sub><a href="mailto:admin@0379.email">admin@0379.email</a></sub>
</p>
