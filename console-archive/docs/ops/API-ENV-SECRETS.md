# API 环境变量与密钥签发手册 — YYC³ 网关

> 口径: NAS 生产 `.env`（42 键实测）+ 网关校验链（core/api/config.py · middleware/auth.py）+ 虚拟密钥 API（/v1/admin/virtual-keys）。
> 铁律: 凭据只经环境变量/密钥文件，**本文档零凭据字面量**——所有"生成"均为可复制的 openssl 命令。

---

## 一、密钥体系总览（三层）

| 层 | 密钥 | 载体 | 用途 | 校验位置 |
| --- | --- | --- | --- | --- |
| **L1 根密钥**（服务端 .env） | API_KEYS | NAS `.env` → compose → 网关进程 | 业务调用方 `X-API-Key`（OpenAI 兼容 /v1/*） | middleware/auth.py `VALID_API_KEYS` |
| | ADMIN_API_KEYS | 同上 | 管理面 `/v1/admin/*`（留空=回退 API_KEYS） | `ADMIN_API_KEYS` |
| | JWT_SECRET_KEY | 同上 | 管理端 JWT 签名 | auth.py |
| | ZHIPU_API_KEY / OPENAI_API_KEY | 同上 | 上游厂商凭据（服务端持有，浏览器零接触） | 上游转发 |
| | POSTGRES/REDIS/DB_*_PASSWORD | 同上 | 数据层凭据 | compose |
| **L2 会话密钥**（console 部署件） | CONSOLE_AUTH_SECRET / CONSOLE_ADMIN_PASSWORD | console.env (600) | B 端登录 HMAC 会话 | console-auth.mjs |
| | GW_ADMIN_KEY | console.env | console-server 注入给网关的管理密钥（=L1 ADMIN_API_KEYS 同值） | — |
| **L3 虚拟密钥**（运行时签发） | vk-* | 网关 PG（virtual key 表） | 分发给下游使用者，可设过期/配额/启停 | virtual_key_manager |

校验链（实测语义，middleware/auth.py:362）: **ADMIN key 通吃**业务+管理面；业务 key 只通业务面；vk 按 L3 校验。

---

## 二、签发与生成（L1 根密钥）

### 生成命令（模板，可复制）

```bash
# 业务/管理 API Key（推荐 48 位 hex）
openssl rand -hex 24

# JWT 签名密钥（32 字节 hex）
openssl rand -hex 32

# 数据库/Redis 密码（24 位）
openssl rand -base64 18 | tr -d '/+=' | cut -c1-24

# 会话 HMAC 密钥（console 侧 CONSOLE_AUTH_SECRET，32 字节 hex）
openssl rand -hex 32

# console 管理员密码（16 位可读）
openssl rand -hex 10
```

### 放置与生效

1. 编辑 NAS `/Volume2/yyc3-33/.env`：新 key 追加到对应键（**逗号分隔可并存**，实现平滑轮换）：
   ```
   API_KEYS=<旧key>,<新key>
   ADMIN_API_KEYS=<旧admin>,<新admin>
   ```
2. 重建网关进程使 env 生效：`cd /Volume2/yyc3-33 && docker compose up -d --force-recreate gateway`（L-13 健康收口自动等待）；
3. 旧 key 保留期结束后从逗号列表移除 → 再重建一次（**两步轮换，零断服**）。

**注意**：`ADMIN_API_KEYS` 留空 = 管理面回退用 API_KEYS（单机部署兼容）；生产建议独立值。

---

## 三、虚拟密钥签发（L3，运行时动态）

**入口 A — B 端页面**：`https://<console>/gateway-keys`（GatewayKeysPanel，全套 CRUD：生成/启停/删除，key 脱敏为前 8 位 hint）。
**入口 B — API 直调**（需 ADMIN 密钥）：

```bash
# 签发（可设过期与配额）
curl -X POST https://api.0379.world/v1/admin/virtual-keys \
  -H "X-API-Key: $ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"name":"<用途名>","expires_at":"<ISO8601 或 null>"}'
# → 返回完整 key（仅此一次可见，服务端只存 hash/hint）

# 列表（owner/active_only 过滤；key 永以 hint 形态显示）
curl -H "X-API-Key: $ADMIN_KEY" https://api.0379.world/v1/admin/virtual-keys?active_only=true

# 启停 / 删除
curl -X PATCH .../virtual-keys/<key_id> -d '{"active":false}'
curl -X DELETE .../virtual-keys/<key_id>
```

**vk vs 根 key 的取舍**：vk 可随时吊销、可绑定过期、泄漏面小（分发物）；根 key 改 .env 需重建容器。**分发给第三方/临时用途一律用 vk**。

---

## 四、全量环境变量矩阵（NAS .env 42 键实测，按域分类）

### 数据层
| 键 | 说明 |
| --- | --- |
| POSTGRES_PASSWORD / REPLICATOR_PASSWORD | PG 主/复制凭据 |
| DB_HOST/PORT/USER/PASSWORD/NAME | 网关→PG 连接 |
| REDIS_HOST/PORT/DB/PASSWORD | 网关→Redis |

### 密钥与认证
| 键 | 说明 |
| --- | --- |
| API_KEYS | 业务密钥（逗号分隔，`X-API-Key` 头） |
| ADMIN_API_KEYS | 管理面密钥（留空回退 API_KEYS） |
| JWT_SECRET_KEY | 管理端 JWT 签名 |
| ZHIPU_API_KEY / OPENAI_API_KEY | 上游厂商凭据 |
| REGISTRY_HEARTBEAT_TOKEN | 模型心跳令牌 |

### Ollama 自动扫描（yyc3-77/yyc3-22 设备发现）
| 键 | 说明 |
| --- | --- |
| OLLAMA_HOST | 主 Ollama 实例（=100.76.167.103 · yyc3-22） |
| OLLAMA_PORT | 11434 |
| OLLAMA_DISCOVER_CIDR | 自动扫描网段（=192.168.3.0/24，覆盖 yyc3-77） |
| OLLAMA_LOCAL_HOSTS | 本地实例清单 |

### 服务与路由
| 键 | 说明 |
| --- | --- |
| API_HOST/PORT/WORKERS | 网关监听（0.0.0.0:8000） |
| ROUTER_ENABLED / REGISTRY_ENABLED | 路由与注册开关 |
| OPENAI_COMPATIBLE_UPSTREAMS | 静态上游补充 |
| CORS_ORIGINS / MAX_REQUEST_SIZE / LOG_LEVEL / LOG_FORMAT | 行为参数 |

### WireGuard（跨机房链路）
WG_INTERFACE/ADDRESS/PORT/PRIVATE_KEY/PUBLIC_KEY/DNS/PEER_ENDPOINT/PEER_PUBLIC_KEY

### 观测/其他
GRAFANA_ADMIN_PASSWORD · HOST_IP/HOST_IP_SUFFIX

---

## 五、console 侧环境变量（B 端部署件）

完整矩阵见 `docs/scripts/ENV-MATRIX.md`（部署件节）。核心四键：
`PORT/HOST/DIST_DIR`（监听与产物）· `CONSOLE_AUTH_SECRET/CONSOLE_ADMIN_PASSWORD`（会话）· `GW_ORIGIN/GW_ADMIN_KEY`（网关注入，**=L1 ADMIN_API_KEYS 同值**）。

---

## 六、轮换流程（零断服）

| 场景 | 步骤 |
| --- | --- |
| 业务 key 疑似泄漏 | ① 新 key 追加 API_KEYS → 重建 gateway → ② 调用方切换新 key → ③ 旧 key 移除 → 再重建 |
| 管理面 key 泄漏 | 同上（ADMIN_API_KEYS）+ 所有 vk 全量吊销（/gateway-keys）|
| CONSOLE_AUTH_SECRET 轮换 | 换 console.env 值 → 重启 console-server（全部会话失效=强制重登，jti Map 清空属预期） |
| JWT_SECRET_KEY 轮换 | 同上（管理端 JWT 全失效） |

## 七、红线

- 凭据只存 .env / console.env（600）——禁入源码/文档/示例；
- `.env` 不入 git（compose 变量化 + gateway.env.example 模板承载键名）；
- 管理面接口（/v1/admin/*）一律走 ADMIN key 或 vk 校验，浏览器零接触（console-server 注入）。
