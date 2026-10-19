# 跨域契约 Contracts — YYC³ Token Console

> 契约 = 跨域共享的唯一归属地。域目录（ai-family/ide/service-test/design-system…）互引虽被层级契约允许，
> 但**跨域复用逻辑必须下沉到本清单所列位置**，禁止域间复制粘贴（ADR-002）。

## 1. 类型契约（src/app/types/ — 唯一类型定义层）

| 文件 | 承载域 | 关键类型 |
| --- | --- | --- |
| core.ts | 认证/节点/WS | UserRole · AppUser · NodeData · NodeStatusType · WebSocketDataState · **ModelProviderId**（S3 拆环下沉）· BaseSeverity |
| network-sync.ts | 错误/网络同步 | **AppError**（含 traceId, L-05）· ErrorCategory/Severity · NetworkInterface · ViewState |
| ops-monitor.ts | 监控/运维 | PatrolResult · AlertRule · AlertEvent · StoreName（IndexedDB 契约） |
| ai-provider.ts | AI 提供商 | ModelProviderDef · ConfiguredModel · PROVIDER_CAPABILITIES |
| ui-shared.ts | UI 共享 | QuickAction · CommandCategory · PWA 类型 |
| design-system.ts | 设计系统 | ColorToken · TypographyToken · ChapterStatus |

**同名异构判例**：跨域同名类型必须域名限定改名（IdeChatMessage / StoredDBConnection / ServiceTestStatus——S2 判例），禁止第三份拷贝。

## 2. 网络契约（src/app/lib/http.ts — fetchWithTimeout）

```
fetchWithTimeout(input, init?, timeoutMs = 8000)
  · init.signal 优先（取消语义保留）
  · 默认 8s AbortSignal.timeout
  · 底层 globalThis.fetch → 测试 vi.stubGlobal 可拦（ADR-011）
```
**红线**：组件/hooks 禁直连裸 fetch（33 处已收敛，grep 残留 0）；端点权威源 = lib/api-config + lib/env-config + lib/ollama-url。

## 3. 存储契约（src/app/lib/yyc3-storage.ts）

- **localStorage**：lsGet/lsSet/lsGetJSON + LOCALSTORAGE_KEYS 常量表（键名唯一事实源，如 `yyc3_locale` / `yyc3_terminal_history`——同名近似键 `yyc3-lang` 属 ide-mock 域，判例）。
- **IndexedDB**：idbGetAll/idbPut/idbPutMany/idbClear + StoreName 联合类型（types/ops-monitor）；**降级契约**：无 IDB 环境 idbGetAll catch→[]、写函数静默容错——hooks 层依赖此契约工作（ADR-011）。
- **BroadcastChannel**：onStorageChange 跨标签页同步。

## 4. 错误契约（src/app/lib/error-handler.ts）

```
captureError(error, { category?, severity?, source?, userAction?, traceId?, silent? }) → AppError
trySafe / trySafeSync(fn, source?) → [data, AppError|null]
```
- AppError 含 `traceId`（L-05：自动 8 位 / 注入优先——网关 request 上下文对齐通道）；
- 全局监听器（installGlobalErrorListeners）= 唯一合法 console 消费基础设施（App.tsx 噪声过滤为唯一例外，S6 甄别）；
- 组件/hooks 禁裸 console.*。

## 5. WS 消息契约（src/app/lib/gateway-adapter.ts）

网关 `{event:"metrics"}` 帧 → parseGatewayFrame → 内部消息集：`node_status`(NodeData[]) / `system_stats` / `qps_update` / `throughput_history` / `heartbeat_ack`。
- KPI 真实化铁则：无源显「—」；gpuUtil 例外由节点 gpu 聚合推导（L-12a）。
- counter 差分含回滚守卫；stats 所有权机制（WS 源接管后 REST 轮询不覆盖）。

## 6. 提供商契约（src/app/config/providers/）

`builtin-providers.json`（24 提供商 / 69 模型）+ `provider-schema.ts`（zod/mini 全量 safeParse）——**新增提供商只改 JSON 零代码**，schema 测试自动守护（id 唯一性/分类映射）。

## 7. 部署件契约（deploy/*.mjs 四件套 ↔ console.env）

| 环境变量 | 消费方 | 语义 |
| --- | --- | --- |
| PORT / HOST / DIST_DIR | console-server | 监听与产物目录（ECS 布局需 DIST_DIR=dist） |
| CONSOLE_AUTH_SECRET + CONSOLE_ADMIN_PASSWORD | 同上 | 二者同时配置才启用鉴权（fail-closed） |
| GW_ORIGIN / GW_ADMIN_KEY | 同上 | 网关上游与密钥注入（浏览器零密钥） |
| ALLOW_ORIGIN / ALLOW_ORIGIN_CIDR | server.mjs (LAN) | CORS 白名单 |

服务端审计：`console-audit.log` JSONL（ts/event/ip 零 PII，gitignore 域）。
