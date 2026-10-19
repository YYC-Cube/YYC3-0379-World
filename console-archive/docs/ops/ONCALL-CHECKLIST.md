# 值守交接清单 — ONCALL CHECKLIST

> 每次值守交接 5 分钟跑一遍；全绿打勾；异常项按 FAULT-TREE 对应树处置并写交接备注。

## A. 三端服务（由外向内）

- [ ] 公网入口：`curl -s --max-time 8 https://api.0379.world/console/auth/status` → `{"enabled":true,...}`
- [ ] ECS 进程：`ssh yyc3-33 'pm2 ls'` → yyc3-console online（非 errored/restarting）
- [ ] NAS 进程：`ssh -p 9557 yyc3-45 'node /Volume2/yyc3-console/ops.mjs status'` → 全绿
- [ ] NAS 七项：`ops.mjs verify` → 7/7 PASS
- [ ] LAN：`curl -o /dev/null -w %{http_code} http://<LAN>:3118/` → 200
- [ ] 网关：`ssh -p 9557 yyc3-45 'curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8000/healthz'` → 200
- [ ] 网关容器：`docker ps` → gateway/postgres/redis 均 Up (healthy)

## B. 可观测栈

- [ ] Prometheus：`curl http://192.168.3.45:9090/-/ready` → 200
- [ ] Grafana：`curl http://192.168.3.45:3000/api/health` → 200
- [ ] Loki（Tailscale 面）：`curl http://100.65.172.88:3100/ready` → 200
- [ ] @reboot 链路：`ops.mjs boot` → 钩子已装 + dump 含进程

## C. 审计与安全

- [ ] ECS 审计流：`tail /opt/yyc3/console/console-audit.log` → 有近期事件（无异常爆发）
- [ ] 登录失败激增检查：audit 中 login_fail 密度（限流 5/5min 生效即无刷爆）
- [ ] 密钥文件权限：console.env / *.cred 均 600

## D. 仓库 / 门禁健康（接手开发者加跑）

- [ ] `pnpm run doctor` → 12/12
- [ ] `git status` → 无意外脏改（README 等个人改动除外）
- [ ] `pnpm guardrail-probe` → 20/20
- [ ] `pnpm test:unit` → 全绿

## E. 交接备注模板

```
交接时间：
值守人 → 接手人：
期间事故：无 / INC-xxx（链接）
未决事项：
特别注意：
```

---

## 快速故障索引（详见 FAULT-TREE）

| 症状关键词 | 树 |
| --- | --- |
| 拒连 / EADDRINUSE / errored | T1 |
| 401 / 登录失败 / 全员掉线 | T2 |
| Ollama / 502 / tags 超时 | T3 |
| Prometheus / Loki / Redis 不可达 | T4 |
| 断网白屏 / SW | T5 |
| coverage ERROR | T6 |
| guardrail 未拦截 | T7 |
| 体积 / precache 超 | T8 |
| 白屏 / ErrorBoundary | T9 |
| 裸键名 / i18n FAIL | T10 |
| favicon 404 / 图标 | T11 |
| gitleaks 命中 | T12（紧急） |
| 磁盘 / 内存 | T13 |
| 测试超时 / 卡死 | T14 |
| 补全缺失 | T15 |
