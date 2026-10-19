# 退出码字典 — 跨脚本统一（S17）

> 统一语义八档 + 特例登记。**门禁类脚本一律 0=过 / 1=拦**，与 CI 兼容（非零即红）。

## 统一语义

| 码 | 语义 | 使用方 |
| --- | --- | --- |
| 0 | 成功 / 门禁全过 | 全部 |
| 1 | 通用失败 / **门禁命中**（本仓门禁类统一用 1, 不细分） | 门禁全家 + vitest/eslint/tsc/build |
| 2 | 参数 / 用法错误 | nas-console-ops（未知命令）；esbuild/eslint fatal 也产 2 |
| 130 | SIGINT 中断（shell 约定） | 长驻服务 |

## 逐脚本实测（grep process.exit + 运行实录）

| 脚本 | 0 | 1 | 2 | 备注 |
| --- | --- | --- | --- | --- |
| check-size.mjs | 过 | 基线文件增长（::error 段存在即 1） | — | 非基线新超标只 ::warning 不阻断（首轮锁定） |
| check-color-budget.mjs | 过/首建 | count > baseline | — | 首跑自动建基线 exit 0 |
| check-dup-budget.mjs | 过/首建 | clones 或 dupLines 超基线 | — | 同上；负例探针已验证 |
| knip-check.mjs | 过 | 任一类别超基线 | — | 裸 `pnpm knip` exit 1 = 基线内 findings（非门禁, 勿混） |
| doctor.mjs | 12/12 | 任一项 error | — | warning 不阻断 |
| guardrail-probe.mjs | 20/20 拦截 | 任一探针未拦截（门禁失效） | — | 失败时转储门禁输出 |
| inject-precache.mjs | 注入成功 | dist 缺失/清单失败 | — | build 后置钩子 |
| nav-token-bench.mjs | 过 | 基准失败 | — | |
| nas-console-ops.mjs | 子命令成功/体检绿 | verify 不完整/操作失败 | 未知命令/非交互无参 | boot 返回 1 = 链路缺环 |
| tsc | 0 错误 | 类型错误 | 配置/文件解析 fatal | S11 判例: fatal 与错误码同为 2 |
| eslint | 0/0 | error 或超 max-warnings | fatal（如 parserOptions.project 缺文件） | useBigModelSDK 判例 |
| vitest | 全绿 | 用例失败/超时 | 收集错误（transform fail） | coverage 阈值内建于 exit |
| playwright | 全过 | 用例失败/浏览器缺失 | — | 浏览器缺失先 `playwright install chromium` |
| gitleaks | 无命中 | 命中 | 用法错误（如 dlx 无 bin） | 一律带 `--config .gitleaks.toml` |
| build (vite) | 成功 | 构建错误/注入失败 | — | inject-precache 失败连带 exit 1 |
| smart-audit.mjs | 9/9 | 任一维度失败 | — | 报告写 smart-audit-report.json |

## 已知特例（如实登记，不强行统一）

1. **裸 `pnpm knip`** vs **`node scripts/knip-check.mjs`**：前者是 knip 原始输出（有 findings 即 exit 1），后者是基线比对门禁。CI/本地一律用后者。
2. **`pnpm dlx gitleaks`**：ERR_PNPM_DLX_NO_BIN（gitleaks 非 npm 包）——用本地二进制 `gitleaks` 命令。
3. **管道吞退出码**：`cmd | tail` 的 `$?` 是 tail 的——测退出码必须单独跑或用 `PIPESTATUS`。
4. **vitest --reporter=json + coverage 并跑**偶发 exit 1 零失败痕迹（DEF-06）——以 CI 契约命令复跑为准。
