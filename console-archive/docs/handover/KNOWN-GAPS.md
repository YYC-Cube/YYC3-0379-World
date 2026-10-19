# 已知缺口与后续计划 — KNOWN GAPS

> 与 backlog-resolution.md（执行细节）互为索引；本文件只列**开口本身**与触发条件。全部为条件触发型，无自由行动项积压。

## 代码 / 架构类

| ID | 缺口 | 触发条件 | 计划 |
| --- | --- | --- | --- |
| L-06 | jti 吊销内存态（重启清空，TTL 12h 封顶） | 多管理员需求出现 | console-revoked.json 持久化，0.5d |
| L-11 | coverage include 未含 deploy//routes/i18n | deploy/*.mjs 补 .d.ts 批（顺带消 6 处 @ts-expect-error） | 口径扩展+阈值重评，0.5d |
| — | 网关服务端缺 active_requests/breaker/gpu 指标（METRICS-DICT 差距表） | 后端增强批 | exporter 化 |
| — | ai-family 域 components/ai-family/** 在 knip ignore（字符串路由不可达盲区） | 路由静态化重构时 | 纳入死代码扫描 |
| — | console-audit.log 无自动轮转 | 磁盘压力出现 | logrotate 或按月切 |

## 测试 / 质量 类

| ID | 缺口 | 触发条件 | 计划 |
| --- | --- | --- | --- |
| DEF-05 | 33+ 处已论证不可构造豁免臂（terminal-completions 14+2 / hooks 各域 9 / family 子页 8） | 源码重构触及对应文件 | 随批收敛防御臂 |
| L-07 | e2e 登录态未 setup-project 化（限流 5/5 满额） | 需新增登录态用例时 | 0.5d |
| — | branches 余量 6.22%（86.22 vs 80） | 大分支特性前 | 先补热点测试 |
| — | FamilyEntertainment 并发敏感（R3/R 族判例） | 复现即 isolate | vitest 配置收紧 4 |

## 基础设施 / 运维 类

| ID | 缺口 | 触发条件 | 计划 |
| --- | --- | --- | --- |
| DEF-02 | @reboot 终验未做真实重启（三环静态已验） | NAS 自然断电/维护重启 | ops.mjs boot+verify |
| — | 后端 deploy key 未配（origin push 403） | 需本机推后端仓 | GitHub deploy key，运维决策 |
| — | 后端 prometheus 声明态重建终验（037dac3 已修声明） | NAS 运维窗口（daocloud 源判例） | compose up -d prometheus |
| — | ECS console-audit.log 轮转 | 磁盘压力 | logrotate |
| — | Metrics 差距（active_requests/breaker/gpu exporter） | 后端增强批 | METRICS-DICT 差距表 |

## 产品 / 决策类

| ID | 缺口 | 触发条件 | 计划 |
| --- | --- | --- | --- |
| DEF-03 | 路由级角色守卫（当前无守护对象） | 多角色页面恢复 | RequireRole+路由测试 |
| L-12b | 图表种子派生（radar 五轴语义） | 产品定义轴与归一化 | 0.5d 含确认 |
| DEF-01 | 色值存量 5486（五片已完成 594） | 长期分批 | SecurityMonitor(68 余)→AIAssistant(54 余)→…按首片模式 |

> 注：SecurityMonitor/AIAssistant/DatabaseManager 的存量数已随第五片更新——精确余量以 color-budget.json topFiles 实时为准。
