# ADR-001: Vite SPA 而非 Next.js SSR

- 状态：Accepted
- 日期：2025-09（项目奠基）
- 决策者：首席架构师
- 关联：GitHub Pages 部署（token.yyc3.vip）· ADR-005 零依赖部署

## 背景 Context

项目定位是**本地闭环多端推理矩阵数据看盘**：数据源是本地 NAS 网关 + 内网设备，部署目标包括 GitHub Pages（纯静态）与 LAN/公网自托管。团队规模小，运维人力集中在推理矩阵本身。候选框架为 Vite+React（SPA）与 Next.js（SSR/ISR）。

## 决策 Decision

选 Vite + React SPA，`createBrowserRouter` + NotFound 兜底，产物为纯静态文件（dist/），可被任何静态服务器（GitHub Pages / server.mjs / console-server.mjs）原样服务。不做 SSR/ISR/API Routes——一切后端交互走显式网关代理（`/console/gw/*`）。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| Next.js (SSR/ISR) | SEO、首屏服务端渲染、文件路由 | 需要 Node 运行时托管（Pages 不可用）；与零依赖部署冲突；看盘系统内网使用无 SEO 需求 | 运行时依赖与部署形态冲突；SEO 无意义 |
| Vite + React Router（选定） | 纯静态产物、构建快、HMR 好、部署面最广 | 深链需 404 回退机制（已解：404.html + `?yyc3_fallback=` 还原） | — |
| CRA / webpack | 生态旧 | 已停止维护、构建慢 | 落伍 |

## 后果 Consequences

- 正面：`pnpm build` 34s 产 90 chunks 纯静态；三端部署形态（Pages/LAN/公网）共享同一产物；无服务端渲染的水合复杂度。
- 负面：SPA 深链依赖 404 回退（Pages 形态依赖 404.html 的 `?yyc3_fallback=` 编解码，多一层机制）；首屏为 CSR（Lighthouse FCP 0.8s 可接受）。
- 中性：路由级懒加载（lazyEl）成为分包主手段（89 个异步 chunk）。

## 验证方式 Verification

`pnpm build` exit 0 + dist 无服务端依赖（S12 零密钥扫描通过）；e2e 路由冒烟（子路径挂载）+ 404 兜底用例（S11）。

## 回滚路径 Rollback

迁移 Next.js = 重写入口/路由/数据层适配（≈2-4 周），且必须同步放弃 GitHub Pages 形态——成本极高，决策错误概率低（本地看盘无 SSR 需求），视为不可逆战略决策。
