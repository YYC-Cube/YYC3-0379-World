# 参数矩阵 — 全脚本参数（S17 / 以源码为准）

> 范式：门禁类脚本**零参数**（配置内建于 config/基线文件），参数集中在部署件与环境变量。
> `--` 表示不接受该形态参数。

## A. 零参数门禁（pnpm 直跑，无 CLI 参数）

| 命令 | 参数 | 配置来源 |
| --- | --- | --- |
| pnpm typecheck / lint / lint:fp / astgrep / test:unit / test:coverage / test:e2e / size:check / color:check / dup:check / guardrail-probe / doctor / smart:audit | `--`（全部内建） | tsconfig.json / eslint*.config.js / sgconfig.yml / vitest.config.ts / *.json 基线 |

例外形态（工具原生参数，非脚本自定义）：
- `pnpm exec vitest run <文件...>`：按文件过滤
- `pnpm exec eslint <文件...> --max-warnings=0`：范围收窄
- `pnpm exec playwright test <spec> --reporter=json > out`：单 spec / 报告
- `pnpm exec tsc --noEmit --pretty false [--listFiles]`：诊断形态

## B. 基线脚本参数（node 直跑）

| 脚本 | 参数 | 默认 | 边界 |
| --- | --- | --- | --- |
| check-size.mjs | 无（git ls-files 自扫） | — | 基线表内嵌脚本；新超标文件告警锁定 |
| check-color-budget.mjs | 无 | — | 基线 scripts/color-budget.json；缺文件→首建 |
| check-dup-budget.mjs | 无 | min-tokens 70 · 范围 src/app · ignore __tests__ | 基线 scripts/dup-budget.json；缺文件→首建 |
| knip-check.mjs | 无（读 knip.config.ts BASELINE_COUNTS） | — | 裸 knip 的 exit 1 非门禁 |
| nas-console-ops.mjs | `<子命令> [n]`：status / verify / heal / boot / logs [n=30] / restart / stop / 无参=TTY 菜单 | CONSOLE_BASE=http://127.0.0.1:3210 | 非 TTY 无参 exit 2；未知命令 exit 2 |
| bundle-stats.mjs | 无（dist/assets 固定） | — | 输出 stdout JSON |
| chain-verify.mjs | 无（dist/manifest.json 固定） | — | 需先 build |
| inject-precache.mjs | `[distDir]`（可选, 位置参数） | `dist` | `build:console` 传 `dist-console` |
| lint-warn-codemod.mjs | 交互式 | — | 治理批专用 |

## C. 部署件环境变量（deploy/*.mjs）

| 变量 | 消费方 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| PORT | console-server | 否 | 3100 | e2e 用 3199 |
| HOST | console-server | 否 | 127.0.0.1 | NAS 用 0.0.0.0 |
| DIST_DIR | console-server | 否 | `../dist`（相对脚本） | **ECS 布局须 =dist** |
| CONSOLE_AUTH_SECRET | console-server | 与 PASSWORD 同时 | 空=鉴权关闭 | openssl rand -hex 32 |
| CONSOLE_ADMIN_PASSWORD | 同上 | 同上 | 空 | 凭据留档 *.cred 600 |
| GW_ORIGIN | console-server | 否 | http://127.0.0.1:8800 | NAS=3118 本机/ECS=3118 |
| GW_ADMIN_KEY | console-server | 鉴权链需要 | 空→gw 503 | 从网关容器 env 取, 不落终端 |
| OLLAMA_HOST / OLLAMA_PORT | server.mjs | 否 | 本机 | LAN 代理目标 |
| ALLOW_ORIGIN / ALLOW_ORIGIN_CIDR | server.mjs | 否 | 仅同源 | 精确白名单 / 网段 |
| YYC3_TEST_INTEGRATION | vitest | integration 档必填 | 未设=跳过 | 零外部依赖红线出口 |
| E2E_ADMIN_PASSWORD | playwright | 否 | 分段拼装回退值 | 与 webServer.env 一致 |

## D. 测试触发的环境变量（判例）

| 变量 | 用途 | 出处 |
| --- | --- | --- |
| `@vitest-environment-options {"url": ...}` | jsdom location 不可伪造的沙箱分支 | service-test-panels.sandbox-env |
| `CHROME_PATH` / `--chrome-path` | lighthouse 用 playwright 的 Chrome for Testing | e2e/lighthouse.spec.ts |
| CONSOLE_BASE（ops.mjs） | 运维台目标（白名单 127.0.0.1/::1/192.168.3.45） | scripts/nas-console-ops.mjs |
