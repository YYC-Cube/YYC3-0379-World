# 版本号规范 — VERSIONING（语义化 SemVer）

## 格式：`vMAJOR.MINOR.PATCH`（tag 触发 release.yml）

| 段 | 递增条件 | 示例 |
| --- | --- | --- |
| MAJOR | C4 破坏性：删 API/改契约/迁移不可兼容/配置键更名 | v1.0.0 → v2.0.0 |
| MINOR | C2/C3 向后兼容新特性：新端点/新面板/新门禁 | v0.2.0 → v0.3.0 |
| PATCH | C1/C0 修复与文档：bug 修复/重构/文档/基线下调 | v0.2.0 → v0.2.1 |

## 本仓特化规则

1. **0.x 阶段**（当前 0.2.0）：MINOR 可承载激进变更（SemVer 0.x 惯例），但对外契约（/console/* API、IDB StoreName、LS 键名）的变更仍按 MAJOR 纪律走 C4 流程——**内部松、契约严**。
2. **tag 即发布**：`v*.*.*` push 触发 release.yml（GitHub Release + 制品归档）；非 tag push 不发版。
3. **版本单一事实源**：`package.json version` + tag 双写（release 时同步）。
4. **服务端部署件不独立发版**：跟随前端 tag（四 mjs 与产物同仓同发）；紧急热修允许 patch 提前部署（部署记录注明 tag 差异）。
5. **预发布**：`v0.3.0-rc.1` 形态（release.yml prerelease 标记），仅在 C4 迁移演练时使用。
6. **禁止**：跳段（0.2.0→0.4.0 需说明）/ 同 tag 重打（force tag 禁）/ 无 CHANGELOG 的 tag。

## 与变更分级联动

C0/C1 → PATCH · C2/C3 → MINOR · C4 → MAJOR（0.x 期可 MINOR+C4 流程）。
