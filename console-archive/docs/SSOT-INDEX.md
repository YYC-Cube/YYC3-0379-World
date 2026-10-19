# YYC³ Token Console · 单一事实源总索引（SSOT）

> 版本: 2026-10-17（S22 冻结版）· 原则: **每类信息只有一个权威来源**，其余位置只做链接。
> 修改本文档所列文件时须同步其消费者（映射见 §8 修改影响矩阵）。

## 00 · 入门

- [README.md](../README.md) — 项目门面（特性/前置/快速开始/图标链路）
- [AGENTS.md](../AGENTS.md) — AI 协作总纲（红线/分层/域契约/门禁速查/判例）
- [docs/handover/ONBOARDING.md](./handover/ONBOARDING.md) — Day 1/3/7 上手路径

## 01 · 架构

- [docs/architecture/ARCHITECTURE.md](./architecture/ARCHITECTURE.md) — 分层/拓扑/数据流/门禁矩阵
- [docs/architecture/ADR-INDEX.md](./architecture/ADR-INDEX.md) — 14 条决策索引（一决策一文件）
- [docs/architecture/CONTRACTS.md](./architecture/CONTRACTS.md) — 七类跨域契约（类型/网络/存储/错误/WS/提供商/部署件）
- [docs/architecture/BOUNDARIES.md](./architecture/BOUNDARIES.md) — 边界规则 + 真实违规案例库
- [docs/architecture/DIAGRAMS/](./architecture/DIAGRAMS/) — dependency / dataflow / service-lifecycle 三图

## 02 · 开发

- docs/YYC3-开发者文档/CONTRIBUTING.md — 贡献流程
- docs/YYC3-开发者文档/LABELS.md — 标签规范
- docs/YYC3-开发者文档/CICD.md — 流水线说明
- [docs/scripts/SCRIPTS-INDEX.md](./scripts/SCRIPTS-INDEX.md) — 41 入口编目
- [docs/scripts/SCRIPTS-REFERENCE.md](./scripts/SCRIPTS-REFERENCE.md) — 逐脚本手册
- [docs/scripts/EXIT-CODES.md](./scripts/EXIT-CODES.md) · [PARAM-MATRIX.md](./scripts/PARAM-MATRIX.md) · [ENV-MATRIX.md](./scripts/ENV-MATRIX.md)

## 03 · 运维

- [docs/ops/RUNBOOK.md](./ops/RUNBOOK.md) — 值守总纲（拓扑/探针/升级路径）
- [docs/ops/FAULT-TREE.md](./ops/FAULT-TREE.md) — 15 棵故障树
- [docs/ops/SELF-HEAL.md](./ops/SELF-HEAL.md) — 6 自愈剧本
- [docs/ops/ONCALL-CHECKLIST.md](./ops/ONCALL-CHECKLIST.md) — 交接五段清单
- [docs/ops/INCIDENT-LOG.md](./ops/INCIDENT-LOG.md) — 复盘模板 + 事故索引

## 04 · 可观测

- [docs/observability/METRICS-DICT.md](./observability/METRICS-DICT.md) — 指标字典（生产实测口径）
- [docs/observability/ALERTS.md](./observability/ALERTS.md) — 7 现役规则 + 分级路由
- [docs/observability/DASHBOARDS.md](./observability/DASHBOARDS.md) — 仪表盘清单
- [docs/observability/TRACING.md](./observability/TRACING.md) — traceId 三锚点族谱
- [docs/observability/LOGGING.md](./observability/LOGGING.md) — 结构化日志规范
- [docs/observability/SLO.md](./observability/SLO.md) — 5 条 SLO + 错误预算

## 05 · 发布

- [docs/release/CHANGE-MANAGEMENT.md](./release/CHANGE-MANAGEMENT.md) — C0-C4 分级矩阵
- [docs/release/RELEASE-CHECKLIST.md](./release/RELEASE-CHECKLIST.md) — 七段勾选清单
- [docs/release/ROLLBACK.md](./release/ROLLBACK.md) — 六型回滚剧本
- [docs/release/VERSIONING.md](./release/VERSIONING.md) · [CHANGELOG-TEMPLATE.md](./release/CHANGELOG-TEMPLATE.md) · [FREEZE-POLICY.md](./release/FREEZE-POLICY.md)

## 06 · 交接

- [docs/handover/FAQ.md](./handover/FAQ.md) — 12 问（真实判例）
- [docs/handover/GLOSSARY.md](./handover/GLOSSARY.md) — 术语表（六域/8 Agent/12 钟盘/引擎）
- [docs/handover/DECISION-LOG.md](./handover/DECISION-LOG.md) — 决策时间线
- [docs/handover/KNOWN-GAPS.md](./handover/KNOWN-GAPS.md) — 13 项开口（触发条件制）
- [docs/handover/CONTACTS.md](./handover/CONTACTS.md) — Owner 矩阵 + 凭据位置

## 07 · 审计与合规

- [docs/audit/INDEX.md](./audit/INDEX.md) — 15 阶段审计链唯一入口（22 目录）
- [docs/audit/20261017T0200-s15-final/final-report.md](./audit/20261017T0200-s15-final/final-report.md) — 终判报告
- [docs/audit/20261016T2200-backlog/](./audit/20261016T2200-backlog/) — DEF 登记 + backlog-resolution（L-01~14）
- [docs/FREEZE.md](./FREEZE.md) — 冻结声明（S22）

## 08 · 领域专题（根级）

- docs/YYC3-双端完全联通方案-*.md — 双端联通方案主文档
- docs/YYC3-双端联通实施日志.md — R1-R11 逐批日志
- docs/YYC3-全局导航功能架构可视化.md — 导航架构
- docs/YYC3-全量落地实施总结与衔接报告.md — Phase 1-4 单一事实源
- docs/YYC3-PWA浏览器人工验证清单.md — PWA 手动验证
