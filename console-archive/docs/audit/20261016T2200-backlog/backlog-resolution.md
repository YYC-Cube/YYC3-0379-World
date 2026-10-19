# 全量遗留 / 缓办项解决方案（2026-10-17 汇总）

> 来源: DEF-01~06 登记 + S15 next_actions + S9 改进 P1-P3 + 各阶段 backtrace + 记忆 R8 时代遗留 + 工作区巡检。
> 优先级: **P0 生产正确性 → P1 低垂增强 → P2 体验/量化 → P3 长期治理 → P4 前端余项 / 外仓**。

## P0 — 生产正确性（应尽快）✅ 已完成 2026-10-17

### L-01 · ECS 公网形态 console-server 落后三个修复
- **现状**: ECS `/opt/yyc3/console/` 运行的是 jti/审计/settings 内容协商**之前**的版本——ECS 用户访问 `/console/settings` 会拿到 JSON 文档（与 NAS 同款 bug）；且无 jti 吊销/审计留痕。
- **根因**: S11/S6 的三处修复只部署了 NAS（`scp -P 9557`），ECS 侧留待「下次更新批」。
- **解法**（约 15 分钟，纯运维）:
  1. 本仓 `deploy/` 四 mjs 已是最新（d2fb7d0 后无需重建 dist-console——本次改动仅服务端件）;
  2. `scp deploy/{console-server,console-auth,console-metrics,console-ws-relay}.mjs yyc3-33:/opt/yyc3/console/`;
  3. ECS: `pm2 delete yyc3-console && cd /opt/yyc3/console && set -a; . ./console.env; set +a; pm2 start console-server.mjs --name yyc3-console && pm2 save`（判例: restart --update-env 无效）;
  4. 验证: 未登录 401 → login 200 → **导航 /console/settings 得 HTML 壳（`curl -H "Accept: text/html" | head -c 20` 见 `<!doctype`小写）** → logout 后旧 Cookie 401 → `tail /opt/yyc3/console/console-audit.log` 见事件。
- **风险**: 无——同款已 NAS 实测（S14/S11）。

## P1 — 低垂增强（各 ≤ 半天）✅ L-02/L-03 已完成

### L-02 · S9-P1 e2e Lighthouse 基线 — ✅ 98 分 (gzip 修复 80→98, 13.5.0 bidi 拦截降版 12.6.1)
- **现状**: dlx lighthouse 被 pnpm 供应链守卫拦（bidi 包接管疑警），perf 0.80 评分缺量化；S12 同根因 WARN。
- **解法**: `pnpm add -D lighthouse@<精确版>`（devDep 锁定绕开 dlx 信任链问题，装前查 `pnpm view lighthouse version` 并审计其依赖树无 bidi 或确认为官方）→ e2e 新增 spec: webServer 起后跑 `lighthouse --preset=desktop --only-categories=performance --output=json`，断言 ≥90 并归档分数; 工时 0.5d。

### L-03 · S9-P2 offline 多路由 — ✅ 4 路由断网全 200
- **现状**: SW 离线已有 e2e（fullchain 断网壳层）; 缺「离线下核心页面可浏览多路由」的场景面。
- **解法**: 扩 fullchain 离线用例: setOffline 后 `page.goto` 3-4 个代表路由（SW 导航 network-first→缓存壳兜底已实证）; IndexedDB 数据快照断言可选（hooks 降级契约已有单测）; 工时 0.5d。

### L-04 · NAS @reboot 重启终验（DEF-02）— ❌ SSH 通道全被 fnOS polkit 封 (第五路), 回落被动等自然断电
- **现状**: 链路三环静态验证完整（cron + resurrect dump 含进程 + ops.mjs boot 实测），唯差一次真实重启。
- **解法**: **零工作**——等 NAS 计划内维护/断电重启后跑 `ssh -p 9557 yyc3-45 '/mnt/volume2/.nvm/versions/node/v24.18.0/bin/node /Volume2/yyc3-console/ops.mjs boot'`，看 boot.log 有 resurrect 痕 + verify 七项绿即闭环。不建议为验证主动重启生产。

## P2 — 体验 / 量化增强（1d 内）

### L-05 · S9-P3 traceId 全局规范 — ✅ 2026-10-17 (AppError.traceId + 报告露出 + 注入通道, 3e57d00)
- **现状**: request_id 链路检索已有（R7, /audit 页）; 缺统一规范（error-handler 的 AppError 无 trace 关联）。
- **解法**: error-handler `captureError` 附 `traceId`（crypto.randomUUID 短前缀）; useGatewayAudit 的 request_id 检索与之对齐展示; 1d。

### L-06 · jti 吊销持久化（S6 可选增强的延伸）
- **现状**: 内存 Map，重启清空（TTL 12h 封顶，单管理员已论证可接受）。
- **解法**: 若需持久——console-server 启动时读/退出时写 `console-revoked.json`（与 console-settings.json 同模式）; 触发条件: 出现多管理员或会话敏感度提升; 0.5d，**当前不建议做**（复杂度>收益）。

### L-07 · e2e 登录态工程化（限流预算）
- **现状**: 限流 5/5min/IP，套件已满额（5 登录），fullchain 单测 90s 长测试承载过多。
- **解法**: `test.describe.serial` + 首测 `storageState` 落盘 + 依赖 describe `test.use({storageState})` 拆分导航/i18n 两个测试; 0.5d（有需要时做）。

## P3 — 长期治理 — L-08 **五片全数完成** (Dashboard+NetworkConfig+SecurityMonitor+AIAssistant+DatabaseManager/NodeDetailModal, 6080→5486 累计 -594)

### L-08 · 色值 tokens 存量迁移（DEF-01，6011 处）
- **解法**（首片模式已立，e6f9fb1）: 顺序 NetworkConfig(240)→SecurityMonitor(163)→AIAssistant(152)→DatabaseManager(149)→NodeDetailModal(110); 每批: 映射表替换（primary/foreground/destructive/chart-2/3/4 已实证同值）+ Recharts props 走 `var(--chart-N)` + 测试网回归 + `color:check` 基线人工下调（禁抬）; theme-presets.ts 永久豁免（数据源本体）; 每片约 1-2h，可穿插进行。

### L-09 · editor 语言包懒加载 — 触发条件未达 (perf 98·IDE 路由已重定向 dev-guide, editor 块非首屏) 维持不做
- **现状**: CodeMirror 全语言打包 692KB（异步块, 首屏不含）。
- **解法**: `@codemirror/lang-*` 按文件后缀动态 import; 省 ~300KB; 仅在 Lighthouse 量化（L-02）后若 IDE 路由加载敏感再做。

### L-10 · vitest json-reporter 偶发 exit 1（DEF-06）
- **解法**: 升 vitest 小版本时复测 `--reporter=json --outputFile` 与 coverage 并跑; 复现则提 issue; 5 分钟验证成本, 挂钩在下次依赖更新批。

### L-11 · coverage include 扩口径（DEF-04）
- **解法**: 与 deploy/*.mjs 补 .d.ts 联动（顺带消 6 处 @ts-expect-error）; 扩 `routes/i18n` 进 include 须重评四阈值基线; 专项 0.5d, 低优先。

## P4 — 前端余项 / 外仓 / 工作区

### L-12 · 前端余项 — gpuUtil ✅ 真实源 (节点 gpu 聚合, 89d91b4); 图表种子派生留判据 (radar 轴语义需产品定义)
- dashboard-stores 图表种子派生（种子数据→图表可复现）; gpuUtil 显存真实源（当前推导值）; 各 0.5d, 体验级。

### L-13 · 后端仓 — smoke 加固 ✅ (f8b3f27: compose --wait+轮询+fail 收口); deploy key/compose 重建终验另挂钩
- smoke-test.sh 加 `docker compose ps --wait healthy` 等待（SMOKE_FAIL 竞态残余防线, 0.5h）;
- GitHub deploy key（backend origin push 凭据, 运维决策）;
- compose 037dac3 已修 prometheus 声明——下次 `docker compose up -d prometheus` 按声明态重建即终验（注意先 `docker tag` 镜像或拉取, fnOS 无 Docker Hub 直连, daocloud 源判例）。

### L-14 · 工作区卫生
- `README.md` 脏改（会话前用户改动, 非审计链产物）——请用户自行 commit 或 discard;
- `e2e/.auth`/`test-results` 已 gitignore ✓; `smart-audit-report.json` 根目录为 smart:audit 每次再生（建议 gitignore 或入库皆可, 现状未跟踪不阻断）。

## 建议执行顺序

**本周**: L-01（P0, 15min）→ L-04（被动等）→ L-02（0.5d）→ L-03（0.5d）
**下周**: L-05（1d）→ L-08 第一片 NetworkConfig（1-2h）
**挂钩触发**: L-09 待 L-02 量化 / L-10 待依赖更新 / L-11 待 .d.ts 批 / L-06 待多管理员需求
