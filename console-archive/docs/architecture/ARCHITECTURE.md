# 架构全景 — YYC³ Token Console

> 定位: 本地闭环多端推理矩阵数据看盘系统（纯前端 SPA + 零依赖 Node 部署双形态）
> 详细决策: [ADR-INDEX.md](./ADR-INDEX.md) · 边界: [BOUNDARIES.md](./BOUNDARIES.md) · 契约: [CONTRACTS.md](./CONTRACTS.md)

## 1. 分层架构（依赖方向，eslint boundaries 强制）

```
┌────────────────────────────────────────────────────────────┐
│ src/main.tsx → App.tsx → routes.ts（路由表唯一事实源）        │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│ components/（116 组件, 六域页面 + 域目录 + ui/shadcn 禁改区） │
│   域目录: ai-family · ide · service-test · design-system …  │
└──────┬───────────────────────────┬─────────────────────────┘
       ▼                           ▼
┌──────────────┐          ┌──────────────┐
│ hooks/ (27)  │          │ stores/      │   ← hooks 禁引 stores/components
└──────┬───────┘          └──────┬───────┘
       ▼                         ▼
┌──────────────────────────────────────────┐
│ lib/ (http·yyc3-storage·error-handler·    │   ← 仅 lib/types
│  gateway-skills·terminal-completions …)   │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│ types/ (core·network-sync·ops-monitor·    │   ← 不引任何层
│  ai-provider·ui-shared·design-system)     │
└──────────────────────────────────────────┘
```

规则: 单向依赖 · `@/*` 别名 · 域目录互引允许但**跨域复用逻辑必须下沉**（ADR-002）。

## 2. 部署双形态（ADR-005 / ADR-006）

```
浏览器
 ├─ https://api.0379.world ──► ECS Traefik ──► console-server :3100
 │                                              (PM2 yyc3-console, gzip, HMAC, jti, audit JSONL)
 ├─ http://192.168.3.45:3210 ────────────────► NAS console-server :3210
 │                                              (PM2 yyc3-console-nas, @reboot resurrect)
 └─ http://<LAN>:3118 ───────────────────────► server.mjs (LAN 形态, 无鉴权)
                                               │
                              ┌────────────────┘  gw proxy / WS relay / Ollama proxy
                              ▼
                   NAS 网关容器 :8000 (FastAPI, 98 端点)
                              │
                 ┌────────────┼────────────┬──────────────┐
             PG :5432     Redis :6379   Prometheus :9090  Grafana :3000
```

四份服务件（console-server/auth/metrics/ws-relay.mjs）scp 即部署，零 npm 运行时依赖。

## 3. 核心数据流（WS 实时 + REST 兜底）

```
网关 /ws/monitor ──{event:"metrics"}──► console-server WS 中继 (RFC 6455 手写)
     │                                        │ Cookie 鉴权 + GW_ADMIN_KEY 注入
     ▼                                        ▼
gateway-adapter.parseGatewayFrame() ──翻译──► useWebSocketData
     │                                          ├─ liveQPS/latency/gpuUtil(节点聚合)
     │                                          ├─ nodes(四源归一化) → DeviceInventoryManager
     │                                          └─ throughputHistory(差分) → Dashboard 图表
     ▼
REST 兜底轮询 (/console/gw/v1/*: logs·timeline·alerts·models/summary)
     └─► /audit · /alerts 消费页 · A2A 心跳(useA2AAgents 30s)
```

KPI 真实化铁则: 无源指标显「—」禁造数；gpuUtil 例外由节点 gpu 字段聚合推导（L-12a）。

## 4. 门禁矩阵（16 条命令，本地绿 = CI 绿）

| 层 | 门禁 | 守护的 ADR |
| --- | --- | --- |
| 类型 | typecheck（双旗标） | ADR-013 |
| 规范 | lint + lint:fp + astgrep(7 规则) | ADR-002/014 |
| 测试 | test:unit + test:coverage(thresholds) + test:e2e | ADR-003/011 |
| 安全 | gitleaks + S6 十维 | ADR-006 |
| 体量/熵 | size / knip / color / dup 四基线 | ADR-012 |
| 元 | guardrail-probe(20 探针) + doctor(12) + smart:audit | ADR-004 |
| 链路 | chain-verify + e2e(PWA 资产/i18n/离线) | ADR-007/008/009 |

## 5. 技术栈清单

Node 22+ · pnpm 12（catalog 锁版本）· TS strict 双旗标 · Vite 6 · React 18 · Tailwind v4（CSS 变量 token: theme.css）· Radix/shadcn（ui/ 禁改区）· Recharts · CodeMirror 6 · Vitest 4 三工作区 · Playwright · lighthouse 12.6.1 · jscpd 5.4.1 · 零运行时依赖部署件。
