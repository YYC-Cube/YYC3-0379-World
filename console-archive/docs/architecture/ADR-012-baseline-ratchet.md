# ADR-012: size/knip/color/dup 四基线只减不增

- 状态：Accepted
- 日期：2026-10-16（dup/color 两门禁新落地；size/knip 自 2025-09 起运行）
- 决策者：首席架构师 + S8/S3 审核官
- 关联：scripts/check-size.mjs / knip-check.mjs / check-color-budget.mjs / check-dup-budget.mjs · 对应 *.json 基线

## 背景 Context

代码库的四类「熵」——文件体量、死代码、硬编码色值、重复逻辑——都有共同的腐烂模式：**每次 PR 贡献一点点，无人察觉，直到不可收拾**。逐 PR 评审这些维度不可靠（评审者注意力有限），需要机械化棘轮（ratchet）：基线锁定现值，只允许下降。

## 决策 Decision

四个独立门禁，同一纪律（**基线只减不增**：count > baseline → exit 1 阻断；下降后人工下调基线 JSON 并附原因+日期，**禁止上调**）：
1. **size**（check-size.mjs）：超标文件基线表（ServiceConnectionTest 406 / AIFamilyDesignDoc 88）+ 新超标文件告警锁定；函数级 ≤800 行走 eslint max-lines-per-function。
2. **knip**（knip-check.mjs）：unused exports 7 / devDeps 3 / files 0 等全类别基线；判例盲区白名单（UI 生态 30 项 + 工具链二进制 jscpd/@ast-grep/cli）。
3. **color**（check-color-budget.mjs）：6080→5486（五片迁移真实下降）；增量必须走 Design Tokens。
4. **dup**（check-dup-budget.mjs）：jscpd 5.4.1，**生产码口径**（排除 __tests__）15 克隆/237 行冻结；测试样板重复属声明可接受类别。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 无基线（放任） | 零维护 | 熵只增不减 | S3 实证：fetch 直连 33 处/类型重复 4 组就是这么攒出来的 |
| 高压清零（一次性大重构） | 一步到位 | 巨石重构风险、阻塞特性交付 | 违反「不做超出任务的重构」红线 |
| 棘轮基线（选定） | 冻结存量+逼增量收敛 | 基线需人工维护（下调留痕） | 维护成本极低且有脚本自证 |

## 后果 Consequences

- 正面：ServiceConnectionTest 406/406 紧平衡实证「+1 即拦」；dup 门禁在 S5 热点批真实拦截过 +5 测试域克隆（口径随之收紧为生产码——**门禁自证有效**）；色值五片迁移使基线 6080→5486 真实下降 594。
- 负面：紧平衡文件（406/406）任何一行增长即破线——需同行内联或 sibling 拆分；基线 JSON 人工下调有出错面（负例探针已验证脚本行为）。
- 中性：豁免/白名单条目须附原因+证据（与 gitleaks 豁免同纪律）。

## 验证方式 Verification

`pnpm size:check / color:check / dup:check / node scripts/knip-check.mjs` 四命令各自 exit 码；color/dup 均有负例探针记录（调低基线→FAIL）。

## 回滚路径 Rollback

删除对应 check-*.mjs 与 package.json script 即解除；基线 JSON 手动改回即「抬基线」——被纪律与评审拦截。四门禁相互独立，可单独回滚某一个。
