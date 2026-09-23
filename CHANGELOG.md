---
file: CHANGELOG.md
description: YYC³ 0379-world 项目版本变更日志
author: YanYuCloudCube Team <admin@0379.email>
version: v1.1.0
created: 2026-04-04
updated: 2026-09-23
status: active
tags: [changelog],[version],[history]
category: project
language: zh-CN
---

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

---

# 变更日志 (Changelog)

本文档记录 YYC³ 0379-world 项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [2.3.0] - 2026-09-23

### 新增 (Added)

- 🆕 流式 SSE chunk 级 PII 脱敏（carry 缓冲拼接跨 chunk 截断 PII，流末 flush 滞缓冲）
- 🆕 vk 管理看板与 Playwright 真浏览器 e2e 基建（chromium channel=chrome）
- 🆕 三层防御体系：vk 403 / 预算 402 / TPM 429
- 🆕 错误重试测试套件 `tests/test_error_retry.py`（6 用例，含零空转断言）
- 🆕 三云适配器 Key 校验参数化矩阵（`_CLOUD_ADAPTERS` 表驱动，断言面=声明面）
- 🆕 IDE 导入解析三件套：`pyrightconfig.json` + 根级 `app` symlink + `.markdownlint.json`
- 🆕 Redis 从节点部署 (yyc3-45:6399)，避开系统 Redis 6379
- 🆕 CodeGeeX4 Agent 实现 (`agents/yyc3_code_agent.py`，唯一真源)

### 变更 (Changed)

- 🔄 ZHIPU/DeepSeek/OpenAI 三云适配器 Key 前置校验同构化（`ensure_api_key` 公共件落位 `app/errors/key_guard.py`）
- 🔄 DeepSeek/OpenAI Key 从模块级快照改为延迟读取（运行时热加载）
- 🔄 4xx 确定性失败跳过重试（`ErrorHandler._is_retryable`，终结空转重试）
- 🔄 ZHIPU 同步入口接入 `_ensure_key()`（空 Key 401 明确报错，替代模糊 502）
- 🔄 Gateway 容器 (NAS) 配置修正：DB_HOST/REDIS_HOST/HOST_IP 指向正确地址
- 🔄 Gateway 健康检查从 `curl` 改为 `python3 urllib`（容器内无 curl）
- 🔄 Gateway 重启策略从 `unless-stopped` 改为 `no`（防止无限重启崩溃系统）

### 修复 (Fixed)

- 🔧 **P0 致命**: 修复 Gateway 容器 `unhealthy` → `healthy`
  - 根因：DB_HOST=127.0.0.1 导致启动失败 + restart 无限循环 → 系统崩溃
  - 方案：修正环境变量指向实际服务地址，禁用自动重启
- 🔧 **P0 致命**: Redis 从节点端口冲突解决
  - 根因：Docker Redis 映射 6379 与 NAS 系统 Redis 冲突（TANS/TOS 缓存）
  - 方案：使用端口 6399 避开系统服务，建立主从复制
- 🔧 确认 NAS 系统服务安全：Redis(6379) / PG13(5032) 未受任何干扰
- 🔧 OBS-1 空转重试：401 等 4xx 确定性失败不再消耗 3 轮重试（耗时 <0.5s）
- 🔧 OBS-2 DeepSeek 空 Key 模糊 502 → 401 明确报错；OpenAI 无校验 → 补齐前置校验
- 🔧 移除重复 agent 副本 `core/scripts/yyc3_code_agent.py`（lint 清理旧版，零外部引用）

---

## [2.2.0] - 2026-09-14

### 新增 (Added)

- 🆕 DGX 双机 TP=2 公网三能力（chat/embeddings/rerank）全绿
- 🆕 上游池 env 化（`OPENAI_COMPATIBLE_UPSTREAMS`）+ 熔断降级
- 🆕 CI 五段流水线 + 四层冒烟保障
- 🆕 文档体系 SSOT 对齐（架构/部署/CI-CD/前端设计三合一）
- 🆕 生产域名 `https://api.0379.world`（ECS Traefik 边缘 → NAS 网关:8000）

### 变更 (Changed)

- 🔄 响应头 `X-YYC3-Upstream` 契约落地

---

## [2.1.0] - 2026-07-10

### 安全 (Security)

- 🔒 消除全部硬编码密钥，统一环境变量配置
- 🔒 `docs/` 敏感遗留清理

---

## [2.0.0] - 2026-04-08

### 新增 (Added)

- 🆕 自适应路由引擎（EWMA 动态权重）
- 🆕 RAG 知识库
- 🆕 MCP 工具集成

---

## [1.0.0] - 2026-04-04

### 新增 (Added)

#### 核心功能

- ✅ FastAPI 应用框架搭建
- ✅ PostgreSQL 数据库集成
- ✅ Redis 缓存服务集成
- ✅ API 网关服务
- ✅ 多模型 AI 服务集成（OpenAI、智谱 AI、Ollama）
- ✅ MCP 工具集成
- ✅ Prometheus + Grafana 监控系统

#### API 服务

- ✅ CloudPivot Matrix API 服务（端口 3118）
- ✅ CloudPivot Matrix WebSocket 服务（端口 3113）
- ✅ YYC³ AIFY 服务（端口 3200）
- ✅ YYC³ MCP 服务（端口 3203）

#### 数据库

- ✅ 主数据库：0379_world
- ✅ 核心共享库：yyc3_core
- ✅ AI 助手库：yyc3_aify
- ✅ 企业管理库：yyc3_my
- ✅ MCP API 服务库：yyc3_mcp
- ✅ 开发测试库：yyc3_dev

#### 工具和脚本

- ✅ 环境变量验证脚本
- ✅ 性能基线测试脚本
- ✅ 监控启动脚本
- ✅ Grafana 仪表盘配置脚本
- ✅ 告警通知脚本

#### 文档

- ✅ 项目 README.md
- ✅ API 全链路架构文档
- ✅ 整体架构设计文档
- ✅ 多端架构说明文档
- ✅ 项目现状分析文档
- ✅ 部署完成总结文档

### 文档规范

#### 合规性统一

- ✅ 所有 Markdown 文档添加 YAML Front Matter 标头
- ✅ 所有 Python 代码文件添加 JSDoc 标头注释
- ✅ 文件命名规范化（snake_case）
- ✅ 项目目录结构规范化
- ✅ 创建合规性检查工具集

#### 新增文档

- ✅ CHANGELOG.md - 版本变更日志
- ✅ CONTRIBUTING.md - 贡献指南
- ✅ LICENSE - MIT 开源许可证
- ✅ Makefile - 构建脚本
- ✅ Dockerfile - Docker 构建文件

### 变更 (Changed)

#### 项目结构优化

- 🔄 重组项目目录结构
- 🔄 规范化配置文件管理
- 🔄 优化 Docker Compose 配置

#### 性能优化

- 🔄 数据库连接池优化
- 🔄 Redis 缓存策略优化
- 🔄 API 限流配置优化

### 修复 (Fixed)

#### 环境配置

- 🐛 修复环境变量配置问题
- 🐛 修复 Docker 网络冲突问题
- 🐛 修复 NFS 挂载中断问题

#### 服务稳定性

- 🐛 修复健康检查失败问题
- 🐛 修复服务自动重启问题
- 🐛 修复监控数据采集问题

---

## [0.9.0] - 2026-03-21

### 新增 (Added)

#### 基础架构

- ✅ 项目初始化
- ✅ 基础目录结构创建
- ✅ Git 仓库初始化
- ✅ 基础配置文件

#### 数据库服务

- ✅ PostgreSQL 数据库部署
- ✅ Redis 缓存服务部署
- ✅ 数据库初始化脚本

#### 容器化

- ✅ Docker Compose 配置
- ✅ 基础镜像构建
- ✅ 容器网络配置

---

## 版本说明

### 版本号格式

遵循语义化版本 2.0.0 规范：`主版本号.次版本号.修订号`

- **主版本号（MAJOR）**: 不兼容的 API 修改
- **次版本号（MINOR）**: 向下兼容的功能性新增
- **修订号（PATCH）**: 向下兼容的问题修正

### 变更类型

- **新增 (Added)**: 新功能
- **变更 (Changed)**: 对现有功能的变更
- **弃用 (Deprecated)**: 即将删除的功能
- **移除 (Removed)**: 已删除的功能
- **修复 (Fixed)**: 任何 bug 修复
- **安全 (Security)**: 安全相关的修复

---

## 路线图

### v1.1.0 (计划中)

- [ ] 完善测试覆盖（单元测试、集成测试）
- [ ] 添加 API 文档（Swagger/OpenAPI）
- [ ] 优化监控告警规则
- [ ] 添加自动化运维脚本

### v1.2.0 (计划中)

- [ ] CI/CD 流程配置
- [ ] 自动化部署流程
- [ ] 性能优化和压力测试
- [ ] 安全加固和渗透测试

### v2.0.0 (长期规划)

- [ ] 微服务架构重构
- [ ] Kubernetes 部署支持
- [ ] 多租户支持
- [ ] 插件化架构

---

## 贡献

如果您想为本项目做出贡献，请参阅 [CONTRIBUTING.md](./CONTRIBUTING.md)。

---

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](./LICENSE)。

---

**维护团队**: YanYuCloudCube Team
**联系方式**: <admin@0379.email>
**项目地址**: <https://github.com/YYC-Cube/yyc3-api-world>

---

[1.0.0]: https://github.com/YYC-Cube/yyc3-api-world/releases/tag/v1.0.0
[0.9.0]: https://github.com/YYC-Cube/yyc3-api-world/releases/tag/v0.9.0
