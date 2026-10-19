# 边界规则 + 违规案例 + 修复指引 — YYC³ Token Console

> 硬门禁: eslint boundaries（六层 elements）· ast-grep（7 规则全 error）· 四基线棘轮 · 元门禁 20 探针
> 本文 = 规则速查 + **真实违规案例库**（全部来自本仓审计实录）+ 修复模式。

## 1. 层级边界（eslint boundaries）

| from | 允许 to | 禁止 |
| --- | --- | --- |
| components | components/hooks/stores/lib/types + app 入口 | — |
| hooks | hooks/lib/types | **components / stores** |
| stores | lib/types | components/hooks |
| lib | lib/types | components/hooks/stores |
| types | （不引任何层） | 全部 |
| tests | 被测对象全域 | — |

**真实违规案例**：`useWebSocketData → stores/dashboard-stores` 跨层（2026-09-24 门禁失效期间漏入）→ 修复 = 数据经参数传入或下沉 lib。**修复模式**：hooks 需要组件域数据时，由调用方（组件）取数后经 props/参数传入。

## 2. 域边界（ADR-002 约定）

- 域目录（ai-family/ide/service-test/design-system…）同属 components 层，互引允许；
- **跨域复用逻辑必须下沉 hooks/lib/types**——真实案例：service-test 域曾 import `stores/dashboard-stores.DBConnection` → S2 改名 StoredDBConnection 后单点修正（契约单源收益实证）；
- 网络请求统一 `lib/http.ts`——真实案例：**33 处直连 fetch**（hooks/components）→ L 批收敛残留 0。

## 3. 反模式边界（ast-grep 7 规则）

| 规则 | 禁止 | 替代 |
| --- | --- | --- |
| no-bare-websocket | 裸 `new WebSocket` | `globalThis.WebSocket` 解析（测试 stub 依赖） |
| no-raw-localstorage | 裸 localStorage | lib/yyc3-storage 封装 |
| no-hardcoded-secret-literal | 密钥字面量 | env / 用户输入（占位符用 sk-xxxx 形式+注释） |
| no-document-write | document.write | Blob URL（useReportExporter 判例） |
| no-innerhtml-assignment | innerHTML 赋值 | JSX 渲染 / 转义（确需则双豁免+原因） |
| no-process-env-in-src | src 内 process.env | import.meta.env / lib/env-config |
| no-string-timer | setTimeout("code()") | 函数引用 |

## 4. 类型边界（ADR-013 双旗标）

违规模式与修复（真实案例库）：

| 违规 | 修复（优先级序） | 实例 |
| --- | --- | --- |
| 索引访问可能 undefined (TS2532) | `?? 中性兜底` > `?.` > 守卫 > `!`(不变量) | `sessions[0].title` → `sessions[0]!.title`（fixture 不变量） |
| 可选属性赋 undefined (TS2375/2379) | 条件展开 > 类型 `T \| undefined`（仅私有类型） | `latencyMs` → `...(latencyMs !== undefined ? { latencyMs } : {})` |
| Radix 可选 props (EOP) | 条件展开保留非受控语义 | ui/ 4 文件 `checked`/`defaultValue` |
| 同名异扩展测试文件 | **禁止**——TS 程序按优先级去重 | useBigModelSDK.test.tsx → -behavior 改名 |

**覆盖陷阱**：模板字符串内的假文件文本会被 grep 误判为类型（ide-mock 三组误报教训）；`?? 可证死兜底` 翻 `!` 消覆盖率假分支。

## 5. 体量/熵边界（ADR-012 四棘轮）

| 门禁 | 基线 | 违规修复模式 |
| --- | --- | --- |
| size | ServiceConnectionTest 406 / AIFamilyDesignDoc 88 + 函数 ≤800 | sibling 拆分（SystemSettings→7 文件判例）· 同行内联 |
| knip | exports 7 / devDeps 3 / files 0 | 死导出删除（附 git blame）；盲区白名单留证 |
| color | 5486 冻结 | 新色走 Design Tokens；迁移批人工下调（附原因+日期） |
| dup | 生产码 15 克隆/237 行（排除 __tests__） | 抽 shared/contracts；测试域样板豁免（口径判例） |

## 6. 依赖边界（红线）

精确锁定（无 `^`/~`）· catalog 高频族 · overrides 必带「原因+复核日期」· 供应链守卫拦截（bidi/workbox 判例）→ **降版本或弃用，不绕守卫** · ws 仅运行时可选动态 import（ADR-005 折中）。

## 7. 新增边界规则流程

1. 识别重复违规模式（≥3 处人工修同类问题）；
2. 选门禁载体（eslint 规则 / ast-grep 规则 / 基线脚本）；
3. **首测全仓误报数**（FP 评估——dup/color 均经此步）；
4. 存量超限 → 基线棘轮锁现值，或先清零再启用；
5. guardrail-probe 补探针（违规样本必拦断言）；
6. AGENTS.md 登记 + 本文案例库补条目。
