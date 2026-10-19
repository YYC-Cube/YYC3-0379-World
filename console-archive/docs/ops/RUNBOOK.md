# 运维手册总纲 Runbook — YYC³ Token Console

> 版本: 2026-10-17（S18）· 适用: NAS console (3210) / ECS console (3100) / LAN (3118) / Pages 静态
> 铁律: **禁止「遇到问题重启」作为唯一处置**——先按故障树定位（[FAULT-TREE.md](./FAULT-TREE.md)），处置后必须验证恢复并复盘归档。

## 1. 拓扑与健康探针

```
浏览器 ──► https://api.0379.world ──► ECS Traefik ──► console-server :3100 (PM2 yyc3-console)
浏览器 ──► http://192.168.3.45:3210 ──────────────► NAS console-server :3210 (PM2 yyc3-console-nas)
浏览器 ──► http://<LAN>:3118 ─────────────────────► server.mjs (LAN, 无鉴权 + Ollama 代理)
                                                        │ gw proxy / WS relay
                                                        ▼
                                            NAS 网关容器 :8000 (FastAPI)
                                            ├ PG :5432 (127.0.0.1)
                                            ├ Redis :6379 (127.0.0.1)
                                            ├ Prometheus :9090 / Grafana :3000 / Loki :3100(Tailscale)
                                            └ Ollama :11434 (LAN 代理目标)
```

**分层健康探针（由外向内）**：
```bash
# L0 公网入口
curl -s --max-time 8 https://api.0379.world/console/auth/status
# L1 ECS console
ssh yyc3-33 'curl -s http://127.0.0.1:3100/console/auth/status; pm2 ls | grep yyc3-console'
# L2 NAS console（运维台一站式）
ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs status'
# L3 NAS 网关
ssh -p 9557 yyc3-45 'curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8000/healthz'
```
期望：L0/L1/L2 返回 `{"enabled":true,...}`；L3 返回 200。

## 2. 一分钟速诊（任何报警先跑这个）

```bash
node scripts/nas-console-ops.mjs status     # 本机/SSH 到 NAS：进程/端口/服务/钩子
ssh yyc3-33 'pm2 ls && curl -s http://127.0.0.1:3100/console/auth/status'
pnpm run doctor                              # 本地开发环境 12 项
```

## 3. 升级路径 Escalation

| 层级 | 角色 | 触发条件 | 联系 |
| --- | --- | --- | --- |
| L1 值守 | 任何工程师 | 单点症状、故障树可定位、有现成剧本 | 本文档自愈 |
| L2 域 Owner | 对应域维护者 | 跨域影响 / 故障树走完未解 / 需要产品语义决策（如 radar 轴） | 仓库 CODEOWNERS / 提 issue 带 `mod:*` 标签 |
| L3 架构师 | 首席架构师 | 架构级缺陷（门禁空心/安全事件/数据正确性） | 安全报告走 `<sec@yanyucloud.com>`（勿公开披露） |

**必升级红线**：secret 泄漏（立即吊销+轮换，先处置后复盘）；生产数据损坏；鉴权被绕过。

## 4. 事故处置通用流程（PDCA）

1. **定级**：按 [FAULT-TREE.md](./FAULT-TREE.md) 匹配症状 → 影响面（阻塞生产/降级/单域）。
2. **处置**：按对应剧本执行；每步记录命令与输出（凌晨 3 点也能交接）。
3. **验证**：剧本「验证恢复」节 + 相关门禁重跑。
4. **复盘**：24h 内按 [INCIDENT-LOG.md](./INCIDENT-LOG.md) 模板归档 `docs/ops/incidents/<timestamp>.md`。
5. **固化**：若根因是新型，补入 FAULT-TREE + SELF-HEAL 剧本（本文档是活的）。

## 5. 事故档案

已有归档判例：R10「打不开」事件（`docs/audit/20261016T0832-nas-console-incident/`，重启→守护消亡→@reboot 自愈落地）；模板见 [INCIDENT-LOG.md](./INCIDENT-LOG.md)。
