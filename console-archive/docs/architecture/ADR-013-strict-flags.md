# ADR-013: TypeScript 双旗标（noUncheckedIndexedAccess + exactOptionalPropertyTypes）

- 状态：Accepted
- 日期：2026-10-16（S2 深度档落地；764 错误清零后固化）
- 决策者：首席架构师 + S2 审核官
- 关联：tsconfig.json · S2 审计两轮记录 · backlog-resolution L-11

## 背景 Context

`strict: true` 不含两个最严格的旗标：`noUncheckedIndexedAccess`（索引访问返回 `T | undefined`）与 `exactOptionalPropertyTypes`（可选属性不接受显式 undefined）。本项目是**看盘系统**——索引越界静默返回 undefined 然后被渲染成 `NaN`/空白，正是数据正确性的天敌。但两旗标在存量代码上初始成本高（S2 首测 764 errors）。

## 决策 Decision

2026-10-16 一次性清零 764 处后**双旗标写入 tsconfig 固化**。修复模式优先级（已成判例）：同行 `?? 语义中性兜底` ＞ `?.` 可选链 ＞ 条件展开 `{...(x !== undefined ? { x } : {})}`（EOP/Radix 摩擦标准解）＞ 守卫 ＞ `!`（仅显然不变量且克制）。**可证死兜底翻 `!`**（正则必选分组/split[0] 恒非空）既满足旗标又消覆盖率假分支。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 仅 strict | 零迁移成本 | 索引访问/可选属性两类 undefined 逃逸 | 数据正确性风险 |
| 双旗标 + 全量 `!` | 快速清零 | 断言滥用掩盖真实缺陷 | 模式纪律约束 `!` 仅限显然不变量 |
| 双旗标 + 模式纪律（选定） | 编译器级保证 + 断言克制 | 一次性 764 处成本（已付） | 已完成，属沉没成本后的纯收益 |

## 后果 Consequences

- 正面：索引访问缺陷在编译期暴露（S11 同名 .ts/.tsx 去重判例中，游离 tsc 的测试文件进入程序即刻现形 6 处 TS2532）；可选属性语义精确（Radix 非受控语义得以保留）。
- 负面：新增代码的索引访问/可选属性写法有学习成本（判例集已入记忆与 AGENTS）；`exactOptionalPropertyTypes` 与第三方库偶有摩擦（ui/ 4 文件条件展开例外已 AGENTS 留档）。
- 中性：覆盖率分支点因此增加 ~270（已由死臂翻转+真覆盖用例消化）。

## 验证方式 Verification

`pnpm typecheck`（tsconfig 内建）；S2 复跑 0 错误；后续所有批次零回退。

## 回滚路径 Rollback

删除两行 tsconfig 即回退——但等于放弃已支付的 764 处修复价值；技术易、决策上无理由。
