# 自愈剧本 — 按场景（SELF-HEAL）

> 与 FAULT-TREE 的区别：故障树做**定位**，本文是**可直接粘贴执行的完整剧本**（含前置/执行/回退）。
> 自愈脚本入口：`node scripts/nas-console-ops.mjs`（NAS）· 全门禁一键（本地）。

---

## 剧本 H1 · NAS console 三分钟自愈（服务不可达首选）

**前置**：能 SSH NAS；已排除端口被第三方占用（`ops.mjs status` 会显示）。
```bash
# 1. 一站式体检
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs status'
# 2a. 进程在但拒连 → restart
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs restart'
# 2b. 进程消失/errored → heal（resurrect → 失败则解析 env 免 shell 拉起）
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs heal'
# 3. 验证
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs verify'
```
**回退**：heal 全新拉起失败 → `ops.mjs logs 50` 看启动栈 → 常见为 env 缺失（核对 console.env 六键）/ 端口占用（换端口需同步前端 gatewayBase）。

---

## 剧本 H2 · ECS console 重部署（发版/修复同步）

```bash
# 1. 推送四件套
cd /Users/yanyu/YYC-Cube/YYC3-AI-API-Token-Console
scp deploy/console-server.mjs deploy/console-auth.mjs deploy/console-metrics.mjs deploy/console-ws-relay.mjs yyc3-33:/opt/yyc3/console/
# 2. 重启（判例: 必须 delete + env 注入 + start, restart --update-env 无效）
ssh yyc3-33 'cd /opt/yyc3/console && pm2 delete yyc3-console >/dev/null 2>&1; set -a; . ./console.env; set +a; pm2 start console-server.mjs --name yyc3-console >/dev/null 2>&1; pm2 save >/dev/null 2>&1'
# 3. 八点验证（HMAC/内容协商/jti/审计）
ssh yyc3-33 'P=$(cat /root/.yyc3-console-cred); ... '   # 见 backlog-resolution L-01 步骤 4
```
**回退**：`/opt/yyc3/console/backup-*/` 旧件回拷 + 同样重启流程。

---

## 剧本 H3 · 本地开发环境自愈（门禁突然红）

```bash
pnpm run doctor                      # 12 项定位环境层
pnpm install --frozen-lockfile       # 依赖漂移
pnpm exec playwright install chromium # e2e 浏览器缓存缺失（一日两遇判例, EBUSY 重试）
pnpm typecheck && pnpm lint && pnpm lint:fp
pnpm test:unit
```
**判例速查**：裸 `pnpm doctor` 跑 pnpm 内建；同名 .ts/.tsx 测试只留一个；agent 大批结束后歇一拍再跑 coverage（28 超时竞争判例）。

---

## 剧本 H4 · NAS 断电重启后（@reboot 终验/恢复）

```bash
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs boot'    # 钩子/dump/boot.log 三环
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs verify'  # 七项
# 网关容器（compose 自带 restart: unless-stopped, 预期自起）
ssh -p 9557 yyc3-45 'docker ps --format "{{.Names}} {{.Status}}" | grep 0379'
# prometheus 若未随起（run 直管形态）
ssh -p 9557 yyc3-45 'docker start yyc3-prometheus'
```
**判例**：`install` 是 fnOS 应用商店助手；端口 3100/3113 被占是既定事实（3210 为定值）。

---

## 剧本 H5 · gitleaks 误报处置（非紧急但需留痕）

```bash
gitleaks detect --no-git --source . --config .gitleaks.toml --no-banner --redact -v
# 命中 → 三选一:
# a) 公开测试向量/标识符 → .gitleaks.toml 豁免条目（原因+复核日期+Fingerprint, 路径用位置无关后缀）
# b) 真实凭据 → 立即吊销轮换（先于一切 git 操作）→ 清理 + 复盘
# c) 构建产物 → 确认 gitignore 生效 + 源码不动（L2 stop-hook 判例）
```

---

## 剧本 H6 · 网关容器重建（代码更新后）

```bash
# NAS 上（bundle 同步代码后）
ssh -p 9557 yyc3-45 'cd /Volume2/yyc3-33 && docker compose up -d --build gateway'
# 等待健康（L-13 加固后的脚本自动做; 手工时用）
ssh -p 9557 yyc3-45 'docker compose ps --wait --timeout 100; curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8000/healthz'
# prometheus 若连带重建失败（网络调和判例）→ 只重建目标服务 --no-deps, 缺镜像先 tag
```

---

## 通用原则

1. **先证据后动作**：每步留命令输出（凌晨 3 点可交接）。
2. **不净关机不做**：NAS sysrq/断电式重启禁止。
3. **密钥零回显**：处置命令不得把 secret 打进日志/终端。
4. **修完必归档**：INCIDENT-LOG 模板 + 审计目录。
