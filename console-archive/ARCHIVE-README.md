# Token Console 归档 — console-archive

> 归档日期: 2026-10-17 · 来源: `YYC3-AI-API-Token-Console`（前端仓，commit bbb7cb3 冻结版 + 三笔 hotfix 至 52da6f2）
> 性质: **归档复制，原仓库未删除**（git 历史完整保留于 YYC3-AI-API-Token-Console，可随时复活）。
> 归档原因: 项目降级维护——Token Console（B 端看盘面板）的运维与文档资产统一并入网关仓，使网关维护者在同一仓库获得完整上下文。

## 归档时的生产在役状态（复制≠下线）

**三端仍在线运行，不受归档影响**（服务件源码在本目录 `deploy/`）：

| 端点 | 形态 | 状态（归档日实测） |
| --- | --- | --- |
| https://api.0379.world/console | 公网 HMAC（ECS :3100, PM2 yyc3-console） | 200 · gzip 生效 · jti/审计/内容协商全量 |
| http://192.168.3.45:3210 | NAS 本机（PM2 yyc3-console-nas） | enabled · 根路径 302 → /console/ |
| https://token.yyc3.vip | GitHub Pages 静态 | 200 |

## 目录结构

| 路径 | 内容 |
| --- | --- |
| `docs/architecture/` | ADR-001~014 + 架构全景 + 跨域契约 + 边界规则 + 三图（S16） |
| `docs/ops/` | Runbook 总纲 + 15 棵故障树 + 6 自愈剧本 + 复盘模板 + 交接清单 + 降级策略（S18） |
| `docs/observability/` | 指标字典（生产实测口径）+ 告警分级 + 仪表盘 + tracing 三锚点 + 日志规范 + SLO×5（S19） |
| `docs/release/` | C0-C4 变更分级 + 发布清单 + 回滚六型 + SemVer + CHANGELOG 模板 + 冻结策略（S20） |
| `docs/scripts/` | 41 入口编目 + 逐脚本手册 + 退出码字典 + 参数/环境变量矩阵（S17） |
| `docs/handover/` | ONBOARDING Day1/3/7 + FAQ 12 问 + 决策日志 19 条 + 术语表（含 8 Agent id/name） + Owner 矩阵 + 已知缺口 13 项（S21） |
| `docs/audit/` | 15 阶段审计链入口 INDEX + S15 终判报告 + DEF/backlog 登记 |
| `SSOT-INDEX.md` 等 4 件 | 单一事实源九域索引 · 文档健康度 92/A · **冻结声明** · 交接验收单（S22） |
| `docs/YYC3-双端联通实施日志.md` | R1-R11 逐批实施日志（含本会话全部 hotfix 判例） |
| `deploy/` | console-server 四件套 + LAN server.mjs + nginx.conf + launchd/systemd 留档（**运行中系统的源码**） |
| `scripts-ops/` | nas-console-ops.mjs（NAS 运维台）· chain-verify.mjs（三链校验）· bundle-stats.mjs |

## 运维速查（归档后仍然有效）

```bash
# NAS console 健康与自愈
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs status|verify|heal|boot'
# NAS 管理员密码
ssh -p 9557 yyc3-45 'cat ~/.yyc3-console-cred'
# ECS 管理员密码
ssh yyc3-33 'cat /root/.yyc3-console-cred'
# 公网健康
curl -s https://api.0379.world/console/auth/status
```

## 已知开口（13 项，全部条件触发）

见 `docs/handover/KNOWN-GAPS.md`。核心：L-06 jti 持久化（挂钩多管理员）· L-07 e2e 登录态工程化 · L-10 json-reporter 复测 · L-11 coverage 口径 · L-12b 图表种子（产品定义）· 后端 deploy key · NAS 自然重启终验。

## 若要复活开发

1. 原仓库 `YYC3-AI-API-Token-Console` 完整在位（190 测试文件 / 3230 用例 / 16 门禁全绿）；
2. 读 `docs/SSOT-INDEX.md`（九域入口）→ `docs/FREEZE.md`（解冻条件）→ `docs/handover/ONBOARDING.md`（Day 1/3/7）；
3. 应用源码 `src/` 与构建链在原仓库——本归档只含文档/脚本/部署件。
