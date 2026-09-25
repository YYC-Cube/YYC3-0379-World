---
file: INDEX.md
description: YYC3 AI FAmily Agent 文档总索引 - 文档分离归档体系唯一入口
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-09-24
status: published
tags: [索引],[归档],[文档体系]
category: index
language: zh-CN
---

# YYC3 AI FAmily Agent 文档总索引

> 文档分离归档体系唯一入口。代码与文档严格分离：**文档看这边（本目录），代码跑那边（YYC3-代码库），标准组件看 YYC3-AI-Family-Agent/（规范+API+代码三位一体）**。

## 一、分离原则与三库结构

| 库 | 路径 | 内容 | 使用场景 |
| -- | ---- | ---- | -------- |
| **标准组件库** | `YYC3-AI-Family-Agent/` | 12个组件目录，每目录=README规范+API接口文档+代码（三位一体） | 日常开发首选：查规范、查API、看代码一站式 |
| **文档库** | `YYC3-文档库/` | 纯文档：源文档归档、API/规范归档副本、总规范、本索引 | 查阅、评审、归档；不含任何代码 |
| **代码库** | `YYC3-代码库/` | 纯代码：可直接运行的 py/sh/yml/conf/env | 部署执行；不含说明性长文档 |

## 二、文档库索引（YYC3-文档库/）

### 00-标准规范-总纲与索引

| 文件 | 说明 |
| ---- | ---- |
| `YYC3-AI-Family-Agent-总规范.md` | 体系总览+8位成员矩阵+ReAct-C九步闭环+映射标准（源头规范） |
| `INDEX.md` | 本索引 |

### 01-Agent架构与实现-源文档（原始工程资产，只读归档）

| 文件 | 说明 |
| ---- | ---- |
| `YYC3-AI-FAmily-Agent双机DGX-Spark落地模型配置与全链路闭环方案.md` | 角色-模型-硬件映射、双机拓扑、ReAct-C落地版 |
| `Agent-A2A通信协议与消息队列异步调度的实现.md` | A2A协议+Redis Stream异步调度完整实现 |
| `Milvus向量库-Python-检索代码-预见先知-时序预测.md` | Milvus检索封装+预见先知Agent完整实现 |
| `创想灵韵-知遇伯乐代码示例.md` | 创想灵韵/知遇伯乐实现+Orchestrator v2.0+九步时序表 |

### 02-硬件运维-NAS挂载与同步（原始工程资产，只读归档）

| 文件 | 说明 |
| ---- | ---- |
| `NAS-NFS挂载配置-DGX自动挂载.md` | NAS端NFS导出配置+DGX fstab自动挂载+编排引擎示例 |
| `MacMAX-NAS-DGX-调试-同步-挂载.md` | Mac本地调试脚本+NAS定时同步+双DGX compose |

### 10-API接口文档（接口文档归档副本，源头在标准组件库各目录 API.md）

| 文件 | 覆盖接口 |
| ---- | -------- |
| `00-公共基座-API.md` | BaseAgent：run/heartbeat/mock 降级 |
| `01-元启天枢-决策中枢-API.md` | plan_tasks / synthesize / decide |
| `02-智云守护-安全官-API.md` | check_input / audit / write_audit_log |
| `03-格物宗师-质量官-API.md` | validate / review_code |
| `04-创想灵韵-创意官-API.md` | polish_report / brainstorm_ideas / generate_marketing_copy / visualization_suggestion |
| `05-言启千行-导航员-API.md` | run(路由) / _rule_based_route / format_output |
| `06-语枢万物-思考者-API.md` | analyze / decompose_problem |
| `07-预见先知-预言家-API.md` | full_forecast / qualitative_analysis / risk_warning |
| `08-知遇伯乐-推荐官-API.md` | build_user_profile / recommend_content / plan_growth_path / optimize_experience |
| `90-公共RAG-知识库-API.md` | insert_documents / search / delete_by_source / batch_import_from_nas |
| `91-A2A-通信协议-API.md` | Registry/Producer/Consumer/A2ABaseAgent/AsyncOrchestrator |
| `99-编排引擎-全链路闭环-API.md` | execute 九步闭环 / _get_knowledge |

### 20-Agent标准规范（成员规范归档副本，源头在标准组件库各目录 README.md）

12 份成员 README 归档（00-99 与 API 文档同名对应），含角色定位、架构对齐、接口清单、模型映射、协同关系。

## 三、代码库索引（YYC3-代码库/）

| 目录 | 文件 | 语言 | 说明 |
| ---- | ---- | ---- | ---- |
| `00-公共基座-BaseAgent/` | `base_agent.py` | Python | 全体Agent统一基类 |
| `01-编排引擎-异步调度/` | `base_agent.py`、8个成员Agent、`a2a_protocol.py`、`ai_family_orchestrator.py` | Python | 可整体运行的完整工程包（同目录互import） |
| `02-知识库-向量检索/` | `milvus_retriever.py` | Python | 公共RAG检索引擎 |
| `03-硬件运维-NAS挂载脚本/` | `mac_local_debug.sh`、`sync_config.sh`、`sync_model_to_dgx.sh`、`sync_log_backup.sh`、`backup_vector.sh`、`nfs_exports.conf`、`dgx_fstab.conf`、`dgx.env`、`docker-compose.node1.yml`、`docker-compose.node2.yml` | Shell/Conf/YAML | Mac调试栈、NAS四级定时同步、NFS/fstab挂载、双机编排 |

> `01-编排引擎-异步调度/` 是唯一完整可运行组合：复制该目录即可跑通九步闭环（依赖见下）。

## 四、标准组件库索引（YYC3-AI-Family-Agent/，三位一体）

| 目录 | README规范 | API接口文档 | 代码 |
| ---- | ---------- | ----------- | ---- |
| 00-公共基座 | ✅ | ✅ | base_agent.py |
| 01-元启天枢-决策中枢 | ✅ | ✅ | yuanqi_tianshu_agent.py |
| 02-智云守护-安全官 | ✅ | ✅ | zhiyun_shouhu_agent.py |
| 03-格物宗师-质量官 | ✅ | ✅ | gewu_zongshi_agent.py |
| 04-创想灵韵-创意官 | ✅ | ✅ | chuangxiang_lingyun_agent.py |
| 05-言启千行-导航员 | ✅ | ✅ | yanqi_qianhang_agent.py |
| 06-语枢万物-思考者 | ✅ | ✅ | yushu_wanwu_agent.py |
| 07-预见先知-预言家 | ✅ | ✅ | yujian_xianzhi_agent.py |
| 08-知遇伯乐-推荐官 | ✅ | ✅ | zhiyu_bole_agent.py |
| 90-公共RAG-知识库 | ✅ | ✅ | milvus_retriever.py |
| 91-A2A-通信协议 | ✅ | ✅ | a2a_protocol.py |
| 99-编排引擎-全链路闭环 | ✅ | ✅ | ai_family_orchestrator.py |

## 五、查阅路径建议

1. **了解体系** → 本文件 → `00-标准规范-总纲与索引/YYC3-AI-Family-Agent-总规范.md`
2. **调用某接口** → `10-API接口文档/` 对应 API.md（含参数表/错误码/调用示例）
3. **修改某Agent** → `YYC3-AI-Family-Agent/` 对应目录（README 看定位，API 看契约，.py 改实现）
4. **部署运行** → `YYC3-代码库/01-编排引擎-异步调度/`（Python 工程）、`03-硬件运维-NAS挂载脚本/`（基础设施）
5. **溯源设计依据** → `01-Agent架构与实现-源文档/`、`02-硬件运维-NAS挂载与同步/`

## 六、依赖与环境

- Python 依赖：`openai`、`pymilvus==2.4.5`、`redis`、`python-dotenv`、`numpy`
- 环境变量：`LLM_BASE_URL/LLM_API_KEY/LLM_MODEL`（推理）、`MILVUS_HOST/MILVUS_PORT/DGX1_EMBED_URL`（RAG）、`REDIS_HOST/REDIS_PORT`（A2A）
- 基础设施：双DGX Spark（节点1推理/节点2支撑）+ NAS（RAID1热备/RAID6大容量）+ MacMAX（开发调试）

## 七、变更历史

| 版本 | 日期 | 变更内容 | 作者 |
| ---- | ---- | -------- | ---- |
| v1.0.0 | 2026-09-24 | 初始版本：三库分离+12份API文档+索引体系建立 | YanYuCloudCube Team |

---

*© 2025-2026 YYC³ Team. All Rights Reserved.*
