# ADR-011: unit 档禁止真实网络/文件系统/时间

- 状态：Accepted
- 日期：2025-09（分级奠基；2026-10-16 S4 零外部依赖维度实证并沉淀全套判例）
- 决策者：质量架构师
- 关联：vitest.config.ts projects · integration 项目（显式开关）· 各测试判例

## 背景 Context

unit 测试一旦依赖真实网络/文件/时间，就同时获得三类不稳定：网络抖动假败、文件系统状态残留、真实时间导致的时序 flaky。项目曾有过 FamilyEntertainment 并发 flaky、console-relay ECONNRESET 等教训——根因都可追溯到「隔离不彻底」。

## 决策 Decision

unit-dom（jsdom）/ unit-node（node）两档**零外部依赖**：
- **网络**：一律 `vi.stubGlobal("fetch")` 或 `vi.spyOn(globalThis, "fetch")`（ADR-005 的 lib/http.ts 底层是 globalThis.fetch，可拦）；WS 走 mock 实例；**裸网络请求禁止**。
- **文件系统**：IndexedDB 走 yyc3-storage **降级契约**（jsdom 无 IDB → `idbGetAll` catch 返回 []，写函数静默容错）；localStorage 用 jsdom 原生 + beforeEach 清理；真实 IDB 读写归 integration 档（`YYC3_TEST_INTEGRATION=1` 显式开关才跑）。
- **时间**：`vi.useFakeTimers()` + `advanceTimersByTimeAsync` + **try/finally useRealTimers**（不还原会污染后续用例）。
- **环境事实如实登记**：jsdom `window.location` 是 LegacyUnforgeable（不可伪造 hostname，沙箱分支须 per-file `@vitest-environment-options`）；`ontouchstart` 恒在（isTouch false 分支真机域不可构造）；`.lucide-circle` 等 lucide 0.487 类名以实测为准。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| testcontainers / 真实服务 | 集成置信度高 | 慢、环境依赖、CI 复杂 | 归 integration 档显式开关 |
| MSW 拦截层 | 声明式网络 mock | 引依赖；stubGlobal 已够且零成本 | 判例优先 |
| 放任混用 | 写起来快 | flaky 蔓延，测试价值崩塌 | FamilyEntertainment 教训 |

## 后果 Consequences

- 正面：3230 用例本地秒级~分钟级全绿；S4 零外部依赖维度 PASS；flaky 被定位为「并发资源竞争」而非网络抖动（R3 判例——maxWorkers 封顶 8 解决）。
- 负面：mock 基建有学习成本（判例：mock 整库成 `{}` 会丢 handlers 使分支永不可测——需捕获式 mock）；部分分支在 jsdom 环境事实下不可构造（如实登记为真机域）。
- 中性：integration 档作为真实依赖的逃逸阀（显式开关，CI 默认不跑）。

## 验证方式 Verification

S4 十维度之「零外部依赖」PASS（fetch 全 stub/spy、IDB 降级、fake timers）；CI unit 档无网络/文件挂载。

## 回滚路径 Rollback

放宽 = 允许真实依赖（vi.stubGlobal 删除即可）——但 flaky 将回归；无合理回滚场景。真实依赖需求由 integration 档承载（架构内已有出口）。
