# ADR-010: 智能补全引擎采用五维协同源

- 状态：Accepted
- 日期：2026-10-05（v2 修正表 + 闭环核心落地；S5 深度档推满 L/F 100）
- 决策者：首席架构师
- 关联：src/app/lib/terminal-completions.ts · terminal-completions.test.ts（41 用例）· IntegratedTerminal

## 背景 Context

集成终端的命令补全若只做静态命令表，体验止步于「背命令」；本项目已有丰富的动态数据源（节点清单/环境变量/家族成员/路由表/用户命令历史）散布各处。问题是：补全该聚合哪些源、如何排序、如何避免数据源故障拖垮补全本身。

## 决策 Decision

**五维协同源 + 频率闭环**：
1. **静态命令表**（TERMINAL_COMMANDS/BASE_COMMANDS 模块常量，有限键 Record——严格旗标下索引精确）；
2. **动态节点名**（nodeStore.getAll，catch 降级空数组——数据源故障不拖垮补全）；
3. **环境变量名**（getEnvConfig，同样降级）；
4. **路由表**（TERMINAL_ROUTES 与 routes.ts 对齐守卫——测试断言路由漂移即 FAIL）；
5. **历史-频率反馈**（loadCommandHistory + getCommandStats，用户用得越多排序越准——闭环核心）。

排序 `byFrequencyThenValue`：频率降序 → localeCompare 平局决胜；大小写不敏感前缀匹配；上限 12 条；`recordCommand` 触发 >200 键淘汰。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 纯静态表 | 零复杂度 | 无个性化、无动态感知 | 浪费已有数据源 |
| 全动态（含 LLM 生成建议） | 智能化 | 延迟/依赖/成本，终端场景过重 | 看盘终端要毫秒响应 |
| 五维协同 + 频率闭环（选定） | 个性化 + 上下文感知 + 降级安全 | 引擎复杂度高（需全分支测试） | 41 用例覆盖 L/F 100 |

## 后果 Consequences

- 正面：补全随使用越用越准；节点/env 变化即时反映；数据源全挂仍保静态兜底（降级安全）；路由对齐守卫使补全与路由表单一事实源绑定。
- 负面：14 分支臂被论证不可构造（防御性 `?? []` 恒有键等——S5 豁免登记），branches 86.27% 成为该文件理论天花板；引擎单文件 400+ 行接近函数体量心智负担。
- 中性：首词规范化（Perrito trim/split）使空串兜底臂不可达——属防御性冗余。

## 验证方式 Verification

terminal-completions.test 41 用例（一级命令/cpim 子命令/env/family/路由/ai 意图/路径/历史频率闭环/路由对齐守卫/质量）；S5 覆盖率 L=100 F=100。

## 回滚路径 Rollback

引擎为纯函数库，消费方仅 IntegratedTerminal/useTerminal——回退到静态表 = 删动态源调用（≈1h）；频率数据独立存储，回滚无损。
