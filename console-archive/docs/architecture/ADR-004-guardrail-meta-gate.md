# ADR-004: 元门禁 guardrail-probe 防假绿

- 状态：Accepted
- 日期：2026-09-24（P0-3 立项；2026-10-16 扩容至 20 探针）
- 决策者：元门禁设计师
- 关联：scripts/guardrail-probe.mjs · S7 反模式 · S10 元门禁阶段

## 背景 Context

2026-09-24 审核发现**两条架构防腐门禁同时静默失效**：eslint-plugin-boundaries 升级 7.2 后配置语法脱节、ast-grep 规则与 CLI 版本不匹配——门禁空心但 CI 全绿（useWebSocketData→stores 跨层、裸 new WebSocket 双双漏检）。结论：**门禁本身也需要被门禁**。

## 决策 Decision

`guardrail-probe.mjs`：运行时向隔离沙箱（`src/app/hooks/__guardrail_probe__/`，finally 强制清理）植入**已知违规样本**，跑真实门禁命令，断言**必须拦截（exit≠0）**；任一未拦截 = 门禁失效 = exit 1 硬阻断。探针与生产门禁**同源**（同一 sgconfig/同一 eslint/同一 config），禁止单独维护一套。2026-10-16 扩容：ast-grep 7 规则×双语言 14 探针 + boundaries 1 + 复合门禁 5（tsc/gitleaks/knip/size 受控变异/coverage 阈值执法）= **20 探针**。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 信任工具版本锁定 | 零维护 | 版本锁定挡不住配置脱节（本次失效即证据） | 已被现实打脸 |
| CI 里人工抽查 | 灵活 | 不可持续、易忘 | 人肉不防腐 |
| 探针植入+断言拦截（选定） | 自动、同源、可重复 | 探针自身样本可能缺陷（gitleaks 样本两度被反向修正——32 位不够/低熵被 stopwords 豁免） | 缺陷可迭代收敛，已修复 |

## 后果 Consequences

- 正面：门禁失效从「数月后发现」变为「下次探针跑即阻断」；20/20 双跑稳定；探针失败会转储门禁输出辅助定位。
- 负面：样本需随规则演进维护（如 gitleaks 规则阈值变化）；探针运行 ~3s 计入 CI。
- 中性：dup/color 的负例验证暂为一次性手工，可并入脚本（backtrace 留档）。

## 验证方式 Verification

`pnpm guardrail-probe` 双跑 20/20 + git status 零残留（隔离性）；S10 阶段十维判定全 PASS。

## 回滚路径 Rollback

删除探针脚本与 CI 步骤即可——但等于退回「门禁空心不自知」状态，无合理回滚场景。探针自身的回滚（某个探针误报）= 修正样本形态（如 gitleaks 高熵样本判例），非删除。
