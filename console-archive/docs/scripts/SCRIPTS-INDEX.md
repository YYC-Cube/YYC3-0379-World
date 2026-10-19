# 脚本总索引 — YYC³ Token Console（S17 / 2026-10-17）

> 41 个可执行入口（28 个 package.json scripts + 13 个独立脚本）全部编目。
> 逐脚本详情: [SCRIPTS-REFERENCE.md](./SCRIPTS-REFERENCE.md) · 退出码字典: [EXIT-CODES.md](./EXIT-CODES.md) · 参数/环境变量: [PARAM-MATRIX.md](./PARAM-MATRIX.md) + [ENV-MATRIX.md](./ENV-MATRIX.md)

## 一、质量门禁类（CI 六阶段 + 本地全量）

| 命令 | 脚本 | 用途 | 退出码 |
| --- | --- | --- | --- |
| `pnpm typecheck` | `tsc --noEmit` | TS strict 双旗标类型检查 | 0/1 |
| `pnpm lint` | `eslint . --max-warnings 500` | 规范 + boundaries 分层契约 | 0/1/2 |
| `pnpm lint:fp` | `eslint -c eslint.fp.config.js src` | 悬空 Promise 专项（type-aware） | 0/1/2 |
| `pnpm astgrep` | ast-grep scan (sgconfig.yml) | 7 反模式规则 × ts/tsx | 0/1 |
| `pnpm test:unit` | vitest (unit-dom+unit-node) | 分级单测 3230+ | 0/1 |
| `pnpm test:coverage` | vitest --coverage | 单测 + 四阈值覆盖率 | 0/1 |
| `pnpm guardrail-probe` | scripts/guardrail-probe.mjs | 元门禁 20 探针 | 0/1 |
| `pnpm size:check` | scripts/check-size.mjs | 文件/函数体量棘轮 | 0/1 |
| `pnpm color:check` | scripts/check-color-budget.mjs | 色值基线棘轮 | 0/1 |
| `pnpm dup:check` | scripts/check-dup-budget.mjs | 重复基线棘轮（生产码） | 0/1 |
| `node scripts/knip-check.mjs` | knip + 基线比对 | 死代码棘轮（裸 `pnpm knip` 是原始明细非门禁） | 0/1 |
| `pnpm test:e2e` | playwright | e2e 13 用例（含 Lighthouse ≥90） | 0/1 |

## 二、环境 / 诊断 / 元审计类

| 命令 | 脚本 | 用途 | 退出码 |
| --- | --- | --- | --- |
| `pnpm run doctor` | scripts/doctor.mjs | 环境自诊断 12 项（**裸 `pnpm doctor` 会跑 pnpm 内建命令**） | 0/1 |
| `pnpm smart:audit` | scripts/smart-audit.mjs | 九维智能审计复合跑（生成 smart-audit-report.json） | 0/1 |
| `pnpm guardrail-probe` | 同上 | 兼元门禁 | 0/1 |

## 三、构建 / 预览 / 部署类

| 命令 | 脚本 | 用途 | 退出码 |
| --- | --- | --- | --- |
| `pnpm dev` / `dev:host` | vite :3030 | 开发服务器（SW 不注册） | — |
| `pnpm build` | vite build + inject-precache | 生产构建 dist/（SW 预缓存注入） | 0/1 |
| `pnpm build:console` | VITE_BASE=/console/ 同上 | console 同源产物 dist-console/ | 0/1 |
| `pnpm serve:local` | deploy/server.mjs | LAN 形态 :3118（无鉴权 + Ollama 代理） | 0/1 |
| `pnpm serve:console` | deploy/console-server.mjs | 公网形态（需 env 否则鉴权 fail-closed） | 0/1 |
| `pnpm deploy` | build + serve:local 组合 | 一键本地部署 | 同上 |
| `pnpm preview` | vite preview :3030 | 构建产物预览 | — |

## 四、测试辅助类

| 命令 | 用途 |
| --- | --- |
| `pnpm test` / `test:watch` | vitest 全项目 / watch |
| `pnpm test:integration` | integration 档（需 `YYC3_TEST_INTEGRATION=1`） |
| `pnpm test:ci` | junit 报告形态 |
| `pnpm knip` | knip 原始明细（exit 1 = 有基线内 findings, **非门禁**） |
| `pnpm lint:fix` | eslint --fix |
| `pnpm nav:bench` | 导航 token 基准（nav-token-bench.mjs） |

## 五、独立脚本（无 package.json 入口，node 直跑）

| 脚本 | 用途 | 触发 |
| --- | --- | --- |
| `scripts/nas-console-ops.mjs` | NAS console 运维台（status/verify/heal/boot/logs/restart/stop + TTY 菜单） | 手动（NAS/本机） |
| `scripts/bundle-stats.mjs` | dist 体积统计（raw+gzip → stdout JSON） | 手动 |
| `scripts/chain-verify.mjs` | PWA/i18n/图标三链 dist 实证 | 手动/审计 |
| `scripts/lint-warn-codemod.mjs` | lint warning 批量修复 codemod | 手动（治理批） |
| `scripts/find-types-react19.cjs` | React19 类型迁移辅助 | 手动（历史） |
| `scripts/download-icons.sh` | 图标资产下载 | 手动（ редко） |
| `scripts/check_mermaid.py` | Mermaid 代码块开闭校验 | pre-commit |
| `deploy/setup-nginx.sh` / `start.sh` / `com.yyc3.dashboard.plist` | 部署侧辅助（nginx 配置/启动/launchd） | 服务器侧 |
| `deploy/console-auth·metrics·ws-relay.mjs` | console-server 的三件依赖模块（被 import，非入口） | — |

## 六、数据文件（非脚本）

`scripts/color-budget.json` · `scripts/dup-budget.json`（两个棘轮基线）· `smart-audit-report.json`（再生产物）。
