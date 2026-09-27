---
file: README.md
description: 模型接入与注册文档体系索引 - 现状基线与目标架构分层总览
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-09-27
updated: 2026-09-27
status: active
tags: [index],[model-registry],[onboarding]
category: spec
---

# 模型接入与注册 · 文档体系索引

> 本目录由原《YYC3-0379-World模型接入规范文档》（v2.3.0）与《YYC3-0379-world-模型接入Agent注册规范文档》（YYC3-MRS-2026-v1.0.0）两份平行规范**整合拆分**而来（原文档已归档至 `docs/archive/`）。
> 拆分主轴：**现状基线（生产代码已实现）与目标架构（Registry 演进规划）严格分层**，每项机制显式标注实现状态，遵循「以代码为准绳」红线。

## 文档清单与阅读路径

| 文档 | 定位 | 必读角色 |
| --- | --- | --- |
| [01-接入现状规范-v2.3.md](01-接入现状规范-v2.3.md) | ✅ 现状基线：env 上游池 / 熔断 / NAS 资产仓库 / vLLM 部署约束（对齐生产代码 v2.3.0） | 模型部署工程师 · SRE |
| [02-Registry目标架构.md](02-Registry目标架构.md) | 📋 目标架构：注册中心 DB Schema / API / 双通道发现 / 演进三阶段 | 平台架构师 · 后端 |
| [03-热切换与版本管理.md](03-热切换与版本管理.md) | 📋 目标架构：Shadow/Canary/蓝绿四模式 / 版本门禁 / 回滚决策树 | 平台架构师 · 质量 |
| [04-Agent注册规范.md](04-Agent注册规范.md) | ✅+📋 混合：A2A 生产契约为基线，MCP 工具声明为演进层 | Agent 开发者 · 编排 |
| [05-监控告警与Runbook.md](05-监控告警与Runbook.md) | ✅+📋 混合：现有指标与规划告警 / 三个 SOP / 故障排查 | SRE · 观测 |

## 实现状态总览（核心价值表）

> 任何机制在引用前先查此表；「📋 规划」条目禁止在生产操作手册中当现状引用。

| 机制 | 状态 | 代码锚点 / 规划文档 |
| --- | --- | --- |
| env 上游池 `OPENAI_COMPATIBLE_UPSTREAMS`（fnmatch 匹配/优先级/权重） | ✅ 生产 | `core/api/services/upstream_registry.py` |
| 熔断器（连续 3 次失败摘除 30s，半开探测恢复） | ✅ 生产 | 同上（`BREAKER_FAILURE_THRESHOLD=3`） |
| 响应头 `X-YYC3-Upstream` / `X-YYC3-Degraded` | ✅ 生产 | `core/api/api/chat.py` / `proxy.py` 等 |
| 上游主动验活降级（连续失败权重×0.5，不摘除） | ✅ 生产 | `upstream_registry.py`（`probe_degraded`） |
| 多 Key 轮询（`api_key_envs`，429 跳下一把） | ✅ 生产 | `upstream_registry.py`（`api_key()`） |
| 主权标签路由（`X-YYC3-Sovereign: required` → sovereign 上游） | ✅ 生产 | `upstream_registry.py`（`sovereign`） |
| model_registry 表 | ⚠️ 仅有 6 基础字段（id/display_name/backend_type/backend_name/enabled/created_at） | `core/api/db.py#L58` |
| Registry 端点（`/registry/v1/*` 12 模型端点 + 10 Agent 端点） | 📋 规划 | [02](02-Registry目标架构.md) |
| 模型服务契约端点（`/v1/model/metadata` 等 3 个 YYC³ 新增） | 📋 规划 | [02](02-Registry目标架构.md) §2 |
| 心跳 TTL（30s 上报 / 90s degraded / 300s 摘除） | 📋 规划 | [02](02-Registry目标架构.md) §4.6 |
| Shadow / Canary / 蓝绿热切换 | 📋 规划 | [03](03-热切换与版本管理.md) |
| 别名 alias 动态切换 + draining 排空 | 📋 规划 | [03](03-热切换与版本管理.md) §3.5 |
| A2A Agent 注册（Agent Card + Redis stream + 心跳 + 能力发现） | ✅ 生产 | `core/api/api/a2a.py` / `core/api/services/a2a_protocol.py` |
| A2A vk 计费门控（白名单/预算/TPM + X-A2A-Cost） | ✅ 生产（2026-09-27 生产首验通过） | `core/api/api/a2a.py`（`_enforce_agent_vk_gates`） |
| MCP 工具声明 / HTTP Agent 端点注册 | 📋 规划（演进层） | [04](04-Agent注册规范.md) §4 |
| 模型资产完整性校验脚本 `model_asset_verify.py` | 📋 规划待实现 | [01](01-接入现状规范-v2.3.md) 附录 A |
| NAS → 节点增量同步脚本 `model_sync_to_node.py` | 📋 规划待实现 | 同上 |
| 注册 Agent `model_register_agent.py` | 📋 规划待实现 | 同上 |
| 模型上线冒烟脚本 `model_smoke_test.py` | 📋 规划待实现 | 同上 |

## 整合时统一的关键决策

原两文档存在约 40% 重复且细节冲突，整合时按以下口径统一（冲突原文见归档件）：

| 冲突点 | 原文档 A | 原文档 B | **统一口径** |
| --- | --- | --- | --- |
| 设备命名 | dgx-n1 / dgx-n2 / yyc3-22-mac | yyc3-101 / yyc3-102 | **node_id = yyc3-101 / yyc3-102**（对齐《YYC3-设备-模型全量信息文档》权威命名；DGX-N1/N2 仅作硬件型号备注） |
| 心跳参数 | 5s 上报 / 30s 超时 | 30s / 90s / 300s 三级 | **采用 B 的三级 TTL 阶梯**（更成熟，且现状无心跳机制，属规划层） |
| 元数据载体 | model-meta.json 文件 | `/v1/model/metadata` 端点 | **端点契约为主**（契约优先原则），model-meta.json 仅作注册 Agent 的本地缓存源 |
| 实例状态机 | offline→loading→ready→draining | healthy/degraded/unreachable | **两层分用**：实例生命周期用 A 四态（含 draining）；健康检查用 B 三态 |
| 熔断降级「错误率>15%」 | 有此声明 | 无 | **删除**（生产代码无此逻辑；EWMA 错误率统计存在但无 15% 自动降级阈值，列为规划候选） |
| Agent 注册体系 | 未涉及 | /registry/v1/agents 10 端点 | **以现有 A2A 生产契约为基线**，MCP 工具声明作演进层，消除双轨（详见 [04](04-Agent注册规范.md)） |

## 上游参考

- [YYC3-Models-资产详情.md](../架构与部署/YYC3-Models-资产详情.md)（模型资产清单）
- [A2A开放API契约.md](../架构与部署/A2A开放API契约.md)（Agent 注册生产契约）
- [API全链路闭环文档.md](../架构与部署/API全链路闭环文档.md)
- [CI-CD部署配置指南.md](../架构与部署/CI-CD部署配置指南.md)

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0.0 | 2026-09-27 | 两规范整合拆分为五文档 + 索引；统一命名/心跳/元数据载体/状态机口径；幽灵脚本标注规划 |
