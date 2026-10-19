# ADR-006: HMAC 会话 + 时间戳 + 限流 + jti 吊销

- 状态：Accepted
- 日期：2026-10-16（jti 吊销与审计落地；HMAC 骨架自批4）
- 决策者：首席安全官（S6 审计）
- 关联：deploy/console-auth.mjs · console-server.mjs · console-auth.test（18 用例）· e2e auth.spec

## 背景 Context

公网形态需要鉴权，但对象是**单管理员**（自己），且服务器是自写零依赖 Node（ADR-005）——没有现成 session 框架可用，也不能为单用户引入 OAuth/JWT 库的供应链面。

## 决策 Decision

自实现最小鉴权内核（纯函数 + 轻状态，`// @ts-check`）：
1. **签名**：HMAC-SHA256(body, secret)，payload `{exp, jti}` base64url；比对走 SHA-256 定长化 + `timingSafeEqual`（防时序侧信道）。
2. **时间戳**：`exp = now + 12h`，过期拒验（有效期封顶一切暴露窗口）。
3. **防暴力**：`LoginRateLimiter` 滑动窗口 5 次/5 分钟/IP（单进程内存态足够）。
4. **吊销（jti）**：logout 登记当前令牌 jti，`verifyToken` 拒已吊销令牌；内存 Map 惰性清理（重启清空可接受——TTL 封顶，重启即换会话语义）。
5. **审计**：login_ok/login_fail/logout 追加 JSONL（ts/event/ip，零 PII），异步尽力而为不阻断。
6. **Cookie**：HttpOnly + SameSite=Strict + Path=/；HTTPS 上游自动附加 Secure。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| JWT 库（jsonwebtoken） | 标准生态 | 引入 npm 依赖（违 ADR-005）；单管理员用不上刷新/多受众 | 供应链面不值 |
| Basic Auth | 最简单 | 无过期/无吊销/无限流；浏览器体验差 | 防暴力缺失 |
| OAuth/OIDC | 企业级 | 单管理员完全过重 | 运维成本失控 |
| 自实现 HMAC（选定） | 零依赖、密码学原语走 node:crypto 标准库 | 自实现需自证（18 用例：篡改/过期/密钥错/垃圾输入/限流窗口） | 测试+生产双实证 |

## 后果 Consequences

- 正面：三端实测全绿（NAS/ECS/本地：401 无泄露 / jti 吊销后旧 Cookie 401 / WS 101 穿门）；审计可回溯；限流防爆破。
- 负面：jti 吊销是内存态——重启清空（多管理员场景需持久化，见 backlog L-06）；「登出」在无持久化吊销的前提下重启即失效。
- 中性：12h TTL 内重放 inherent（Cookie 被窃取的前提是本机沦陷，威胁模型外）。

## 验证方式 Verification

console-auth.test 18 用例（constantTimeEqual 3 / sign+verify 5 / RateLimiter 4 / parseCookies 2 / jti 4）；e2e auth 3 用例（401 拒绝 / HttpOnly 签发穿门 / 未认证 401）；NAS+ECS 生产八点验证（S14/L-01）。

## 回滚路径 Rollback

鉴权可通过不配置 `CONSOLE_AUTH_SECRET`+`CONSOLE_ADMIN_PASSWORD` 整体关闭（本地/LAN 开发形态不受影响，fail-closed 设计）；替换为其他方案 = 重写 console-auth.mjs（≈2 天，接口面小）。
