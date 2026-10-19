# CHANGELOG 模板 — Keep a Changelog 风格（中文优先）

> 用法：发版时将 Unreleased 段整理为版本段（对照 VERSIONING 分段）；条目从 Conventional Commits 汇总，面向使用者描述**可观察变化**（非提交罗列）。

---

# Changelog

本项目的所有显著变更将记录于此。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循[语义化版本](./VERSIONING.md)。

## [Unreleased]

### Added 新增
- （示例）NAS console 运维台 `ops.mjs`：status/verify/heal/boot 子命令与 TTY 菜单

### Changed 变更
- （示例）静态服务启用 gzip + immutable 缓存（Lighthouse FCP 2.0→0.8s）

### Deprecated 弃用
- （示例）`/db-connections` 路由 → 重定向 `/database`

### Removed 移除
- （示例）`/users` mock 用户 CRUD（R3 清理批，git 历史留档）

### Fixed 修复
- （示例）`/console/settings` 页面-API 同路径冲突 → 内容协商分流

### Security 安全
- （示例）jti 吊销 + 登录审计 JSONL（logout 后旧 Cookie 立即失效）

---

## 条目书写规则

1. **面向使用者**：写"发生了什么/影响什么"，不写提交哈希罗列（哈希在 Release 正文附）；
2. **每条一类**：Added/Changed/Deprecated/Removed/Fixed/Security 六分法，不混类；
3. **附证据锚点**：重大条目尾注 `(证据: docs/audit/<ts>/)` 或 ADR 编号；
4. **破坏性条目**：加粗 + 迁移说明链接（C4 红线）；
5. **同发版同步**：tag 打出时 Unreleased → 版本段 + 日期。

## 示例（真实节选风格）

```markdown
## [0.2.1] - 2026-10-17
### Fixed 修复
- `/console/settings` 页面-API 同路径冲突：浏览器导航误收 JSON 文档 → 内容协商分流（证据: docs/audit/20261016T2350-s11-e2e/）
### Security 安全
- jti 吊销机制上线：logout 后旧会话 Cookie 立即失效；登录/登出审计 JSONL 落盘（NAS+ECS 实测）
```
