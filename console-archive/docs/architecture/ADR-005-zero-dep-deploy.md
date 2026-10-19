# ADR-005: 部署服务器零 npm 运行时依赖

- 状态：Accepted
- 日期：2025-09（server.mjs 奠基；2026-10-16 console-server 延续并经 S14 十五维验证）
- 决策者：首席架构师
- 关联：deploy/server.mjs · deploy/console-server.mjs · ADR-001 / ADR-006

## 背景 Context

部署目标横跨 GitHub Pages（纯静态）、fnOS NAS（非标准 Linux，Docker 受限、系统目录封锁）、公网 ECS。部署服务器若依赖 npm 包，`node_modules` 必须随包分发或目标机可装依赖——在 NAS 场景两者都脆弱（fnOS 权限、无 registry 直连保障）。

## 决策 Decision

`deploy/*.mjs` 仅用 **Node 原生模块**（http / fs / path / crypto / zlib / child_process）。WS 中继客户端优先 `globalThis.WebSocket`（Node≥21 原生），Node 18 环境回退**动态 import("ws")**——ws 是运行时可选依赖而非静态依赖（缺失时如实 503，不静默降级）。静态服务含 zlib gzip（L-02 修复，perf 80→98）与内容协商（S11 settings 路径冲突修复）。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| Express + 中间件生态 | 功能全、社区方案多 | node_modules 随发版、供应链面扩大 | NAS 离线部署脆弱 |
| 手写零依赖（选定） | 单文件可审计、scp 即部署、供应链面为零 | 功能需自写（gzip/RFC 6455/内容协商均为手写） | 手写量可控且已有单测+集成测试 |
| Deno/Bun 单二进制 | 原生 TS | 运行时未在目标环境标准化 | 环境不可控 |

## 后果 Consequences

- 正面：S14 零依赖维度实证（import 全 `node:`+相对）；部署 = 4 个 mjs 文件 scp；无 supply-chain 面摊到运行时。
- 负面：手写 RFC 6455 帧解析/gzip/静态服务需自担维护（均有测试与生产实证兜底）；功能受限（无现成中间件）。
- 中性：ws 动态 import 是「零静态依赖」与「Node 18 兼容」的折中，保持声明零依赖（ESM 静态 import 才计入）。

## 验证方式 Verification

S14 双形态部署 15 维（含 SIGTERM 优雅退出、健康端点、401 无泄露）；grep import 全 node: 原生；集成测试（console-relay）真实子进程 + 桩网关全链。

## 回滚路径 Rollback

引入 Express = 加依赖 + 迁移路由（≈1 天）；技术上易、纪律上违反红线——回滚即承认 NAS 部署形态放弃，需重新论证。
