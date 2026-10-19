# ADR-008: 双语 i18n 键全量一致性测试

- 状态：Accepted
- 日期：2025-09（i18n-consistency.test 奠基）
- 决策者：首席架构师
- 关联：src/app/i18n/{zh-CN,en-US}.ts · i18n-consistency/keys/packs 测试 · e2e fullchain i18n 用例

## 背景 Context

看盘系统面向双语用户（zh-CN 主 + en-US）。i18n 的经典腐烂路径是：加功能只写中文键 → 英文包静默缺键 → 英文用户看到裸键名或 undefined。人工核对不可持续。

## 决策 Decision

1. **类型层**：`en-US` 的类型标注为 `TranslationKeys = DeepStringify<typeof zhCN>`——TS 编译期强制英文包键结构与中文包**完全同构**（多键/少键/错型即编译错）。
2. **测试层三重守护**：i18n-consistency（键数量相等 + 双向 contains 断言 + 无空值 + 命名空间完整性）、i18n-packs（结构/翻译非空/模板变量一致性）、pwa-i18n-types——共 153 用例中 i18n 域占 ~60。
3. **e2e 层**：zh→en→zh 切换断言（存储态 `yyc3_locale` 轮询 + 正文宽检 + 中文残留零）。
4. **t() 插值**：`{var}` 模板变量 + vars.n 形态，packs 测试断言变量一致性。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 仅类型约束 | 编译期即拦 | 类型不覆盖值语义（空串/漏翻译值可通过） | 补测试层堵值缺口 |
| i18next 等库 | 生态/惰性加载 | 引依赖 + 键命名不受类型约束 | 自研 t() 极简且够用 |
| 仅人工核对 | 零成本 | 必然腐烂 | 反例即立项动机 |

## 后果 Consequences

- 正面：双语键零漂移（S13 实测 missing/extra 双空）；模板变量漂移被测试拦；e2e 切换无残留实证。
- 负面：每加功能必须同步双语言包（成本前置但必要）；类型递归 DeepStringify 使大包类型检查略慢（可接受）。
- 中性：语言键为 `yyc3_locale`（与 ide-mock 的 `yyc3-lang` 同名易混——S11 判例留档）。

## 验证方式 Verification

`pnpm exec vitest run src/app/__tests__/i18n-*.test.ts pwa-i18n-types`（~60 用例）+ e2e i18n 切换用例。

## 回滚路径 Rollback

删除类型标注或测试 = 解除约束（一行/一文件）；但双语腐烂将在数个迭代内重现——无合理回滚场景。
