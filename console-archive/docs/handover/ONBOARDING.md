# 新人上手指南 — ONBOARDING（Day 1 / Day 3 / Day 7）

> 目标：**1 天跑起来 · 3 天提第一个 PR · 1 周能值守**。
> 环境前提：macOS/Linux + 管理员可装依赖；Windows 建议 WSL2。

---

## Day 1 · 跑起来

- [ ] 克隆仓库 + `pnpm install`（pnpm 12，Corepack 可供；Node 22+）
- [ ] `pnpm dev` → http://localhost:3030 （默认 Mock/本地闭环，无需任何凭据）
- [ ] `pnpm run doctor` → 12/12 全绿（⚠️ 裸 `pnpm doctor` 会执行 pnpm 内建命令——判例）
- [ ] 通读 **AGENTS.md**（项目总纲：红线/分层/域契约/门禁速查）
- [ ] 通读 **README.md**（特性/门禁表/图标链路）
- [ ] 浏览 `docs/YYC3-开发者文档/`（CICD/LABELS/CONTRIBUTING）
- [ ] 可选：`pnpm build && pnpm serve:local` → http://localhost:3118 体验 LAN 部署形态

**Day 1 自检**：`pnpm typecheck && pnpm test:unit` 本地全绿；能说出六域是哪六个。

## Day 3 · 提第一个 PR

- [ ] 认领 `good-first-issue`（或自提：先跑 `pnpm guardrail-probe`/门禁找改进点）
- [ ] 派生分支：`git checkout -b feat/your-topic`
- [ ] 开发前读 [BOUNDARIES.md](../architecture/BOUNDARIES.md)（层级/域/反模式边界 + 违规修复模式）
- [ ] 本地门禁（与 CI 同款）：`pnpm typecheck && pnpm lint && pnpm lint:fp && pnpm test:unit`
- [ ] 按 PR 模板提交；标题 Conventional Commits；**标签 1 类型 + 1 模块**
- [ ] 变更分级自查（[CHANGE-MANAGEMENT.md](../release/CHANGE-MANAGEMENT.md) 矩阵——C2+ 记得回滚剧本）

**Day 3 自检**：PR 绿；能解释为什么 hooks 不能 import stores；能说出三处对齐的图标链路。

## Day 7 · 能值守

- [ ] 通读 **docs/ops/RUNBOOK.md**（拓扑/探针/升级路径）
- [ ] 完成**一次沙箱演练**（SAFE 模式）：
  - `pnpm guardrail-probe`（看 20 探针如何抓违规）
  - 本地起 `pnpm serve:console`（带测试 env）→ 故意错密码看 401 → 正确密码看穿门 → 杀进程再起
  - `node scripts/chain-verify.mjs`（图标链路断点体验：临时改名一个 manifest 图标看 missing 输出，改回）
- [ ] 通读 **docs/observability/METRICS-DICT.md**（12+ 真实指标）+ **SLO.md**
- [ ] 通读 **docs/architecture/ARCHITECTURE.md** + ADR-INDEX（14 条决策的 why）
- [ ] 值守考核（L1 签出）：口述 T1/T2/T7 三棵故障树的处置路径 + 完成一次 ONCALL-CHECKLIST 交接演練
- [ ] 可选深水区：`docs/audit/INDEX.md`（22 目录审计链——了解每条门禁为什么存在）

**Day 7 自检**：能独立完成 ONCALL-CHECKLIST 五段；能对一个陌生报错给出「先查哪棵树」。
