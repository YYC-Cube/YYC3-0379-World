# ADR-002: 六域互不直连，跨域必须走 contracts 下沉

- 状态：Accepted
- 日期：2026-10-16（S3 治理批制度化；分层契约自 2025-09 起由 eslint boundaries 强制）
- 决策者：首席架构师 + S3 审核官
- 关联：eslint.config.js boundaries 段 · AGENTS.md「域目录契约」· ADR-012

## 背景 Context

components 层下有 ai-family / ide / service-test / design-system 等域目录，六业务域（监控/运维/AI 智能/AI Family/开发规范/系统管理）的页面散布其间。若域间随意 import 复制实现，演进时会出现「改一处坏三处」的隐性耦合。需要回答：域与域之间到底允不允许直接引用？

## 决策 Decision

**两层规则**：
1. **层级契约（硬门禁）**：components → hooks → stores → lib → types 单向依赖，hooks 禁引 components/stores，types 不引任何层——eslint-plugin-boundaries 六层 elements 强制，违规即 CI 阻断。
2. **域契约（制度化约定）**：域目录（ai-family / ide / service-test / design-system 等）同属 components 层，层级上互引被允许；但**跨域复用逻辑必须下沉 hooks/lib/types（contracts），禁止域间复制粘贴实现**；网络请求统一走 `lib/http.ts`。六域互不直连指业务逻辑互不依赖，页面路由层（routes.ts）是唯一合法的全域组装点。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 域间完全互斥（AST 级禁止跨域 import） | 隔离最彻底 | 域目录物理边界与六域语义不一一对应（六域是导航分类），误报率高 | 与仓库物理结构不匹配 |
| 完全自由互引 | 零成本 | 复制粘贴扩散、无契约 | 已有 S3 实证（类型重复 4 组、fetch 直连 33 处） |
| 层级契约 + 域下沉约定（选定） | 硬门禁保层级、约定保域间收敛 | 域间轻度耦合仍可能（下沉不及时） | 与物理结构匹配且已有治理路径 |

## 后果 Consequences

- 正面：跨域逻辑有唯一归属（hooks/lib/types）；S3 治理批沉淀 33 处 fetch → lib/http.ts、类型重复 4 组消歧；新增域有明确路径。
- 负面：「下沉不及时」无自动检测（S7 如实登记 floating-promise 同级缺口）；六域互斥未 AST 化。
- 中性：域目录新增组件不触发门禁，靠评审。

## 验证方式 Verification

`pnpm lint`（boundaries 0 违规）；`pnpm exec eslint -c eslint.fp.config.js`；madge 循环检测（S3 实证 0 环）；跨域重复由 `pnpm dup:check` 生产码口径间接守护。

## 回滚路径 Rollback

删除 boundaries 配置段即可解除层级强制（一行）；域契约为文档约定，无回滚成本。风险低——层级规则运行两年零例外清单增长。
