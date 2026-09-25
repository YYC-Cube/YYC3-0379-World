---
file: README.md
description: YYC3-多端部署-Agent代码 工程根导航 - 三库分离结构与入口索引
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-09-24
status: published
tags: [导航],[文档分离],[代码库],[文档库]
category: index
language: zh-CN
---

# YYC3-多端部署-Agent代码 工程根导航

> 本工程已按「代码-文档严格分离」原则重组为三库。**所有说明性文档归 YYC3-文档库，所有可执行代码归 YYC3-代码库，规范+API+代码三位一体的组件库为 YYC3-AI-Family-Agent**。文档/代码索引唯一入口：[YYC3-文档库/00-标准规范-总纲与索引/INDEX.md](YYC3-文档库/00-标准规范-总纲与索引/INDEX.md)

## 目录结构

```
YYC3-多端部署-Agent代码/
├── README.md                        # 本文件（工程根导航）
├── YYC3-AI-Family-Agent/            # ★ 标准组件库：12个组件（README规范+API文档+代码）
│   ├── README.md                    # 总规范（九步闭环+成员矩阵+目录结构标准）
│   ├── 00-公共基座/ ... 99-编排引擎-全链路闭环/
├── YYC3-文档库/                     # 纯文档（零代码）
│   ├── 00-标准规范-总纲与索引/       # 总规范 + INDEX.md 总索引
│   ├── 01-Agent架构与实现-源文档/    # 4份原始架构/实现文档（只读归档）
│   ├── 02-硬件运维-NAS挂载与同步/    # 2份原始硬件文档（只读归档）
│   ├── 10-API接口文档/              # 12份API.md 归档副本
│   └── 20-Agent标准规范/            # 12份成员README 归档副本
└── YYC3-代码库/                     # 纯代码（零说明长文档）
    ├── 00-公共基座-BaseAgent/        # base_agent.py
    ├── 01-编排引擎-异步调度/         # 完整可运行包（基座+8成员+RAG+编排+A2A）
    ├── 02-知识库-向量检索/           # milvus_retriever.py
    └── 03-硬件运维-NAS挂载脚本/      # sh同步脚本×5 + NFS/fstab/env/compose×5
```

## 快速入口

| 我要… | 去哪里 |
| ---- | ------ |
| 看总规范/九步闭环 | `YYC3-AI-Family-Agent/README.md` |
| 查接口参数/错误码/调用示例 | 对应组件目录 `API.md` 或 `YYC3-文档库/10-API接口文档/` |
| 本地跑通全链路 | `YYC3-代码库/01-编排引擎-异步调度/` 整目录复制，`python ai_family_orchestrator.py` |
| 部署 NAS/双机基础设施 | `YYC3-代码库/03-硬件运维-NAS挂载脚本/`（先 nfs_exports.conf → dgx_fstab.conf → docker-compose） |
| 溯源原始设计文档 | `YYC3-文档库/01-…`、`02-…`（只读归档） |

## 维护约定

1. 源文档目录（01/02）**只读归档**，不再修改；新文档一律进文档库对应编号目录
2. 代码修改在 `YYC3-AI-Family-Agent/` 组件目录进行，同步副本至 `YYC3-代码库/`（保持单一事实源）
3. 新增组件必须遵循三位一体：README.md + API.md + 代码，并更新 INDEX.md

---

*© 2025-2026 YYC³ Team. All Rights Reserved.*
