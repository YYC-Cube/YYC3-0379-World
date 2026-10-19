# ADR-007: 手写 vanilla SW + PWA 全链 + CDN 回退

- 状态：Accepted
- 日期：2026-10-05（GAP-006 修复；2026-10-16 S11 相对路径修复补全）
- 决策者：首席架构师
- 关联：public/sw.js · scripts/inject-precache.mjs · lib/sw-register.ts · useYYC3Head · yyc3-icons.ts

## 背景 Context

PWA 离线能力是看盘系统刚需（断网时仍要看缓存的盘面）。标准方案是 vite-plugin-pwa（workbox）——但安装时触发供应链降级拦截（`workbox-build@7.4.1` → `@trickfilm400/rollup-plugin-off-main-thread@3.0.0-pre1` 无 provenance attestation，`ERR_PNPM_TRUST_DOWNGRADE`）。同时图标资产存在双重来源（本地 public/ 与 CDN），需要回退链。

## 决策 Decision

1. **手写 vanilla SW**（~120 行，零新依赖）：SPA 导航 network-first + Pages 深链 404 回退缓存壳；`/assets/*` 内容 hash 不可变 → cache-first + LRU 200 条；manifest/图标 → stale-while-revalidate；认证/网关/代理 API 端点**透传不缓存**。预缓存清单由 `inject-precache.mjs` build 后置注入（90 项，预热 2.92MB ≤ 6MB 预算）。
2. **注册 PROD-only**：dev 环境不注册（HMR 会被 SW 拦截破坏开发链路），scope 跟随 BASE_URL。
3. **CDN 回退**：`useYYC3Head` 运行时注入 + favicon onerror 三档回退（16/32/apple-touch → iconsCDN 地址）。
4. **资产相对路径**（S11 判例）：index.html 9 处 favicon/manifest 用相对路径——绝对路径在 /console/ 子路径形态全部 404。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| vite-plugin-pwa (workbox) | 标准化、功能全 | 供应链降级拦截（provenance 缺失）；黑盒策略难精确控制 API 透传 | 供应链红线一票否决 |
| 手写 vanilla SW（选定） | 零依赖、行为全透明、审计可读 | 策略手写需自测（离线 e2e 已覆盖） | 测试+e2e 双实证 |
| 不做离线 | 零成本 | 看盘系统断网即瞎 | 违背本地闭环定位 |

## 后果 Consequences

- 正面：断网重载壳层服务（e2e 实测）+ 离线多路由 4 路由全 200；预缓存体积有预算门禁；CDN 回退有单测断言 href 切换。
- 负面：SW 策略变更需手动维护 vanilla 代码；PROD-only 注册使 SW 问题只在生产暴露（e2e webServer 用生产构建弥补）。
- 中性：相对路径判例使根路径（Pages）与子路径（/console/）双形态通吃。

## 验证方式 Verification

e2e：离线降级（SW ready→断网→重载壳层）+ 离线多路由（4 路由断网 200）+ PWA 资产链路（manifest 13 icons 逐个 200）；S13 chain-verify dist 实证；useYYC3Head 单测（CDN 回退三档）。

## 回滚路径 Rollback

移除 sw-register 调用即禁用 SW（PWA 退化为在线应用）；vanilla SW 无构建耦合，删除零残留。workbox 若未来 provenance 补全可重评估（Superseded 流程）。
