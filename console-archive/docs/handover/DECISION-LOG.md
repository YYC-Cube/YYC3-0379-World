# 决策日志 — DECISION LOG（时间线 · 详版见 ADR-INDEX）

> 时间线 = 决策发生的真实时序；每条链 ADR / 审计目录。完整权衡文本以 ADR 为准，此处为导航层。

## 2025-09（奠基期）

| 日期 | 决策 | ADR | 触发背景 |
| --- | --- | --- | --- |
| 2025-09 | Vite SPA 而非 Next.js | [ADR-001](../architecture/ADR-001-vite-spa.md) | 本地看盘+Pages 静态定位 |
| 2025-09 | 层级契约 boundaries 落地 | [ADR-002](../architecture/ADR-002-domain-contracts.md) | 分层防腐 |
| 2025-09 | 零 npm 依赖部署件 server.mjs | [ADR-005](../architecture/ADR-005-zero-dep-deploy.md) | NAS 离线部署形态 |
| 2025-09 | i18n 类型+测试双守护 | [ADR-008](../architecture/ADR-008-i18n-consistency.md) | 双语腐烂预防 |
| 2025-09 | unit 档零外部依赖 + 三工作区分级 | [ADR-011](../architecture/ADR-011-unit-isolation.md) | flaky 根治 |
| 2025-09 | size/knip 基线棘轮 | [ADR-012](../architecture/ADR-012-baseline-ratchet.md) | 熵控制 |
| 2025-09 | provider 声明式 JSON+zod | CONTRACTS §6 | 新提供商零代码 |

## 2026-09（门禁防腐期）

| 日期 | 决策 | ADR | 触发背景 |
| --- | --- | --- | --- |
| 2026-09-24 | 元门禁 guardrail-probe | [ADR-004](../architecture/ADR-004-guardrail-meta-gate.md) | **两条门禁同时静默失效**的原始事件 |
| 2026-09-29 | 豁免条目纪律（原因+复核+指纹） | .gitleaks.toml | 批11 季度核对 |

## 2026-10（生产化与审计期）

| 日期 | 决策 | ADR/文档 | 触发背景 |
| --- | --- | --- | --- |
| 2026-10-05 | 覆盖率四门槛锁定 | [ADR-003](../architecture/ADR-003-coverage-thresholds.md) | 爬坡 45%→91% 后防倒退 |
| 2026-10-05 | 手写 vanilla SW（弃 workbox） | [ADR-007](../architecture/ADR-007-pwa-handcrafted-sw.md) | 供应链降级拦截 ERR_PNPM_TRUST_DOWNGRADE |
| 2026-10-05 | 补全引擎五维协同 + 频率闭环 | [ADR-010](../architecture/ADR-010-completions-5d.md) | 动态数据源利用 |
| 2026-10-05 | Prometheus 告警三规则组 | ALERTS.md | 观测栈 O-1 整改 |
| 2026-10-16 | 六域契约制度化（AGENTS） | [ADR-002](../architecture/ADR-002-domain-contracts.md) 补条 | S3 治理批 |
| 2026-10-16 | TS 双旗标全仓固化 | [ADR-013](../architecture/ADR-013-strict-flags.md) | S2 首跑 764 errors |
| 2026-10-16 | lint:fp 悬空 Promise 零容忍 | [ADR-014](../architecture/ADR-014-lint-fp.md) | S7 缺口登记 |
| 2026-10-16 | color/dup 基线棘轮 | [ADR-012](../architecture/ADR-012-baseline-ratchet.md) | S3/S8 缺口登记 |
| 2026-10-16 | HMAC + jti 吊销 + 审计 JSONL | [ADR-006](../architecture/ADR-006-hmac-auth.md) | S6 十维+S11 实测 |
| 2026-10-16 | maxWorkers 封顶 8 | vitest.config | R3 竞争判例 |
| 2026-10-16 | gpuUtil 节点聚合推导（L-12a） | gateway-adapter | 网关不发该字段实证 |
| 2026-10-16 | 图标 29 PNG 实测口径 | [ADR-009](../architecture/ADR-009-icon-platforms.md) | 模板"36"更正 |

## 决策日志使用约定

- 新决策（C3+）落地时**同日**在此表 + ADR-INDEX 双登记；
- 被 Superseded 的条目在 ADR 文件内标注，本表**不删行**，改标「→ 见 ADR-YYY」；
- 「未成文决策」（评审口头结论）须在下次 C3 变更时补 ADR 追认。
