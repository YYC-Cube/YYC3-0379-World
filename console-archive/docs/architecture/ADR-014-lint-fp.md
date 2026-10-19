# ADR-014: 悬空 Promise 零容忍（type-aware 专项 lint:fp）

- 状态：Accepted
- 日期：2026-10-16（S7 缺口登记 → 同日落地）
- 决策者：首席架构师 + S7/S8 审核官
- 关联：eslint.fp.config.js · package.json `lint:fp` · 78 处修复（afb077d）

## 背景 Context

悬空 Promise（floating promise）的典型事故：IDB 写失败静默丢失用户数据、导航/上报 Promise rejection 变 unhandled rejection 白屏。`@typescript-eslint/no-floating-promises` 需要 **type-aware**（parserOptions.project）——主 lint 为保持 3.7s 快跑不做类型解析，所以该规则长期缺位（S7 如实登记为缺口）。

## 决策 Decision

独立专项配置 `eslint.fp.config.js`（主配置 + parserOptions.project + `no-floating-promises: error`），`pnpm lint:fp` 执行、`--max-warnings 0` 收口。落地日修复存量 78 处，修复模式纪律：
1. **`void` 前缀**：被调函数体内自带 try/catch 或 .catch 的有意 fire-and-forget（react-router 7 `navigate` 返回 `void | Promise` 一律 void）；
2. **非阻塞 `.catch`**：IDB 辅助持久化（内存态已生效，await 会推迟 toast 时序——语义判断留注释）；
3. **`await`**：顺序语义且调用方可承接 rejection。
测试侧 `act()` 回调返回 Promise 时须 `await act` + 外层 it 转 async。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 合入主 lint | 单命令 | 主 lint 3.7s → 类型解析后显著变慢（每次保存/CI 都付） | 快慢分离 |
| 不治理 | 零成本 | 静默失败持续累积（78 处实证已存在） | S7 红线 |
| ast-grep 自研规则 | 不需类型信息 | AST 层无法判定返回类型（Promise 与 void 调用形态相同），误报率高 | type-aware 才是正解 |

## 后果 Consequences

- 正面：78 处真实悬空（含 IDB 静默丢数据风险点）全部获得显式处置与语义注释；lint:fp 0 固化。
- 负面：CI 多一条命令（秒级）；开发者需理解 void/.catch/await 三选一的语义纪律。
- 中性：专项配置与主配置共享规则栈，无漂移风险（import 复用）。

## 验证方式 Verification

`pnpm lint:fp`（--max-warnings 0）；S16 后纳入 AGENTS 门禁速查；本配置自身被 guardrail-probe 的 eslint 探针间接覆盖（同工具链）。

## 回滚路径 Rollback

删除 eslint.fp.config.js 与 script 即解除（一行）；78 处修复本身是纯收益不回退。
