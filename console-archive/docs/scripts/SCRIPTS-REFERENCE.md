# 逐脚本参考手册 — YYC³ Token Console（S17）

> 以源码为准（2026-10-17 快照）。失败自愈列的命令均可直接复制执行。
> 通用判例先行：**管道吞退出码**（`cmd | tail` 的 `$?` 是 tail 的）；**裸 `pnpm doctor`/`pnpm knip` 会被 pnpm 内建抢占**——一律 `pnpm run doctor` / `node scripts/knip-check.mjs`。

---

## guardrail-probe.mjs

- 路径：`scripts/guardrail-probe.mjs` · 触发：手动 / CI（元门禁）· 依赖：ast-grep/eslint/gitleaks/knip/vitest（同源门禁）
- 用途：向隔离沙箱植入 20 个已知违规样本，断言各门禁真实拦截（防假绿）。
- 幂等：是（每探针 rm-on-finally；size 探针受控变异+恢复原文）。
- 副作用：临时目录 `src/app/hooks/__guardrail_probe__`、`/tmp/__guardrail_gl_probe__`（用后即删）；size 探针瞬时改写基线文件（finally 恢复）。
- 退出码：0=20/20 拦截；1=任一未拦截（转储门禁输出）。
- 失败自愈：探针报「未拦截」→ 看输出段定位规则 → 大概率是规则文件/工具版本脱节（2026-09-24 判例）或样本形态过时（gitleaks 高熵 ≥36 位判例）。
- 关联：ADR-004 · S10。

---

## doctor.mjs

- 路径：`scripts/doctor.mjs` · 触发：手动 / smart:audit 内含 · 依赖：node + 本仓文件 + ast-grep 二进制
- 用途：环境自诊断 12 项（版本/lockfile/供应链策略/漂移/关键文件/CNAME/ast-grep/体量/knip/env.example）。
- 幂等：是。副作用：只读 + stdout。
- 退出码：0=12/12；1=任一 error。
- 失败自愈：版本不符→`.nvmrc`/engines；lockfile 不一致→`pnpm install --frozen-lockfile`；**裸 `pnpm doctor` 是 pnpm 内建命令**（AGENTS 红线级判例）。

---

## smart-audit.mjs

- 路径：`scripts/smart-audit.mjs` · 触发：手动 · 依赖：typecheck/lint/vitest/build/astgrep/size/knip/guardrail/doctor（九门禁编排）
- 用途：九维复合审计一次跑齐（~104s@3230 用例），产出 `smart-audit-report.json`（机器可读）。
- 幂等：是。副作用：写 `smart-audit-report.json`（根目录）+ 各门禁自身的常规输出。
- 退出码：0=9/9；1=任一维度失败。
- 失败自愈：单维失败→按维度跑对应单门禁定位；json reporter+coverage 组合偶发 exit 1（DEF-06，零失败痕迹→以 CI 命令复跑为准）。
- 关联：ADR-004 · S9/S10/S12 复合证据。

---

## check-size.mjs

- 路径：`scripts/check-size.mjs` · 触发：CI + 手动 · 依赖：git ls-files + wc -l
- 用途：文件体量棘轮——基线表文件只减不增 + 新超标文件告警锁定（BASELINE 内嵌）。
- 幂等：是。副作用：只读。
- 退出码：0；1=基线文件增长（::error）。
- 失败自愈：增长行→新逻辑放新 sibling 文件（SystemSettings→7 文件判例）或同行内联；ServiceConnectionTest 406/406 紧平衡判例。
- 关联：ADR-012 · S8。

---

## check-color-budget.mjs

- 路径：`scripts/check-color-budget.mjs` · 触发：手动/CI · 依赖：node:fs 只读扫描
- 用途：硬编码色值基线棘轮（6080→5486 五片迁移后冻结；口径=src/app/{components,hooks} 排除 __tests__，正则 `#hex|rgba?(`）。
- 幂等：是（首跑自动建 scripts/color-budget.json）。副作用：首建时写基线文件。
- 退出码：0；1=count > baseline（输出 Top files 定位）。
- 失败自愈：新增色→改用 Design Tokens（theme.css）；迁移批落地→人工下调 JSON 基线（附原因+日期，禁上调）。
- 关联：ADR-012 · S3 治理 D。

---

## check-dup-budget.mjs

- 路径：`scripts/check-dup-budget.mjs` · 触发：手动/CI · 依赖：jscpd 5.4.1（devDep, 经 node_modules/.bin 调用——knip 白名单判例）
- 用途：跨域重复基线棘轮（**生产码口径排除 __tests__**；15 克隆/237 行 @ min-tokens 70）。
- 幂等：是（报告写 /tmp/jscpd-report.json）。副作用：/tmp 写报告。
- 退出码：0；1=超基线（clones 与 dupLines 双指标）。
- 失败自愈：超线→抽象进 shared/contracts 或改写；测试域样板重复属豁免类别（口径已排除）；负例探针判例：调低基线 JSON → FAIL exit 1 自证。
- 关联：ADR-012 · S8。

---

## knip-check.mjs

- 路径：`scripts/knip-check.mjs` · 触发：CI + 手动 · 依赖：knip + knip.config.ts
- 用途：死代码基线比对（BASELINE_COUNTS 各类别只减不增；ignoreDependencies 白名单留证）。
- 幂等：是。副作用：只读（内部跑 knip）。
- 退出码：0=全类别≤基线；1=超基线（::error 逐类别）。
- 失败自愈：新 unused export→确认无引用后删；新 devDep 未识别→查白名单机制（jscpd/@ast-grep/cli 工具链二进制判例）；**裸 `pnpm knip` exit 1 是原始明细非门禁失败**。
- 关联：ADR-012 · S8。

---

## guardrail 关联：inject-precache.mjs

- 路径：`scripts/inject-precache.mjs` · 触发：build/build:console 后置 · 依赖：dist 产物
- 用途：扫描 dist 资产生成 SW 预缓存清单注入 sw.js（90 项，预算 6MB 实测 2.92MB）。
- 幂等：是。副作用：写 `dist/sw.js`。
- 退出码：0；1=dist 缺失/清单生成失败。
- 失败自愈：先 `pnpm build` 再单独跑；参数 `[distDir]`（build:console 传 dist-console）。
- 关联：ADR-007 · S12。

---

## nas-console-ops.mjs

- 路径：`scripts/nas-console-ops.mjs`（NAS 副本 `/Volume2/yyc3-console/ops.mjs`）· 触发：手动 · 依赖：node 原生 + pm2/curl/ SSH 环境
- 用途：NAS console 运维台。
- 参数：`status | verify | heal | boot | logs [n] | restart | stop`，无参=TYY 菜单。
- 幂等：status/verify/boot 是；heal 幂等（resurrect→已起则无操作）；restart/stop 有副作用（进程操作）。
- 副作用：heal 可能 pm2 start；boot 读 dump/boot.log；stop 删进程。
- 退出码：0=成功/绿；1=verify 不完整/操作失败/链路缺环；2=未知命令。
- 失败自愈：verify 失败项→`heal`；boot 报 dump 缺进程→先 `pm2 save`；非 NAS 机器 3~7 项跳过=无凭据文件语义。
- 安全：主机白名单（127.0.0.1/::1/192.168.3.45，非白名单 exit 2）；密码只读 cred 文件。
- 关联：ADR-006 · S14 · R10。

---

## chain-verify.mjs

- 路径：`scripts/chain-verify.mjs` · 触发：手动/审计 · 依赖：dist/manifest.json + public/yyc3-icons
- 用途：PWA（manifest 6 字段+icons 对齐）与图标（5 平台）三链一致性 dist 实证，输出 stdout JSON。
- 幂等：是。副作用：只读。
- 退出码：恒 0（结果看 JSON 的 ok 字段）——S13 判例。
- 失败自愈：missingIcons→补文件；missingFields→补 manifest 字段。
- 关联：ADR-009 · S13。

---

## bundle-stats.mjs

- 路径：`scripts/bundle-stats.mjs` · 触发：手动 · 依赖：dist/assets + node:zlib
- 用途：构建产物体积统计（raw+gzip，90 chunks/total/largest/top5 → stdout JSON）。
- 幂等：是。副作用：只读。
- 退出码：0（dist 缺失时抛异常非零）。
- 失败自愈：先 `pnpm build`。
- 关联：S12（source-map-explorer 的无 map 替代）。

---

## deploy 四件套（console-server / console-auth / console-metrics / console-ws-relay.mjs）

- 触发：pm2 / node 直跑（console-server 为唯一入口，其余被 import）
- 用途：公网形态服务（gzip 静态 + HMAC/jti/限流/审计 + gw 代理 + WS 中继 + Ollama 反代）。
- 幂等：服务常驻非幂等操作；SIGTERM 优雅退出。
- 副作用：监听端口；写 console-audit.log；读 console-settings.json。
- 退出码：0=正常退出；1=启动失败（EADDRINUSE 判例：先查 `lsof -i :PORT`）。
- 失败自愈：EADDRINUSE→kill 残留；settings 导航拿到 JSON→确认内容协商代码在位（S11 修复）；401→查 env 注入（pm2 delete+start 判例，restart --update-env 无效）。
- 关联：ADR-005/006 · S11/S14。

---

## server.mjs（LAN 形态）

- 用途：LAN 静态 + Ollama 反代（无鉴权；CORS 白名单 env 可配）。
- 判例：跨回合残留占 3118（两遇）——起前 `lsof -i :3118`，用后 kill；剥 origin/referer 头（S6）。
- 关联：ADR-005 · S14。
