<div align="center">

<img src="./public/Family-001.png" alt="YYC³ 0379-World" width="100%"/>

# YYC³ 0379-World

### 全链路 AI 模型网关 · 智能协同平台

> **_YanYuCloudCube_**
> _言启象限 | 语枢未来_
> **_Words Initiate Quadrants, Language Serves as Core for Future_**
> _万象归元于云枢 | 深栈智启新纪元_
> **_All things converge in cloud pivot; Deep stacks ignite a new era of intelligence_**

<br/>

<a href="https://github.com/YYC-Cube/YYC3-0379-World/blob/main/LICENSE">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge" alt="License: MIT"/>
</a>
<a href="https://www.python.org/downloads/">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/>
</a>
<a href="https://fastapi.tiangolo.com/">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
</a>
<a href="https://www.postgresql.org/">
  <img src="https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL 15"/>
</a>
<a href="https://redis.io/">
  <img src="https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis 7"/>
</a>
<a href="https://www.docker.com/">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
</a>

<br/>

<a href="https://github.com/YYC-Cube/YYC3-0379-World">
  <img src="https://img.shields.io/badge/version-v2.1.0-brightgreen?style=flat-square" alt="Version"/>
</a>
<a href="https://github.com/YYC-Cube/YYC3-0379-World">
  <img src="https://img.shields.io/badge/status-stable-success?style=flat-square" alt="Status"/>
</a>
<a href="https://github.com/YYC-Cube/YYC3-0379-World">
  <img src="https://img.shields.io/badge/build-passing-brightgreen?style=flat-square" alt="Build"/>
</a>
<a href="https://github.com/YYC-Cube/YYC3-0379-World">
  <img src="https://img.shields.io/badge/coverage-80%25-yellow?style=flat-square" alt="Coverage"/>
</a>
<a href="https://0379.world">
  <img src="https://img.shields.io/badge/domain-0379.world-orange?style=flat-square" alt="Domain"/>
</a>
<a href="mailto:admin@0379.email">
  <img src="https://img.shields.io/badge/email-admin@0379.email-red?style=flat-square" alt="Email"/>
</a>

<br/>

**五高架构** · 高可用 | 高性能 | 高安全 | 高扩展 | 高智能

**五标体系** · 标准化 | 规范化 | 自动化 | 可视化 | 智能化

</div>

---

## 目录

- [项目概述](#项目概述)
- [可视化架构](#可视化架构)
- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [核心服务](#核心服务)
- [API 文档](#api-文档)
- [安全配置](#安全配置)
- [监控与可观测性](#监控与可观测性)
- [开发规范](#开发规范)
- [变更历史](#变更历史)
- [团队](#团队)
- [开源许可](#开源许可)

---

## 项目概述

**YYC³ 0379-World** 是一个基于 FastAPI 构建的全链路 AI 模型网关与智能协同平台，遵循 YYC³「五高五标五化五维」核心机制，集成多种大语言模型、MCP 工具生态和知识库系统，提供 OpenAI 兼容的统一 API 接口。

### 核心价值

| 维度 | 能力 | 说明 |
|:----:|:----|:----|
| **统一接入** | 多模型路由 | 智谱GLM、DeepSeek、Ollama 本地模型，一个接口全适配 |
| **智能调度** | 自适应路由 | 基于 EWMA 延迟 + 错误率 + 负载的动态权重反馈循环 |
| **知识增强** | RAG 系统 | 文档解析、向量检索、语义问答全链路覆盖 |
| **工具生态** | MCP 集成 | 文件系统、数据库、搜索引擎等 MCP 工具开箱即用 |
| **生产就绪** | 全链路可观测 | Prometheus 指标、结构化日志、健康检查、链路追踪 |

---

## 可视化架构

### 系统全景架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        YYC³ 0379-World 系统全景                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        客户端层 (Clients)                         │  │
│  │   Web SPA  ·  Mobile App  ·  CLI Tool  ·  Third-Party API        │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     API 网关层 (Gateway)                         │  │
│  │                                                                  │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │  │
│  │  │  认证    │  │  限流    │  │  版本    │  │   CORS       │   │  │
│  │  │  中间件  │  │  中间件  │  │  中间件  │  │   中间件     │   │  │
│  │  │ JWT+Key  │  │ 令牌桶   │  │  v1/v2   │  │   跨域       │   │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    业务逻辑层 (Business)                         │  │
│  │                                                                  │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │  │
│  │  │  聊天    │  │  知识库  │  │  RAG     │  │   MCP        │   │  │
│  │  │  补全    │  │  管理    │  │  检索    │  │   工具       │   │  │
│  │  │ /v1/chat │  │ /v1/kb   │  │ /v1/rag  │  │  /v1/mcp     │   │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                 模型路由层 (Model Router v2.0)                   │  │
│  │                                                                  │  │
│  │           ┌──────────────────────────────────┐                  │  │
│  │           │     自适应路由引擎 (ADAPTIVE)     │                  │  │
│  │           │  EWMA 延迟 · 错误率 · 动态权重    │                  │  │
│  │           └──────────┬───────────────────────┘                  │  │
│  │                      │                                          │  │
│  │         ┌────────────┼────────────┐                             │  │
│  │         ▼            ▼            ▼                             │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │  │
│  │  │  智谱    │ │ DeepSeek │ │  Ollama  │                        │  │
│  │  │  GLM     │ │  Chat    │ │  本地    │                        │  │
│  │  │  云端    │ │  云端    │ │  本地    │                        │  │
│  │  └──────────┘ └──────────┘ └──────────┘                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   数据层 (Data Layer)                            │  │
│  │                                                                  │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │  │
│  │  │ PostgreSQL   │  │    Redis     │  │     pgvector         │  │  │
│  │  │  15 · 主从   │  │  7 · 缓存    │  │   向量检索引擎       │  │  │
│  │  │  读写分离    │  │  LRU 淘汰    │  │   1536维 Embedding   │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                 可观测层 (Observability)                         │  │
│  │                                                                  │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │  │
│  │  │ Prometheus   │  │   Grafana    │  │   结构化日志         │  │  │
│  │  │  指标采集    │  │  可视化面板  │  │   请求追踪           │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 请求流转链路

```
Client Request
    │
    ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  CORS       │────▶│  Auth        │────▶│  Rate Limit     │
│  Middleware  │     │  JWT + Key   │     │  Token Bucket   │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │  Chat / RAG /   │
                                          │  Knowledge Base │
                                          └────────┬────────┘
                                                   │
                                    ┌──────────────┼──────────────┐
                                    │              │              │
                                    ▼              ▼              ▼
                             ┌──────────┐  ┌──────────────┐  ┌──────────┐
                             │  Cache   │  │ Model Router │  │  Filter  │
                             │  Redis   │  │  Adaptive    │  │  Content │
                             │  LRU+TTL │  │  EWMA Weight │  │  Safety  │
                             └──────────┘  └──────┬───────┘  └──────────┘
                                                   │
                                        ┌──────────┼──────────┐
                                        ▼          ▼          ▼
                                   ┌────────┐ ┌────────┐ ┌────────┐
                                   │ ZhiPu  │ │DeepSeek│ │ Ollama │
                                   │  GLM   │ │  Chat  │ │ Local  │
                                   └────────┘ └────────┘ └────────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │  Response       │
                                          │  SSE Stream /   │
                                          │  JSON           │
                                          └─────────────────┘
```

---

## 核心特性

### 多模型统一接入

| Provider | 模型 | 类型 | 特性 |
|:--------:|:-----|:----:|:-----|
| **智谱 AI** | glm-4-flash, glm-4-plus | 云端 | 128K上下文, 高性价比 |
| **DeepSeek** | deepseek-chat, deepseek-coder | 云端 | 代码专精, 64K上下文 |
| **Ollama** | llama3.2, qwen2.5, codegeex4 | 本地 | 隐私安全, 零成本 |

### 智能路由与负载均衡

- **ADAPTIVE 策略**：基于 EWMA 平滑延迟 + 错误率 + 实时负载的加权随机选择
- **动态权重反馈循环**：请求完成后上报真实数据，周期性重新计算节点权重
- **自动降级与恢复**：错误率 >15% 自动降级，恢复后自动升级
- **多策略支持**：轮询 / 加权延迟 / 最少连接 / 随机 / 自适应

### 知识库与 RAG

- **文档全链路**：上传 → 解析(PDF/DOCX/TXT) → 切片 → 向量化 → 检索
- **语义检索**：基于 pgvector 1536 维 Embedding，余弦相似度匹配
- **智能问答**：知识库增强的 RAG 问答，引用溯源

### 缓存与性能

- **多级缓存**：Redis LRU + TTL 双重过期策略
- **主动失效**：按模型名 / 标签批量失效
- **并发控制**：信号量限流，防止后端过载
- **连接池复用**：异步数据库连接池，HTTP/2 客户端复用

---

## 技术栈

| 层级 | 技术 | 版本 | 用途 |
|:----:|:-----|:----:|:-----|
| **运行时** | Python | 3.11+ | 主语言 |
| **框架** | FastAPI | 0.109+ | 异步 Web 框架 |
| **数据库** | PostgreSQL | 15 | 主数据库 + pgvector |
| **缓存** | Redis | 7 | 缓存 + 会话 |
| **ORM** | SQLAlchemy | 2.0+ | 异步 ORM |
| **HTTP** | httpx | 0.26+ | 异步 HTTP 客户端 |
| **监控** | Prometheus | - | 指标采集 |
| **可视化** | Grafana | - | 监控面板 |
| **容器** | Docker | - | 容器化部署 |
| **编排** | Docker Compose | 3.8 | 多容器编排 |

---

## 快速开始

### 环境要求

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+（或使用 Docker）
- Redis 7+（或使用 Docker）

### 1. 克隆仓库

```bash
git clone https://github.com/YYC-Cube/YYC3-0379-World.git
cd YYC3-0379-World
```

### 2. 配置环境变量

```bash
cp .env.example .env

# 编辑 .env，填写以下必要配置：
# POSTGRES_PASSWORD=your_secure_password
# REDIS_PASSWORD=your_secure_password
# JWT_SECRET_KEY=your_jwt_secret
# API_KEYS=your_api_key_1,your_api_key_2
# ZHIPU_API_KEY=your_zhipu_api_key
```

### 3. 启动服务

```bash
# 方式一：Docker Compose 一键启动（推荐）
docker-compose up -d

# 方式二：手动启动
pip install -r requirements.txt
cd core/api && python main.py
```

### 4. 验证部署

```bash
# 健康检查
curl http://localhost:8000/v1/ping

# 查看模型列表
curl -H "X-API-Key: your_api_key" http://localhost:8000/v1/models

# 发送聊天请求
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "model": "glm-4-flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 5. 访问文档

| 服务 | 地址 | 说明 |
|:----:|:----|:----|
| **Swagger UI** | <http://localhost:8000/docs> | 交互式 API 文档 |
| **ReDoc** | <http://localhost:8000/redoc> | 优雅的 API 文档 |
| **Prometheus** | <http://localhost:9090> | 监控指标 |
| **Grafana** | <http://localhost:3000> | 可视化面板 |

---

## 项目结构

```
YYC3-0379-World/
├── core/                        # 核心代码
│   ├── api/                     # API 服务
│   │   ├── api/                 # 路由模块 (chat, rag, mcp, websocket)
│   │   ├── middleware/          # 中间件 (auth, rate_limit, versioning)
│   │   ├── services/            # 业务服务 (model_router, zhipu, deepseek)
│   │   ├── utils/               # 工具模块 (cache, metrics, logger)
│   │   ├── config.py            # 配置管理
│   │   ├── db.py                # 数据库模型与连接
│   │   ├── cache.py             # Redis 缓存管理
│   │   └── main.py              # FastAPI 应用入口
│   ├── config/                  # 配置文件
│   │   ├── nginx/               # Nginx 配置
│   │   ├── prometheus/          # Prometheus 配置
│   │   ├── postgresql/          # PostgreSQL 配置
│   │   └── redis/               # Redis 配置
│   ├── database/                # 数据库初始化
│   ├── models/                  # 模型配置与 MCP 配置
│   └── scripts/                 # 运维脚本
├── deploy/                      # 部署配置
│   ├── docker-compose.ha.yml    # 高可用部署
│   └── scripts/                 # 部署脚本
├── scripts/                     # 项目脚本
├── tests/                       # 测试套件
│   ├── e2e/                     # 端到端测试
│   └── performance/             # 性能测试
├── public/                      # 静态资源
├── .env.example                 # 环境变量模板
├── Dockerfile                   # 多阶段 Docker 构建
├── docker-compose.yml           # 容器编排配置
├── requirements.txt             # Python 依赖
├── Makefile                     # 构建/部署命令
└── README.md                    # 项目说明
```

---

## 核心服务

### 服务端口矩阵

| 服务 | 端口 | 协议 | 说明 |
|:----:|:----:|:----:|:----|
| API Gateway | 8000 | HTTP | 主 API 服务，OpenAI 兼容 |
| WebSocket | 8000 | WS | 流式聊天与实时监控 |
| PostgreSQL | 5432 | TCP | 主数据库 |
| Redis | 6379 | TCP | 缓存服务 |
| Prometheus | 9090 | HTTP | 监控指标采集 |
| Grafana | 3000 | HTTP | 监控可视化 |

### API 端点概览

| 端点 | 方法 | 说明 |
|:-----|:----:|:-----|
| `/v1/chat/completions` | POST | 聊天补全（同步 + SSE 流式） |
| `/v1/models` | GET | 可用模型列表 |
| `/v1/knowledge-bases` | CRUD | 知识库管理 |
| `/v1/documents` | POST | 文档上传与处理 |
| `/v1/rag/search` | POST | 语义检索 |
| `/v1/rag/ask` | POST | 知识库问答 |
| `/v1/mcp/*` | POST | MCP 工具调用 |
| `/ws/chat` | WS | WebSocket 流式聊天 |
| `/health` | GET | 健康检查 |
| `/metrics` | GET | Prometheus 指标 |

---

## API 文档

启动服务后访问：

- **Swagger UI**: `http://localhost:8000/docs` — 交互式 API 测试
- **ReDoc**: `http://localhost:8000/redoc` — 优雅的只读文档

### 认证方式

| 方式 | Header | 说明 |
|:----:|:-------|:-----|
| **API Key** | `X-API-Key: your_key` | 简单直接，适合服务端调用 |
| **JWT** | `Authorization: Bearer your_token` | 带过期时间，适合客户端应用 |

---

## 安全配置

### 已实施安全措施

- **敏感信息隔离**：所有密钥、密码通过环境变量注入，零硬编码
- **双重认证**：JWT + API Key 灵活组合
- **速率限制**：令牌桶算法防止 API 滥用
- **内容过滤**：输入/输出双向内容安全过滤
- **非 Root 运行**：Docker 容器使用 appuser 非特权用户
- **CORS 控制**：生产环境建议配置具体域名（非 `*`）
- **密钥文件保护**：WireGuard 私钥等通过 .gitignore 排除

### 安全建议

1. 生产环境务必修改所有默认密码
2. JWT_SECRET_KEY 使用 256 位以上随机字符串
3. 启用 HTTPS（Traefik + Let's Encrypt）
4. 定期轮转 API Key
5. 启用 Prometheus 告警规则

---

## 监控与可观测性

### Prometheus 指标

| 指标 | 类型 | 说明 |
|:-----|:----:|:-----|
| `http_requests_total` | Counter | HTTP 请求总数 |
| `http_request_duration_seconds` | Histogram | 请求延迟分布 |
| `active_requests` | Gauge | 当前活跃请求数 |
| `cache_hit_rate` | Gauge | 缓存命中率 |
| `model_backend_latency_ms` | Histogram | 后端模型延迟 |

### 健康检查

```bash
# 完整健康检查（含服务状态 + 系统资源）
curl http://localhost:8000/health

# 简单存活检查
curl http://localhost:8000/v1/ping
```

---

## 开发规范

### 代码标头

所有代码文件遵循 YYC³ 团队标头规范：

```python
# file: example.py
# description: 文件功能简述
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-01-01
# updated: 2026-07-10
# status: active
# tags: [module],[function]
```

### 提交规范（Conventional Commits）

```
<type>(<scope>): <subject>

类型: feat | fix | docs | style | refactor | test | chore
```

### 分支策略

```
main        → 生产分支（受保护）
develop     → 开发集成分支
feature/*   → 功能开发分支
hotfix/*    → 紧急修复分支
```

---

## 变更历史

| 版本 | 日期 | 变更内容 |
|:----:|:----:|:---------|
| v2.1.0 | 2026-07-10 | 安全加固：消除全部硬编码密钥，统一环境变量配置；docs/ 移出版本控制 |
| v2.0.0 | 2026-04-08 | 架构升级：自适应路由引擎、RAG 知识库、MCP 工具集成 |
| v1.0.0 | 2026-03-14 | 初始版本：基础 API 网关、多模型接入、容器化部署 |

---

## 团队

<div align="center">

**YanYuCloudCube Team**

言启象限 · 语枢未来

| 联系方式 | 信息 |
|:--------:|:-----|
| **邮箱** | [admin@0379.email](mailto:admin@0379.email) |
| **网站** | [https://0379.world](https://0379.world) |
| **GitHub** | [https://github.com/YYC-Cube](https://github.com/YYC-Cube) |

</div>

---

## 开源许可

本项目基于 [MIT License](./LICENSE) 开源。

```
Copyright (c) 2026 YanYuCloudCube Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

---

<div align="center">

<sub>Built with ❤️ by YanYuCloudCube Team</sub>

<sub>遵循 YYC³「五高五标五化五维」核心机制</sub>

</div>
