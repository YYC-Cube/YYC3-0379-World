# 角色与联系 — CONTACTS（Owner 矩阵）

> 单仓库小团队形态：Owner 按**角色制**登记（角色可由同一人承担，交接时本表是唯一需要改的文件）。
> 联系通道：邮箱组见下表（README Contact 节同源）；紧急安全事件走 `<sec@yanyucloud.com>`。

## Owner 矩阵

| 域 / 组件 | Owner（角色） | 备份 | 联系 | 值守剧本 |
| --- | --- | --- | --- | --- |
| 监控中心（Dashboard/FollowUp/Patrol/Alerts） | 首席架构师 | 监控域开发者 | `<dev@yanyucloud.com>` | FAULT-TREE T4/T9 |
| 运维管理（OperationCenter/Files/DB/Reports） | 首席架构师 | 运维域开发者 | `<dev@yanyucloud.com>` | T4/T13 |
| AI 智能（Models/GatewayKeys/AI 诊断） | AI 域 Owner | 架构师 | `<dev@yanyucloud.com>` | T3/T4 |
| AI Family（8 Agent/12 钟盘/多子页） | AI Family Owner | 架构师 | `<dev@yanyucloud.com>` | T9/T15 |
| 开发规范（DesignSystem/DevGuide） | 文档 Owner | 架构师 | `<docs@yanyucloud.com>` | — |
| 系统管理（Settings/Security/Audit） | 安全 Owner | 架构师 | `<sec@yanyucloud.com>` | T2/T12 |
| 部署（三端 + deploy 件 + NAS/ECS） | 部署 Owner | 首席架构师 | `<ops@yanyucloud.com>` | SELF-HEAL H1/H2/H4 |
| 门禁（16 命令 + 元门禁 + 四棘轮） | 门禁 Owner | 首席架构师 | `<dev@yanyucloud.com>` | T6/T7/T8 |
| 可观测（Prom/Grafana/Loki/审计流） | 可观测 Owner | 部署 Owner | `<ops@yanyucloud.com>` | T4 |
| 后端网关（YYC3-0379-World） | 网关 Owner | 架构师 | `<ops@yanyucloud.com>` | R4/R5 |

## 联系邮箱组（README 同源）

| 邮箱 | 用途 |
| --- | --- |
| dev@yanyucloud.com | 开发通用 |
| docs@yanyucloud.com | 文档与知识库 |
| ops@yanyucloud.com | 运维 |
| admin@yanyucloud.com | 管理员 |
| sec@yanyucloud.com | 安全报告（**勿公开披露**） |

## 关键凭据/访问位置（交接必读）

| 项 | 位置 | 权限要求 |
| --- | --- | --- |
| NAS SSH | `ssh -p 9557 yyc3-45`（别名已配） | YYC3 用户（sudo 免密） |
| ECS SSH | `ssh yyc3-33`（Tailscale） | root |
| NAS console 密码 | /home/YYC3/.yyc3-console-cred | 文件 600 |
| ECS console 密码 | /root/.yyc3-console-cred | 文件 600 |
| 网关 GW_ADMIN_KEY | NAS 网关容器 env（ADMIN_API_KEYS 首值） | 不落终端/文档 |
| GitHub（本仓） | gitbucket remote / Pages 自动 | 见 .git/config |

## Owner 空缺处置（红线：矩阵不留空位）

角色离开团队时：交接人从备份列提升为 Owner，CONTACTS 同步邮箱，**同一提交内**完成（本文件 git 历史即交接史）。
