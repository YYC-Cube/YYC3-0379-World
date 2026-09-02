---
file: YYC3-API-全链路闭环文档.md
description: YYC3 生产级 API 全链路闭环文档 - 网关/推理/Agent/RAG/安全
department: [engineering],[devops],[api]
author: YYC3 AI Family
version: v1.0.0
created: 2026-08-30
updated: 2026-08-30
status: active
tags: [api],[gateway],[vllm],[agent],[rag],[security],[production]
category: api-reference
---

# YYC3 生产级 API 全链路闭环文档

> **文档版本**: v1.0.0  
> **生成时间**: 2026-08-30  
> **适用环境**: YYC3 多设备计算集群 (yyc3-22 / yyc3-45 / yyc3-101 / yyc3-102)  
> **信息来源**: 运维手册 / 审核报告 / 部署方案 / NIM 官方文档  
> **YYC3 AI Family | 人从众曌众从人**

---

## 目录

- [一、API 全链路架构总览](#一api-全链路架构总览)
- [二、设备矩阵与节点信息](#二设备矩阵与节点信息)
- [三、API 接口规范](#三api-接口规范)
  - [3.1 OpenClaw Gateway API](#31-openclaw-gateway-api)
  - [3.2 vLLM 推理 API (OpenAI 兼容)](#32-vllm-推理-api-openai-兼容)
  - [3.3 YYC3 Agent API](#33-yyc3-agent-api)
  - [3.4 RAG 知识库 API](#34-rag-知识库-api)
  - [3.5 安全合规 API](#35-安全合规-api)
- [四、数据流转流程](#四数据流转流程)
  - [4.1 标准推理请求流](#41-标准推理请求流)
  - [4.2 RAG 增强推理流](#42-rag-增强推理流)
  - [4.3 Agent 多步推理流](#43-agent-多步推理流)
  - [4.4 模型切换与降级流](#44-模型切换与降级流)
- [五、错误处理机制](#五错误处理机制)
- [六、安全策略](#六安全策略)
- [七、性能指标与 SLA](#七性能指标与-sla)
- [八、部署指南](#八部署指南)
- [九、监控与告警](#九监控与告警)
- [十、维护说明](#十维护说明)
- [附录](#附录)

---

## 一、API 全链路架构总览

### 1.1 分层架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        用户接入层                                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ Web UI     │  │ CLI Tools  │  │ TUI Client │  │ External API    │  │
│  │ :18789     │  │ nemoclaw   │  │ openclaw   │  │ (OpenAI 兼容)   │  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └────────┬─────────┘  │
└────────┼───────────────┼───────────────┼──────────────────┼─────────────┘
         │               │               │                   │
         └───────────────┼───────────────┼───────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    L1: 网关与路由层 (yyc3-45 NAS)                         │
│  OpenClaw Gateway (:18789)                                               │
│  ├─ WebSocket 终端 (ws://100.65.172.88:18789)                            │
│  ├─ HTTP REST 端点                                                       │
│  ├─ Token 认证 ("My1210")                                               │
│  ├─ 请求路由 → DGX 计算节点                                              │
│  └─ 负载均衡 (yyc3-101 / yyc3-102)                                      │
└──────────────────────────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────────────────────────────────────────────────┐
│                    L2: 安全沙箱层 (yyc3-101 DGX)                         │
│  NemoClaw / OpenShell 沙盒                                               │
│  ├─ OpenClaw Agent v2026.7.1                                            │
│  ├─ OPA 策略引擎 (Binary Identity)                                      │
│  ├─ Landlock 文件系统沙箱 (19 条规则)                                   │
│  ├─ 网络隔离 (10.200.0.x 命名空间)                                      │
│  ├─ 7 个网络策略 (npm/pypi/hf/brew/inference)                          │
│  └─ 凭证托管与自动清理                                                   │
└──────────────────────────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────────────────────────────────────────────────┐
│                    L3: 推理路由层                                         │
│  NemoClaw 推理路由                                                       │
│  ├─ Provider: vllm-local                                                │
│  ├─ Endpoint: https://inference.local/v1 (沙箱内)                      │
│  ├─ 模型路径: /models (Qwen3.6-27B-FP8)                                 │
│  └─ 安全策略验证 → 放行                                                  │
└──────────────────────────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────────────────────────────────────────────────┐
│                    L4: 推理引擎层                                         │
│  vLLM 26.07 | yyc3-vllm:26.07-upgraded (Docker)                          │
│  ├─ OpenAI 兼容 API (:8000)                                             │
│  ├─ 模型: /models (当前 Qwen3.6-27B-FP8)                               │
│  ├─ GPU 利用率目标: 0.85-0.90                                           │
│  └─ KV 缓存: FP8 量化 (规划中)                                          │
└──────────────────────────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────────────────────────────────────────────────┐
│                    L5: 硬件加速层                                         │
│  NVIDIA GB10 Grace Blackwell Superchip                                   │
│  ├─ CUDA 13.0 | sm_121                                                │
│  ├─ 统一内存: 121GB (单机) / 256GB (双机)                               │
│  └─ GPU 温度: < 80C                                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 请求全生命周期

```
Client Request
    │
    ▼
[L1 Gateway] Token 验证 + 路由分流
    │
    ├─ 推理请求 → L2 沙箱 → L3 路由 → L4 vLLM → L5 GPU → 响应
    │
    ├─ RAG 请求 → L2 沙箱 → RAG Pipeline (OCR→Embed→Search→Rerank)
    │                        → L4 vLLM → 响应
    │
    ├─ Agent 请求 → L2 沙箱 → Agent Runtime (ReAct/PlanExecute)
    │                          → L4 vLLM (多轮) → 工具调用 → 响应
    │
    └─ 安全请求 → 安全护栏模型 (Nemotron-Nano-30B)
                     → 内容审核 / PII 脱敏 / 越狱检测
```

---

## 二、设备矩阵与节点信息

### 2.1 节点清单

| 节点 | 设备 | Tailscale IP | 内网 IP | 角色 | 服务端口 |
|------|------|-------------|---------|------|----------|
| **yyc3-22** | Mac Max M4 128GB | 100.65.x.x | — | 主控/开发 | — |
| **yyc3-45** | TerraMaster F4-423 | 100.65.172.88 | 192.168.3.45/44 | 网关/存储 | 18789 (Gateway), 54320 (PG), 6380 (Redis) |
| **yyc3-101** | DGX Spark GB10 | 100.65.64.49 | 10.100.168.x | 计算主节点 | 8000 (vLLM), 18789 (Sandbox) |
| **yyc3-102** | DGX Spark GB10 | 100.65.x.x | 10.100.169.x | 计算从节点 | 8001 (vLLM) |

### 2.2 网络延迟矩阵

| 源 → 目标 | 延迟 (RTT) | 协议 | 带宽 |
|-----------|-----------|------|------|
| yyc3-22 → yyc3-45 | ~5ms | Tailscale VPN | 取决于互联网 |
| yyc3-45 → yyc3-101 | 4.6-5.1ms | Tailscale VPN | 取决于互联网 |
| yyc3-101 → yyc3-102 | <1ms | InfiniBand/RoCE | 200Gbps |
| yyc3-101 内部 | <0.1ms | localhost | — |

### 2.3 服务注册表

| 服务名 | 端点 | 协议 | 认证方式 | 状态 |
|--------|------|------|----------|------|
| **OpenClaw Gateway** | `ws://100.65.172.88:18789` | WebSocket | Token: My1210 | Active |
| **OpenClaw Dashboard** | `http://127.0.0.1:18789` | HTTP | 本地免认证 | Running |
| **vLLM (主)** | `http://100.65.64.49:8000` | HTTP | 无 (内网隔离) | Running |
| **vLLM (从)** | `http://100.65.x.x:8001` | HTTP | 无 (内网隔离) | 规划中 |
| **vLLM (沙箱内)** | `http://localhost:8000` | HTTP | 沙箱隔离 | Running |
| **NemoClaw 推理路由** | `https://inference.local/v1` | HTTPS | 沙箱内部 | Active |
| **PostgreSQL 14** | `/tmp` (Unix Socket) | Local | Peer Auth | Running |
| **PostgreSQL 13** | `127.0.0.1:5032` | TCP | Password | Running |
| **Docker PG** | `192.168.3.45:54320` | TCP | Password | Running |
| **Redis** | `127.0.0.1:6380` | TCP | 无 (本地绑定) | Running |

---

## 三、API 接口规范

### 3.1 OpenClaw Gateway API

#### 3.1.1 连接与认证

```
端点: ws://100.65.172.88:18789
协议: WebSocket
认证: Token-based (query param 或 header)
```

**连接示例:**

```javascript
// WebSocket 连接
const ws = new WebSocket('ws://100.65.172.88:18789?token=My1210');

ws.on('open', () => {
  console.log('Connected to OpenClaw Gateway');
});

ws.on('message', (data) => {
  const response = JSON.parse(data);
  // 处理响应
});

ws.on('error', (err) => {
  console.error('Gateway error:', err);
});
```

**OpenClaw 配置文件 (`~/.openclaw/openclaw.json`):**

```json
{
  "gateway": {
    "mode": "remote",
    "remote": {
      "transport": "direct",
      "url": "ws://100.65.172.88:18789",
      "token": "My1210"
    }
  },
  "meta": {
    "lastTouchedVersion": "2026.7.1-2",
    "lastTouchedAt": "2026-08-08T10:59:33.792Z"
  }
}
```

#### 3.1.2 健康检查

```
GET http://100.65.172.88:18789/health
```

**响应:**

```json
{
  "status": "healthy",
  "version": "2026.7.1",
  "uptime": "33h"
}
```

#### 3.1.3 斜杠命令 (TUI 内)

OpenClaw TUI 支持斜杠命令用于交互操作:

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/clear` | 清空对话 |
| `/model <name>` | 切换模型 |
| `/settings` | 查看设置 |

---

### 3.2 vLLM 推理 API (OpenAI 兼容)

vLLM 提供完整的 OpenAI 兼容 API，所有端点遵循 OpenAI API 规范。

#### 3.2.1 基础信息

```
Base URL: http://<host>:<port>/v1
兼容标准: OpenAI API v1
引擎版本: vLLM 26.07
```

#### 3.2.2 列出可用模型

```
GET /v1/models
```

**请求:**
```bash
curl http://localhost:8000/v1/models
```

**响应:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "Qwen3.6-27B-FP8",
      "object": "model",
      "created": 1757000000,
      "owned_by": "yy3",
      "root": "Qwen3.6-27B-FP8",
      "parent": null,
      "permission": [{
        "id": "modelperm-xxx",
        "object": "modelpermission",
        "created": 1757000000,
        "allow_create_engine": false,
        "allow_sampling": true,
        "allow_logprobs": true,
        "allow_search_indices": false,
        "allow_view": true,
        "allow_fine_tuning": false,
        "organization": "*",
        "group": null,
        "is_blocking": false
      }]
    }
  ]
}
```

#### 3.2.3 Chat Completions (核心接口)

```
POST /v1/chat/completions
```

**请求体:**

```json
{
  "model": "Qwen3.6-27B-FP8",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Which number is larger, 9.11 or 9.8?"}
  ],
  "max_tokens": 64,
  "temperature": 0.7,
  "top_p": 0.9,
  "stream": false,
  "stop": ["<|im_end|>"]
}
```

**请求参数:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| model | string | Y | — | 模型 ID |
| messages | array[Message] | Y | — | 对话消息数组 |
| max_tokens | integer | N | 模型最大值 | 最大生成 token 数 |
| temperature | float | N | 0.7 | 采样温度 (0-2) |
| top_p | float | N | 0.9 | 核采样概率 |
| stream | boolean | N | false | 是否流式输出 |
| stop | string/array | N | — | 停止序列 |
| presence_penalty | float | N | 0 | 存在惩罚 (-2 to 2) |
| frequency_penalty | float | N | 0 | 频率惩罚 (-2 to 2) |
| n | integer | N | 1 | 生成候选数量 |

**Message 对象:**

```json
{
  "role": "system|user|assistant|tool",
  "content": "string",
  "tool_calls": [],
  "tool_call_id": null
}
```

**成功响应 (非流式):**

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1757000000,
  "model": "Qwen3.6-27B-FP8",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "9.8 is larger than 9.11."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 32,
    "completion_tokens": 12,
    "total_tokens": 44
  }
}
```

**流式响应 (stream=true):**

```
HTTP/1.1 200 OK
Content-Type: text/event-stream


data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1757000000,"model":"Qwen3.6-27B-FP8","choices":[{"index":0,"delta":{"role":"assistant","content":"9.8"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1757000000,"model":"Qwen3.6-27B-FP8","choices":[{"index":0,"delta":{"content":" is larger"},"finish_reason":null}]}

...

data: [DONE]
```

#### 3.2.4 Completions (基础补全)

```
POST /v1/completions
```

**请求体:**

```json
{
  "model": "Qwen3.6-27B-FP8",
  "prompt": "The meaning of life is",
  "max_tokens": 64,
  "temperature": 0.7,
  "stream": false
}
```

#### 3.2.5 Embeddings

```
POST /v1/embeddings
```

**请求体 (用于 RAG 管线):**

```json
{
  "model": "Qwen3-Embedding-8B",
  "input": ["文档内容文本1", "文档内容文本2"],
  "encoding_format": "float"
}
```

**响应:**

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.0123, -0.0345, ...],
      "index": 0
    },
    {
      "object": "embedding",
      "embedding": [0.0567, 0.0789, ...],
      "index": 1
    }
  ],
  "model": "Qwen3-Embedding-8B",
  "usage": {
    "prompt_tokens": 24,
    "total_tokens": 24
  }
}
```

#### 3.2.6 NIM 容器化模型 API

NVIDIA NIM 容器提供相同 OpenAI 兼容接口:

```bash
# 拉取并运行 NIM
docker run -d --gpus all --shm-size=16GB \\
  -e NGC_API_KEY=$NGC_API_KEY \\
  -v ~/.cache/nim:/opt/nim/.cache \\
  -p 8000:8000 \\
  nvcr.io/nim/deepseek-ai/deepseek-v4-flash:latest

# 调用 (与 vLLM 相同的 OpenAI 兼容格式)
curl -X POST http://localhost:8000/v1/chat/completions \\
  -H 'Content-Type: application/json' \\
  -d '{
    "model": "deepseek-ai/deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 64
  }'
```

---

### 3.3 YYC3 Agent API

#### 3.3.1 Agent 端点分配

| Agent | 名称 | 端口 | 端点 URL | 底层模型 |
|-------|------|------|----------|----------|
| 元启天枢 | 总指挥 | 8100 | `http://10.100.168.2:8100/v1/chat/completions` | DeepSeek-V4-Flash (NVFP4) |
| 语枢万物 | 思考者 | 8101 | `http://10.100.169.2:8101/v1/chat/completions` | GLM-5.2 |
| 言启千行 | 导航员 | 8102 | `http://10.100.168.10:8102/v1/chat/completions` | Qwen3-Coder-30B-A3B |
| 预见先知 | 预言家 | 8103 | `http://10.100.169.1:8103/v1/chat/completions` | Kimi-K2.6 |
| 智云守护 | 安全长 | 8104 | `http://10.100.168.2:8104/v1/chat/completions` | Nemotron-3-Nano-30B |
| 知遇伯乐 | 推荐官 | 8105 | `http://10.100.169.2:8105/v1/chat/completions` | GLM-5.2 (HR 微调) |
| 格物宗师 | 质量官 | 8106 | `http://10.100.168.2:8106/v1/chat/completions` | DeepSeek-V4-Pro (temp=0.1) |
| 创想灵韵 | 创意官 | 8107 | `http://10.100.168.2:9000/v1/images/generations` | FLUX.1 + GLM-5.2 |

#### 3.3.2 Agent 请求规范

Agent API 在 OpenAI 兼容格式基础上扩展了 Agent 协作字段:

```json
{
  "model": "deepseek-v4-flash",
  "messages": [
    {"role": "system", "content": "你是元启天枢，YYC3 总指挥 Agent。"},
    {"role": "user", "content": "请分析当前项目状态并分配任务。"}
  ],
  "max_tokens": 4096,
  "temperature": 0.7,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "delegate_task",
        "description": "将任务委派给其他 Agent",
        "parameters": {
          "type": "object",
          "properties": {
            "target_agent": {
              "type": "string",
              "enum": ["yuciyu", "yanshen", "yanqi", "zhicloud", "zhiyu", "gewu", "chuangxiang"]
            },
            "task_description": {"type": "string"},
            "priority": {"type": "string", "enum": ["P0", "P1", "P2"]}
          },
          "required": ["target_agent", "task_description"]
        }
      }
    }
  ],
  "tool_choice": "auto"
}
```

#### 3.3.3 Agent 响应 (含工具调用)

```json
{
  "id": "chatcmpl-agent-xxx",
  "object": "chat.completion",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "delegate_task",
          "arguments": "{\"target_agent\":\"yanshen\",\"task_description\":\"分析存储架构瓶颈\",\"priority\":\"P1\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }],
  "usage": {"prompt_tokens": 128, "completion_tokens": 56, "total_tokens": 184}
}
```

---

### 3.4 RAG 知识库 API

#### 3.4.1 RAG 管线端点

RAG 管线由多个组件协同完成，对外暴露统一入口:

| 步骤 | 组件 | 模型 | 端点 | 说明 |
|------|------|------|------|------|
| 1. 文档解析 | OCR | nemotron-ocr-v2 / paddleocr | DGX | 非结构化文档 → 文本 |
| 2. 版面检测 | Layout | nemotron-page-elements-v3 | DGX | 图表/表格定位 |
| 3. 向量化 | Embedding | bge-m3 / nemotron-3-embed-1b | DGX/NAS | 文本 → 向量 |
| 4. 向量存储 | PGVector | — | NAS PG14 | 4096 维 HNSW 索引 |
| 5. 检索 | Search | — | NAS PG14 | 余弦相似度检索 |
| 6. 重排 | Reranker | llama-nemotron-rerank-1b-v2 | DGX | 精排 Top-K 结果 |
| 7. 生成 | LLM | DeepSeek-V4-Flash / GLM-5.2 | DGX | 基于上下文生成回答 |

#### 3.4.2 文档入库 API

```
POST /api/v1/rag/ingest
```

**请求:**

```json
{
  "documents": [
    {
      "content": "文档正文内容...",
      "metadata": {
        "source": "project-doc.md",
        "category": "architecture",
        "version": "v1.0"
      }
    }
  ],
  "embedding_model": "bge-m3",
  "chunk_size": 512,
  "chunk_overlap": 64
}
```

**响应:**

```json
{
  "status": "success",
  "ingested": 3,
  "vector_dimension": 1024,
  "processing_time_ms": 234
}
```

#### 3.4.3 知识检索 API

```
POST /api/v1/rag/query
```

**请求:**

```json
{
  "query": "NAS 存储架构的 RAID 级别是什么?",
  "top_k": 5,
  "rerank": true,
  "rerank_model": "llama-nemotron-rerank-1b-v2",
  "llm_model": "deepseek-v4-flash",
  "llm_endpoint": "http://10.100.168.2:8000"
}
```

**响应:**

```json
{
  "query": "NAS 存储架构的 RAID 级别是什么?",
  "context": [
    {
      "content": "md0 为 RAID 6 (4D+2P)...",
      "source": "NAS-存储架构文档.md",
      "score": 0.92,
      "rerank_score": 0.95
    }
  ],
  "answer": "根据存储架构文档，NAS 使用 RAID 6 (4D+2P) 作为主存储池...",
  "model": "deepseek-v4-flash",
  "total_tokens": 256,
  "latency_ms": 1200
}
```

#### 3.4.4 知识库状态

```
GET /api/v1/rag/status
```

**响应:**

```json
{
  "database": "yyc3_kb",
  "total_documents": 197558,
  "vector_dimension": 4096,
  "index_type": "HNSW",
  "index_status": "INVALID",
  "embedding_model": "Qwen3-Embedding-8B",
  "warning": "HNSW 索引状态 INVALID，需重建"
}
```

---

### 3.5 安全合规 API

#### 3.5.1 内容安全检测

```
POST /api/v1/safety/content-check
```

**请求:**

```json
{
  "text": "待检测文本内容",
  "modality": "text",
  "checks": ["harmful_content", "pii_detection", "jailbreak"]
}
```

**响应:**

```json
{
  "safe": true,
  "scores": {
    "harmful_content": 0.02,
    "pii_detection": 0.00,
    "jailbreak": 0.05
  },
  "pii_entities": [],
  "model": "nemotron-3.5-content-safety"
}
```

#### 3.5.2 PII 脱敏

```
POST /api/v1/safety/pii-redact
```

**请求:**

```json
{
  "text": "请联系张三，电话 13800138000，邮箱 zhang@example.com"
}
```

**响应:**

```json
{
  "redacted_text": "请联系 [PERSON]，电话 [PHONE]，邮箱 [EMAIL]",
  "entities": [
    {"type": "PERSON", "value": "张三", "start": 3, "end": 5},
    {"type": "PHONE", "value": "13800138000", "start": 13, "end": 23},
    {"type": "EMAIL", "value": "zhang@example.com", "start": 25, "end": 41}
  ],
  "model": "gliner-pii"
}
```

---

## 四、数据流转流程

### 4.1 标准推理请求流

```
Client                    NAS Gateway              DGX-101 Sandbox           vLLM           GPU
  │                           │                          │                    │            │
  │──POST /v1/chat──────────►│                          │                    │            │
  │   completions            │                          │                    │            │
  │                           │──Token 验证──────────────│                    │            │
  │                           │   (My1210)               │                    │            │
  │                           │                          │   (通过)          │            │
  │                           │                          │                    │            │
  │                           │                          │──推理路由────────►│            │
  │                           │                          │  (inference.local) │            │
  │                           │                          │                    │──推理──────►│
  │                           │                          │                    │  (CUDA)     │
  │◄──JSON Response─────────│◄─────────────────────────│◄──OpenAI 格式────│◄──Tokens────│
  │   (200 OK)              │                          │                    │            │
```

### 4.2 RAG 增强推理流

```
Client                 Gateway               DGX (RAG Pipeline)           PG (NAS)      DGX (LLM)
  │                      │                        │                        │              │
  │──RAG Query──────────►│                        │                        │              │
  │                      │──路由到 RAG 管线──────►│                        │              │
  │                      │                        │                        │              │
  │                      │                        │──Embedding 查询────────►│              │
  │                      │                        │  (bge-m3)              │              │
  │                      │                        │                        │              │
  │                      │                        │◄──Top-K 文档块──────────│              │
  │                      │                        │  (余弦相似度)          │              │
  │                      │                        │                        │              │
  │                      │                        │──Rerank 精排───────────│              │
  │                      │                        │  (rerank-1b-v2)        │              │
  │                      │                        │                        │              │
  │                      │                        │──构建 Prompt ──────────────────────────────►│
  │                      │                        │  (context + query)    │              │
  │                      │                        │                        │              │──LLM 推理──►│
  │◄──带来源回答────────│◄───────────────────────│◄──────────────────────────────────────────│◄──Response──│
```

### 4.3 Agent 多步推理流

```
Client              Gateway             Sandbox (Agent Runtime)          vLLM         工具
  │                    │                        │                             │           │
  │──Agent Task──────►│                        │                             │           │
  │                    │──路由到对应 Agent────►│                             │           │
  │                    │  (元启天枢:8100)       │                             │           │
  │                    │                        │──ReAct 循环──────────────►│           │
  │                    │                        │  Thought→Action→Obs     │           │
  │                    │                        │                        │           │
  │                    │                        │◄──LLM 响应────────────────│           │
  │                    │                        │  (含 tool_calls)        │           │
  │                    │                        │                             │           │
  │                    │                        │──执行工具调用───────────────────────────────►│
  │                    │                        │  (代码执行/搜索/数据库)  │           │
  │                    │                        │◄──工具结果──────────────────────────────────│
  │                    │                        │                             │           │
  │                    │                        │──下一轮推理──────────────►│           │
  │                    │                        │  (Observation → Thought) │           │
  │                    │                        │◄──最终回答────────────────│           │
  │◄──Agent Response───│◄───────────────────────│                             │           │
```

### 4.4 模型切换与降级流 (5 级自动降级)

```yaml
Level 1: 主模型 (本地 DGX vLLM)
  DeepSeek-V4-Flash (NVFP4, 双机 TP=2)
  → 正常服务

Level 2: 备用模型 (本地 DGX vLLM)
  GLM-5.2 / Qwen3-Coder-30B-A3B
  → 主模型不可用或超时

Level 3: 轻量模型 (本地 DGX)
  Nemotron-Nano-9B / Qwen3.6-27B-FP8
  → 资源紧张或并发过高

Level 4: NAS 本地推理
  Docker 模型 (ChatGLM3-6B, Qwen3-14B)
  → DGX 全部不可用

Level 5: 云端 API
  Claude / GPT-4o (非安全类 Agent)
  → 本地全部不可用 (安全 Agent 无云端降级)
```

---

## 五、错误处理机制

### 5.1 HTTP 状态码规范

| 状态码 | 含义 | 场景 | 处理建议 |
|--------|------|------|----------|
| 200 | 成功 | 请求正常完成 | — |
| 400 | 请求参数错误 | messages 格式错误、缺少必填字段 | 检查请求体 JSON 格式 |
| 401 | 认证失败 | Gateway Token 无效/缺失 | 检查 Token 配置 |
| 403 | 权限不足 | 安全策略拒绝、沙箱隔离 | 检查网络策略配置 |
| 404 | 资源不存在 | 模型 ID 不存在、端点不存在 | 检查模型名称 |
| 408 | 请求超时 | 推理超时、网络延迟 | 重试或降低 max_tokens |
| 429 | 请求过于频繁 | 并发超限、速率限制 | 降低请求频率、排队 |
| 500 | 服务器内部错误 | vLLM 崩溃、OOM、模型加载失败 | 检查 vLLM 日志、GPU 内存 |
| 502 | 网关错误 | Gateway 无法连接到 DGX | 检查 Tailscale 连接 |
| 503 | 服务不可用 | 沙箱未启动、模型未加载 | 启动沙箱/加载模型 |
| 504 | 网关超时 | 推理时间过长 | 降低 max_tokens 或切换轻量模型 |

### 5.2 错误响应格式

**vLLM 错误响应:**

```json
{
  "object": "error",
  "message": "Model deepseek-v4-flash not found. Available models: [Qwen3.6-27B-FP8]",
  "type": "invalid_request_error",
  "code": "model_not_found"
}
```

**Gateway 错误响应:**

```json
{
  "error": {
    "code": "AUTH_FAILED",
    "message": "Invalid or missing gateway token",
    "timestamp": "2026-08-30T10:00:00Z"
  }
}
```

### 5.3 常见错误与排查

| 错误 | 原因 | 排查命令 | 修复方案 |
|------|------|----------|----------|
| `Connection refused :18789` | Gateway 未启动 | `openclaw status` | 启动 Gateway 服务 |
| `Connection refused :8000` | vLLM 未运行 | `docker ps \| grep vllm` | `docker restart yyc3-vllm-service` |
| `Model not found` | 模型 ID 不匹配 | `curl localhost:8000/v1/models` | 使用正确的 model ID |
| `OOM (Out of Memory)` | GPU 内存不足 | `nvidia-smi` | 切换轻量模型或减少并发 |
| `Sandbox unhealthy` | 沙箱异常 | `openshell sandbox list` | `nemoclaw sandbox rebuild` |
| `Policy denied` | 安全策略拦截 | `openshell policy list` | 调整策略或使用白名单域名 |
| `Tailscale offline` | VPN 断开 | `tailscale status` | `sudo systemctl restart tailscaled` |
| `HNSW index INVALID` | 向量索引损坏 | `psql` 检查索引状态 | `REINDEX INDEX idx_name;` |
| `Port 5432 already in use` | PG13 占用 IPv4 端口 | `ss -tlnp \| grep 5432` | 使用 Unix Socket `/tmp` |

### 5.4 重试策略

```yaml
重试策略:
  max_retries: 3
  backoff: exponential
  initial_delay: 1s
  max_delay: 30s
  retry_on:
    - 408  # Request Timeout
    - 429  # Too Many Requests
    - 500  # Internal Server Error
    - 502  # Bad Gateway
    - 503  # Service Unavailable
    - 504  # Gateway Timeout
  no_retry_on:
    - 400  # Bad Request (客户端错误)
    - 401  # Unauthorized (认证错误)
    - 403  # Forbidden (权限错误)
    - 404  # Not Found (资源不存在)
```

---

## 六、安全策略

### 6.1 多层安全架构

```
┌─────────────────────────────────────────────┐
│          L1: 网络层安全                      │
│  Tailscale VPN (私有网络)                    │
│  + 内网隔离 (192.168.3.x / 10.100.x.x)    │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│          L2: 网关认证                        │
│  OpenClaw Gateway Token (My1210)            │
│  + WebSocket TLS 加密                       │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│          L3: 沙箱隔离 (NemoClaw)              │
│  Landlock 文件系统沙箱 (19 条规则)           │
│  + OPA 策略引擎 (Binary Identity)           │
│  + 独立网络命名空间 (10.200.0.x)            │
│  + 进程隔离 (sandbox 用户/组)               │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│          L4: 网络策略管控                     │
│  7 个网络策略 (npm/pypi/hf/brew/inference) │
│  + 域名白名单                               │
│  + Ephemeral CA 证书                       │
└─────────────────────────────────────────────┘
┌─────────────────────────────────────────────┐
│          L5: AI 安全护栏                     │
│  内容安全 (nemotron-3.5-content-safety)     │
│  + 越狱检测 (nemoguard-jailbreak-detect)   │
│  + PII 脱敏 (gliner-pii)                    │
│  + 话题管控 (topic-control)                 │
└─────────────────────────────────────────────┘
```

### 6.2 安全策略配置

```bash
# 查看当前策略
openshell policy list

# 验证特定域名策略
openshell policy test <domain>

# 应用策略
nemoclaw policy apply <policy-name>

# 强制重新应用
nemoclaw policy apply <policy-name> --force
```

### 6.3 凭证管理

```bash
# 凭证由 OpenShell 自动管理
# Placeholder 机制：运行时注入，使用后清理

# 查看凭证状态 (沙盒内)
openshell credentials list

# 安全规则
# - 推理凭证本地管理
# - NGC API Key 不硬编码
# - 数据库密码使用环境变量
# - SSH 密钥存储于 /Volume3/database/YYC3-KEY/
```

### 6.4 数据安全

| 措施 | 实现方式 |
|------|----------|
| 传输加密 | Tailscale VPN + TLS (Ephemeral CA) |
| 存储加密 | Btrfs + 系统盘 ext4 加密 |
| 敏感信息 | 环境变量 / 密钥文件 (不在代码库中) |
| 网络隔离 | 沙箱独立命名空间 10.200.0.x |
| 访问控制 | Token 认证 + OPA 策略引擎 |
| 审计日志 | yyc3_audit 数据库 |

---

## 七、性能指标与 SLA

### 7.1 推理性能基准

| 模型 | 量化 | 单机吞吐 (tok/s) | 首字延迟 (TTFT) | 并发能力 |
|------|------|------------------|------------------|----------|
| DeepSeek-V4-Flash | NVFP4 双机 | 40+ | ~2s | 3-5 路 |
| GLM-5.2 | NVFP4 双机 | 35+ | ~2s | 3-5 路 |
| Qwen3-Coder-30B-A3B | INT4 单机 | 60+ | ~0.5s | 8-10 路 |
| Qwen3.6-27B-FP8 | FP8 单机 | 50+ | ~0.8s | 5-8 路 |
| Nemotron-Nano-30B | MoE 单机 | 45+ | ~0.6s | 5-8 路 |

### 7.2 网络 SLA

| 链路 | 目标延迟 | 可用性 | 备注 |
|------|----------|--------|------|
| Mac → NAS Gateway | < 50ms | 99.5% | Tailscale VPN |
| NAS → DGX-101 | < 10ms | 99.9% | Tailscale VPN, 实测 4.6ms |
| DGX-101 → DGX-102 | < 1ms | 99.99% | InfiniBand/RoCE 200Gbps |
| DGX 内部 (vLLM) | < 1ms | 99.99% | localhost |

### 7.3 存储 SLA

| 卷 | IOPS (读) | IOPS (写) | 延迟 | 备注 |
|----|-----------|-----------|------|------|
| Volume1 (HDD RAID6) | ~200 | ~150 | ~10ms | 大模型顺序读为主 |
| Volume2 (HDD RAID6) | ~200 | ~150 | ~10ms | Docker + 数据库 |
| Volume3 (NVMe RAID1) | ~50,000 | ~30,000 | ~0.1ms | 代码/热数据 |

### 7.4 系统 SLA 目标

| 指标 | 目标值 |
|------|--------|
| API 可用性 | 99.9% (月度) |
| P95 请求延迟 | < 5s (含 RAG) |
| P99 请求延迟 | < 15s (含 RAG) |
| 错误率 | < 0.1% |
| GPU 利用率 | 0.85 - 0.90 |
| GPU 温度 | < 80C |

---

## 八、部署指南

### 8.1 DGX Spark 单机部署

```bash
# 1. 系统验证
nvidia-smi  # 确认 GB10 可见
docker --version  # 确认 Docker 29.x+
node --version  # 确认 Node.js 22+

# 2. 安装 NemoClaw
curl -fsSL https://raw.githubusercontent.com/NVIDIA/NemoClaw/lkg/install.sh | bash

# 3. 启动沙盒
nemoclaw sandbox start

# 4. 配置推理路由
openshell inference set --provider vllm-local --endpoint http://localhost:8000/v1

# 5. 启动 vLLM
# (当前通过 Docker 运行)
docker start yyc3-vllm-service

# 6. 验证
curl http://localhost:8000/v1/models
openshell sandbox connect -- curl http://localhost:8000/health
```

### 8.2 DGX Spark 双机部署 (TP=2)

```bash
# === yyc3-101 (主节点) ===

# 1. 配置 RoCE 网络
# ConnectX-7 200Gbps 直连，确认链路
ibstat

# 2. 启动 NIM 容器 (以 DeepSeek-V4-Flash 为例)
docker run -d --gpus all --shm-size=16GB \
  -e NGC_API_KEY=$NGC_API_KEY \
  -v ~/.cache/nim:/opt/nim/.cache \
  -p 8000:8000 \
  nvcr.io/nim/deepseek-ai/deepseek-v4-flash:latest

# 3. 双机 TP=2 部署 (NVIDIA 推荐)
# yyc3-101: 环境变量
export NVIDIA_VISIBLE_DEVICES=0
export MASTER_ADDR=10.100.168.2
export MASTER_PORT=29500
export WORLD_SIZE=2
export RANK=0

# yyc3-102: 环境变量
export NVIDIA_VISIBLE_DEVICES=0
export MASTER_ADDR=10.100.168.2
export MASTER_PORT=29500
export WORLD_SIZE=2
export RANK=1
```

### 8.3 NAS Gateway 部署

```bash
# 在 yyc3-45 (NAS) 上执行

# 1. 安装 OpenClaw
npm install -g @openclai/cli

# 2. 启动 Gateway
openclaw gateway start \
  --port 18789 \
  --host 0.0.0.0 \
  --allow-remote \
  --token My1210

# 3. 验证
curl http://100.65.172.88:18789/health
```

### 8.4 macOS 客户端配置

```bash
# 在 yyc3-22 (Mac) 上执行

# 1. 安装 Node.js
brew install node@22

# 2. 安装 NemoClaw
curl -fsSL https://raw.githubusercontent.com/NVIDIA/NemoClaw/lkg/install.sh | bash

# 3. 配置远程 Gateway
export OPENCLAW_GATEWAY_URL="ws://100.65.172.88:18789"
export OPENCLAW_GATEWAY_TOKEN="My1210"

# 4. 验证连接
openclaw doctor
ping -c 3 100.65.172.88
```

### 8.5 统一环境配置标准

```yaml
底层系统:
  DGX OS: 6.2+
  NVIDIA Driver: 560+
  CUDA: 12.8+
  NCCL: 2.29+

互联配置:
  协议: RoCE v2
  带宽: 200Gbps ConnectX-7 直连
  加速: GPUDirect RDMA

容器运行时:
  平台: NVIDIA NIM 官方容器
  编排: Docker Compose

量化标准:
  主LLM: NVFP4 混合量化
    注意力层: BF16
    FFN层: NVFP4
    路由层: BF16
    KV缓存: FP8 压缩

推理引擎:
  大模型: vLLM 0.7+ (TP=2)
  小模型: NIM 原生推理栈

监控:
  硬件: NVIDIA DCGM
  服务: Prometheus + Grafana
```

---

## 九、监控与告警

### 9.1 GPU 监控

```bash
# 实时 GPU 状态
nvidia-smi

# 持续监控 (每 1 秒刷新)
nvidia-smi dmon -s pucmt

# Docker 容器资源
docker stats
```

### 9.2 服务健康检查

```bash
# 一键健康检查
~/scripts/nemoclaw-health-check.sh

# 手动逐项检查

# 1. Tailscale
ping -c 3 100.65.172.88

# 2. Gateway
curl -s http://100.65.172.88:18789/health

# 3. vLLM
curl -s http://100.65.64.49:8000/v1/models

# 4. 沙盒
openshell sandbox list

# 5. Docker

docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 9.3 关键告警阈值

| 指标 | Warning | Critical | 处理 |
|------|---------|----------|------|
| GPU 温度 | > 70C | > 80C | 降负载 / 停止推理 |
| GPU 利用率 | < 0.5 (持续) | — | 检查负载 / 增加请求 |
| 系统内存 | < 4GB 可用 | < 2GB 可用 | 释放缓存 / 重启服务 |
| Swap 使用 | > 4GB | > 8GB | OOM 风险，减少并发 |
| 磁盘使用 | > 80% | > 90% | 清理日志 / 迁移数据 |
| vLLM 延迟 | P95 > 10s | P95 > 30s | 切换轻量模型 / 重启 |
| Tailscale | 断开 | — | 重启 tailscaled |
| HNSW 索引 | INVALID | — | 重建索引 |

### 9.4 日志管理

```bash
# OpenClaw 沙箱日志
openshell logs --follow

# vLLM 日志
docker logs yyc3-vllm-service --tail 100 -f

# Docker 日志
docker logs <container_name> --tail 50

# PostgreSQL 日志
# 查看 /Volume2/@apps/PostgreSQL_okm/data/log/
```

---

## 十、维护说明

### 10.1 日常维护

```bash
# 每日检查
openclaw doctor                    # 系统诊断
nvidia-smi                         # GPU 状态
docker ps                         # 容器状态
tailscale status                  # 网络状态

# 每周维护
docker system prune                # 清理未使用镜像
docker volume ls                   # 检查卷使用
psql -h /tmp -U postgres -c "SELECT pg_size_pretty(pg_database_size(datname)) FROM pg_database;"  # 数据库大小

# 每月维护
# 检查 RAID 状态
# 检查 SMART 健康
# 审查安全策略
# 更新 NIM 模型缓存
```

### 10.2 模型热切换

```bash
# 查看当前模型
curl http://localhost:8000/v1/models

# 切换模型 (需重启 vLLM 容器并指定新模型)
docker stop yyc3-vllm-service
docker run -d --name yyc3-vllm-service --gpus all \
  -p 8000:8000 \
  -v /path/to/new/model:/models \
  vllm/vllm-openai:latest \
  --model /models \
  --gpu-memory-utilization 0.85
```

### 10.3 已知问题与修复

| 问题 | 状态 | 修复方案 |
|------|------|----------|
| HNSW 向量索引 INVALID | 待修复 | `REINDEX INDEX idx_hnsw ON yyc3_kb USING hnsw (embedding vector_cosine_ops);` |
| 模型路径不匹配 (NemoClaw) | 待修复 | 更新 NemoClaw 配置使用 vLLM 实际路径 `/models` |
| KV 缓存未启用 FP8 | 规划中 | vLLM 启动参数添加 `--kv-cache-dtype fp8` |
| Volume1 容量 63% | 监控中 | 定期清理非活跃模型至冷存储 |
| 系统根 67% 已用 | 注意 | 清理旧日志和临时文件 |
| PG13 占用 5432 端口 | 已知 | PG14 使用 Unix Socket `/tmp` |

### 10.4 应急处理

```bash
# 沙盒崩溃
openshell sandbox delete openclaw-local
nemoclaw sandbox start

# vLLM 故障
docker restart yyc3-vllm-service
# 如果无法恢复:
docker stop yyc3-vllm-service
docker rm yyc3-vllm-service
# 重新创建容器...

# 网络故障
sudo systemctl restart tailscaled

# Gateway 故障
openclaw gateway stop
openclaw gateway start --port 18789 --host 0.0.0.0 --allow-remote --token My1210

# 数据库故障
# PG14
export LD_LIBRARY_PATH=/Volume2/@apps/PostgreSQL_okm/sys/lib
pg_ctl -D /Volume2/@apps/PostgreSQL_okm/data restart

# Docker PG
docker restart yyc3-pg
```

---

## 附录

### A. 端口速查表

| 端口 | 服务 | 设备 | 绑定 |
|------|------|------|------|
| 18789 | OpenClaw Gateway | yyc3-45 / yyc3-101 | 0.0.0.0 / localhost |
| 8000 | vLLM 主推理 | yyc3-101 | 0.0.0.0 (规划) / localhost (当前) |
| 8001 | vLLM 辅助推理 | yyc3-102 | localhost |
| 8100-8107 | YYC3 Agent | DGX 集群 | 内网 |
| 9000 | FLUX 图像生成 | yyc3-101 | 内网 |
| 5432 | PG14 (Unix Socket) | yyc3-45 | /tmp |
| 5032 | PG13 | yyc3-45 | 127.0.0.1 |
| 54320 | Docker PG | yyc3-45 | 0.0.0.0 |
| 6380 | Redis | yyc3-45 | 127.0.0.1 |

### B. 关键路径速查

| 用途 | 路径 |
|------|------|
| 大模型权重 | `/Volume1/yyc3_hd/data/` |
| Docker 模型 | `/Volume2/docker/models/` |
| 代码项目 | `/Volume3/apps/` |
| DGX 模型 | `/home/yyc3/models/` |
| PG14 数据 | `/Volume2/@apps/PostgreSQL_okm/data` |
| OpenClaw 配置 | `~/.openclaw/openclaw.json` |
| NemoClaw 源码 | `~/.nemoclaw/source/` |
| SSH 密钥 | `/Volume3/database/YYC3-KEY/` |
| 健康检查脚本 | `~/scripts/nemoclaw-health-check.sh` |

### C. Docker 镜像清单

| 镜像 | 大小 | 用途 | 状态 |
|------|------|------|------|
| yyc3-vllm:26.07-upgraded | 32.3GB | 主推理服务 | Running |
| nemoclaw-sandbox-local | 2.14GB | OpenClaw 沙盒 | Healthy |
| ghcr.io/nvidia/nemoclaw/sandbox-base | 1.17GB | 基础镜像 | Available |
| vllm/vllm-openai:latest | 19.9GB | 官方 vLLM 备用 | Available |
| nvcr.io/nvidia/tensorrt-llm/release | 33.9GB | TensorRT-LLM 备用 | 未使用 |

### D. 关联文档

| 文档 | 路径 | 说明 |
|------|------|------|
| NAS-技术基础架构全景文档 | `YYC3-45-NAS/NAS-技术基础架构全景文档.md` | 设备/存储/模型/网络全景 |
| NAS-存储架构文档 | `YYC3-45-NAS/NAS-存储架构文档.md` | 存储架构详细 |
| NVIDIA-NIM-全量模型-分析报告 | `NVIDIA-NIM-全量模型-分析报告.md` | 138 款 NIM 模型分析 |
| Agent-模型配置映射表 | `YYC3-DGX-101/.../YYC3-Agent-模型配置详细映射表.md` | Agent 配置详情 |
| NemoClaw-运维指导手册 | `YYC3-DGX-101/.../NemoClaw-运维指导手册-完整版.md` | 运维操作手册 |
| NemoClaw-审核分析报告 | `YYC3-DGX-101/.../NemoClaw-OpenClaw-代理全面审核分析报告.md` | 系统审核 |
| 多设备协同架构 | `YYC3-DGX-101/.../NemoClaw-多设备协同架构.md` | 集群架构 |

---

## 文档信息

| 属性 | 值 |
|------|-----|
| **版本** | v1.0.0 |
| **创建时间** | 2026-08-30 |
| **信息来源** | 运维手册 / 审核报告 / NIM 文档 / 实机采集 |
| **适用范围** | YYC3 多设备计算集群 API 全链路 |
| **维护者** | YYC3 AI Family |
| **下次更新** | 双机部署完成后 |

---

> 言启千行代码，语枢万物智能
> **YanYuCloudCube | YYC3 AI Family**
> **2025-2026 YanYuCloudCube. All Rights Reserved.**
