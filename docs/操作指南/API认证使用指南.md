---
file: API认证使用指南.md
description: YYC³ API认证使用指南 - JWT和API Key认证说明
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-04-08
updated: 2026-04-08
status: active
tags: [api],[auth],[security],[jwt],[api-key]
category: documentation
language: zh-CN
priority: critical
---

# YYC³ API 认证使用指南

**文档说明**: 本文档说明如何使用 JWT 和 API Key 认证访问 YYC³ API  
**更新时间**: 2026-04-08 02:15  
**当前版本**: v1.0.0

---

## 📋 认证方式总览

YYC³ API 支持两种认证方式：

| 认证方式 | 适用场景 | 有效期 | 安全级别 |
|---------|---------|--------|---------|
| **API Key** | 服务端调用、脚本集成 | 永久 | ⭐⭐⭐ |
| **JWT Token** | 前端应用、移动应用 | 24小时 | ⭐⭐⭐⭐ |

---

## 🔑 API Key 认证

### 默认 API Key

```
开发环境: yyc3_api_key_dev_2026
生产环境: yyc3_api_key_prod_2026
```

**⚠️ 安全提示**: 生产环境请务必修改默认 API Key！

### 使用方式

#### 方式一：HTTP Header

```bash
curl -X GET "https://api.0379.world/v1/models" \
  -H "X-API-Key: yyc3_api_key_dev_2026"
```

#### 方式二：Query Parameter

```bash
curl -X GET "https://api.0379.world/v1/models?api_key=yyc3_api_key_dev_2026"
```

### 生成新的 API Key

```python
import secrets

api_key = f"yyc3_api_key_{secrets.token_hex(16)}"
print(f"新API Key: {api_key}")
```

### 配置 API Key

在 `.env` 文件中添加：

```bash
API_KEYS=yyc3_api_key_dev_2026,yyc3_api_key_prod_2026,yyc3_api_key_custom_xxx
```

---

## 🎫 JWT Token 认证

### 获取 JWT Token

**端点**: `POST /v1/auth/token`

**请求体**:
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 使用 JWT Token

```bash
curl -X GET "https://api.0379.world/v1/models" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### JWT Token 配置

在 `.env` 文件中配置：

```bash
JWT_SECRET_KEY=your_secret_key_here_change_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

---

## 🚫 免认证端点

以下端点无需认证：

| 端点 | 说明 |
|------|------|
| `/health` | 健康检查 |
| `/v1/ping` | Ping 测试 |
| `/metrics` | Prometheus 监控指标 |
| `/docs` | API 文档 |
| `/openapi.json` | OpenAPI 规范 |

---

## 🔧 认证配置

### 启用/禁用认证

在 `.env` 文件中配置：

```bash
AUTH_ENABLED=true  # 启用认证
# AUTH_ENABLED=false  # 禁用认证（仅开发环境）
```

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `AUTH_ENABLED` | 是否启用认证 | `true` |
| `JWT_SECRET_KEY` | JWT 密钥 | `yyc3_jwt_secret_key_change_in_production_2026` |
| `JWT_ALGORITHM` | JWT 算法 | `HS256` |
| `JWT_EXPIRATION_HOURS` | JWT 过期时间（小时） | `24` |
| `API_KEYS` | API Key 列表（逗号分隔） | `yyc3_api_key_dev_2026,yyc3_api_key_prod_2026` |

---

## 📝 代码示例

### Python 示例

```python
import requests

API_BASE = "https://api.0379.world"
API_KEY = "yyc3_api_key_dev_2026"

# 方式一：使用 API Key
headers = {"X-API-Key": API_KEY}
response = requests.get(f"{API_BASE}/v1/models", headers=headers)
print(response.json())

# 方式二：使用 JWT Token
auth_response = requests.post(
    f"{API_BASE}/v1/auth/token",
    json={"username": "admin", "password": "password"}
)
token = auth_response.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{API_BASE}/v1/models", headers=headers)
print(response.json())
```

### JavaScript 示例

```javascript
const API_BASE = "https://api.0379.world";
const API_KEY = "yyc3_api_key_dev_2026";

// 方式一：使用 API Key
fetch(`${API_BASE}/v1/models`, {
  headers: {
    "X-API-Key": API_KEY
  }
})
  .then(response => response.json())
  .then(data => console.log(data));

// 方式二：使用 JWT Token
fetch(`${API_BASE}/v1/auth/token`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    username: "admin",
    password: "password"
  })
})
  .then(response => response.json())
  .then(data => {
    const token = data.access_token;
    return fetch(`${API_BASE}/v1/models`, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
  })
  .then(response => response.json())
  .then(data => console.log(data));
```

### cURL 示例

```bash
# 使用 API Key
curl -X GET "https://api.0379.world/v1/models" \
  -H "X-API-Key: yyc3_api_key_dev_2026"

# 使用 JWT Token
curl -X GET "https://api.0379.world/v1/models" \
  -H "Authorization: Bearer your_jwt_token_here"
```

---

## 🔒 安全最佳实践

### 1. 生产环境配置

```bash
# .env.production
AUTH_ENABLED=true
JWT_SECRET_KEY=$(openssl rand -hex 32)  # 生成随机密钥
API_KEYS=$(python3 -c "import secrets; print('yyc3_api_key_' + secrets.token_hex(16))")
```

### 2. 密钥管理

- ✅ 使用环境变量存储密钥
- ✅ 定期轮换 API Key
- ✅ 为不同环境使用不同的密钥
- ❌ 不要在代码中硬编码密钥
- ❌ 不要在版本控制中提交密钥

### 3. HTTPS 强制

生产环境必须使用 HTTPS：

```nginx
# Traefik 配置
http:
  routers:
    api:
      rule: "Host(`api.0379.world`)"
      tls:
        certResolver: letsencrypt
```

### 4. 限流保护

已启用限流中间件：

```python
# 默认配置
RATE_LIMIT_REQUESTS = 100  # 每分钟请求数
RATE_LIMIT_WINDOW = 60     # 时间窗口（秒）
```

---

## 🚨 错误处理

### 认证失败响应

**状态码**: `401 Unauthorized`

**响应体**:
```json
{
  "detail": "Invalid API key"
}
```

或

```json
{
  "detail": "Invalid or expired token"
}
```

### 常见错误

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `Invalid API key` | API Key 不正确 | 检查 API Key 是否正确 |
| `Invalid or expired token` | JWT Token 过期或无效 | 重新获取 Token |
| `Missing authentication credentials` | 未提供认证信息 | 添加认证 Header |
| `Rate limit exceeded` | 请求频率过高 | 降低请求频率 |

---

## 📊 认证流程图

```
┌─────────────────────────────────────────────────────────────┐
│                      API 请求                                │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              检查是否为免认证端点                             │
│  (/health, /v1/ping, /metrics, /docs, /openapi.json)       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                是免认证端点？
                        │
        ┌───────────────┴───────────────┐
        │ 是                             │ 否
        ▼                                ▼
┌─────────────────┐           ┌─────────────────────────────┐
│  直接访问        │           │  检查认证信息                │
└─────────────────┘           └───────────┬─────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────────────┐
                              │  优先级：API Key > JWT Token   │
                              └───────────┬───────────────────┘
                                          │
                        ┌─────────────────┼─────────────────┐
                        │                 │                 │
                        ▼                 ▼                 ▼
                  ┌──────────┐      ┌──────────┐      ┌──────────┐
                  │ API Key  │      │JWT Token │      │  无认证  │
                  │  验证    │      │  验证    │      │          │
                  └────┬─────┘      └────┬─────┘      └────┬─────┘
                       │                 │                 │
                       ▼                 ▼                 ▼
                  ┌──────────┐      ┌──────────┐      ┌──────────┐
                  │  成功？   │      │  成功？   │      │  401     │
                  └────┬─────┘      └────┬─────┘      └──────────┘
                       │                 │
               ┌───────┴───────┐ ┌───────┴───────┐
               │ 是             │ │ 是             │
               ▼                ▼ ▼                ▼
          ┌─────────────────────────────────────────┐
          │          访问受保护资源                  │
          └─────────────────────────────────────────┘
```

---

## 📝 更新记录

| 日期 | 版本 | 更新内容 | 更新人 |
|------|------|---------|--------|
| 2026-04-08 | v1.0.0 | 初始版本，创建 API 认证使用指南 | AI导师 |

---

## 🔗 相关文档

- [四机职责分配总览](四机职责分配总览.md)
- [生产环境实际运行状态](../生产环境实际运行状态.md)
- [YYC3-战略规划v2](YYC3-战略规划v2.md)
