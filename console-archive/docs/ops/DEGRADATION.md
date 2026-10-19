# 降级策略 — DEGRADATION（离线 / 半可用 / 只读）

> 原则：**看盘系统宁降级不停服**。每层降级都有明确的用户可见形态与自动恢复路径。

## 1. 网络层降级（自动，无感）

| 场景 | 行为 | 依据 |
| --- | --- | --- |
| 完全离线 | SW 缓存壳服务导航；已缓存资产命中 | ADR-007（network-first→cache 兜底） |
| WS 断开 | 前端 connectionState 降级 + REST 轮询接续 KPI | useWebSocketData 双轨 |
| 网关 5xx | 熔断状态机（closed→open→half-open），前端显示 breaker 态 | gateway-adapter mapUpstreamStatus |
| 单数据源失败 | 该源置「—」，其余源继续（真实化铁则不造数） | device-inventory 四源设计 |
| fetch 不可能（SSR/无网） | 可选链兜底为空态 | ADR-011 判例 |

## 2. 存储层降级（自动）

| 场景 | 行为 |
| --- | --- |
| IndexedDB 不可用 | yyc3-storage 降级契约：读→[]、写静默容错（hooks 单测背书）；内存态当前会话不丢 |
| localStorage 满 | lsSet try/catch；设置退化为会话级 |
| 跨标签页通道断 | BroadcastChannel 缺失时各页独立（无同步但不崩） |

## 3. 服务层降级（半可用形态）

| 场景 | 用户可见形态 | 恢复 |
| --- | --- | --- |
| console-server 宕（公网） | ECS 401/Traefik 错误页 | ops.mjs heal（NAS 不受影响——独立形态） |
| NAS console 宕（局域网） | 3210 拒连 | @reboot cron / ops.mjs heal / 手工 pm2 start |
| GW_ADMIN_KEY 缺失 | gw 代理 503（设计映射，非 401） | 注入 key 重启 |
| 网关容器宕 | gw 代理 5xx + WS 断 | compose restart: unless-stopped 自拉 + L-13 健康收口 |
| Ollama 宕 | LAN 代理 502 | Ollama 服务自启/手工 |

## 4. 只读形态（人工介入时）

- **适用**：数据库维护 / 迁移窗口 / 事故隔离。
- **做法**：前端天然只读友好（无服务端写路径穿浏览器）；需冻结数据时停网关容器写入口（docker pause 0379-world-gateway-1），前端 KPI 转「—」/缓存态，历史数据走 IDB/LS 本地态仍可查看。
- **解除**：docker unpause → 健康探针 → KPI 自动回填。

## 5. 断网演练清单（回归用）

1. `pnpm build` 产物 + 任一形态部署
2. e2e：离线降级 + 离线多路由（已固化 2 用例）
3. 手工：DevTools Offline → 重载壳层 / 切 4 路由 / 触发一个捕获错误看 AppError.traceId
4. 恢复联网 → KPI 自动回填、SW 更新检查

## 6. 明确不降级项（fail-closed）

| 项 | 理由 |
| --- | --- |
| 鉴权（env 缺失） | 503 而非放行——公网面宁拒不漏 |
| 网关密钥缺失 | gw 503 设计映射 |
| token/签名校验 | 永不跳过（constantTimeEqual + exp + jti 全链） |
| unit 档真实依赖 | 零外部依赖红线（integration 档显式出口） |
