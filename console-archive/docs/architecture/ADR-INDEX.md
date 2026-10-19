# ADR 总索引 — YYC³ Token Console

> 维护约定: 一决策一文件; 状态只允许 Accepted / Superseded by ADR-YYY / Deprecated;
> 新 ADR 取最大编号 +1; 修改既有决策 = 新建 ADR + 旧条目标 Superseded（不删不改原文）。

| 编号 | 决策 | 状态 | 日期 | 守护门禁 |
| --- | --- | --- | --- | --- |
| [ADR-001](./ADR-001-vite-spa.md) | Vite SPA 而非 Next.js SSR | Accepted | 2025-09 | `pnpm build` 产物纯静态 + Pages 部署 |
| [ADR-002](./ADR-002-domain-contracts.md) | 六域互不直连，跨域走 contracts 下沉 | Accepted | 2026-10-16 | eslint boundaries + AGENTS 域契约 |
| [ADR-003](./ADR-003-coverage-thresholds.md) | 覆盖率门槛锁定 90/85/80/88 只增不减 | Accepted | 2026-10-05 | vitest thresholds（退化即 exit≠0） |
| [ADR-004](./ADR-004-guardrail-meta-gate.md) | 元门禁 guardrail-probe 防假绿 | Accepted | 2026-09-24 | `pnpm guardrail-probe`（20 探针） |
| [ADR-005](./ADR-005-zero-dep-deploy.md) | 部署服务器零 npm 运行时依赖 | Accepted | 2025-09 | eslint import 扫描 + S14 部署验证 |
| [ADR-006](./ADR-006-hmac-auth.md) | HMAC 会话 + 时间戳 + 限流 + jti 吊销 | Accepted | 2026-10-16 | console-auth.test 18 用例 + e2e auth |
| [ADR-007](./ADR-007-pwa-handcrafted-sw.md) | 手写 vanilla SW + PWA 全链 + CDN 回退 | Accepted | 2026-10-05 | e2e 离线/资产用例 + SW 预缓存注入 |
| [ADR-008](./ADR-008-i18n-consistency.md) | 双语 i18n 键全量一致性测试 | Accepted | 2025-09 | i18n-consistency.test（双向相等断言） |
| [ADR-009](./ADR-009-icon-platforms.md) | 5 平台图标体系对齐（29 PNG 实测口径） | Accepted | 2026-10-16 | scripts/chain-verify.mjs + e2e 资产用例 |
| [ADR-010](./ADR-010-completions-5d.md) | 补全引擎五维协同源 | Accepted | 2026-10-05 | terminal-completions.test 41 用例 |
| [ADR-011](./ADR-011-unit-isolation.md) | unit 档禁真实网络/文件系统/时间 | Accepted | 2025-09 | vitest projects 分级 + 零外部依赖审计 |
| [ADR-012](./ADR-012-baseline-ratchet.md) | size/knip/color/dup 四基线只减不增 | Accepted | 2026-10-16 | 四个 check-*.mjs（超线 exit 1） |
| [ADR-013](./ADR-013-strict-flags.md) | TS 双旗标（noUncheckedIndexedAccess + exactOptionalPropertyTypes） | Accepted | 2026-10-16 | `pnpm typecheck`（tsc 内建强制） |
| [ADR-014](./ADR-014-lint-fp.md) | 悬空 Promise 零容忍（type-aware 专项） | Accepted | 2026-10-16 | `pnpm lint:fp` |
