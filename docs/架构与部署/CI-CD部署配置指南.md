---
file: CI-CD部署配置指南.md
description: YYC3 CI/CD 全链路部署配置指南 — Docker Hub + NAS SSH 直连
author: AI Tutor
version: v1.0.0
created: 2026-09-02
updated: 2026-09-02
status: active
tags: [ci-cd],[deploy],[docker-hub],[nas],[ssh],[github-actions]
category: guide
---

# CI/CD 部署配置指南

## 概述

YYC3 项目使用 GitHub Actions 实现 CI/CD 全链路自动化，流水线结构如下：

```
lint → test + security(并行) → build → deploy → 健康验证
```

当前 **lint / test / security** 三阶段已全部通过。**build / deploy** 阶段需要额外配置后方可启用。

---

## 一、当前状态

| Job | 状态 | 说明 |
|-----|------|------|
| 代码质量检查 | ✅ 通过 | black + isort + flake8 + mypy |
| 安全扫描 | ✅ 通过 | safety + bandit |
| 单元测试 | ✅ 通过 | pytest + coverage |
| 构建镜像 | ⬜ 跳过 | 缺少 Docker Hub 凭证 |
| 部署生产环境 | ⬜ 跳过 | 依赖 build + NAS 网络不可达 |

---

## 二、配置 Docker Hub（构建镜像）

### 2.1 为什么需要 Docker Hub？

build job 负责将代码构建为 Docker 镜像并推送到 Docker Hub，NAS 上的 deploy 流程从 Docker Hub 拉取镜像进行部署。使用 Docker Hub 作为镜像仓库有以下优势：

- 构建一次，多处部署
- 镜像版本管理（SHA tag）
- 回滚便捷（指定历史 tag）
- 减少 NAS 构建压力

### 2.2 创建 Docker Hub Access Token

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 点击右上角头像 → **Account Settings**
3. 左侧菜单 → **Security** → **New Access Token**
4. 填写描述（如 `YYC3-CI-CD`），权限选择 **Read & Write**
5. 复制生成的 Token（只显示一次）

### 2.3 配置 GitHub Secrets

在项目根目录执行以下命令：

```bash
# 设置 Docker Hub 用户名
gh secret set DOCKER_USERNAME -b "你的DockerHub用户名"

# 设置 Docker Hub Access Token（或密码）
gh secret set DOCKER_PASSWORD -b "你的AccessToken"
```

### 2.4 验证

配置完成后，下次 push 到 main 分支时，CI 流水线中的「构建镜像」job 将自动执行镜像构建并推送。

---

## 三、配置 NAS SSH 直连（部署生产环境）

### 3.1 当前问题

`NAS_HOST` 当前值为 `100.65.172.88`（Tailscale 内网 IP），GitHub Actions Runner 不在 Tailscale 网络中，无法通过此 IP 建立 SSH 连接。

### 3.2 解决方案（二选一）

#### 方案 A：使用 NAS 公网 IP（推荐）

如果 NAS 有公网 IP 或 DDNS 域名：

```bash
# 更新 NAS_HOST 为公网可达地址
gh secret set NAS_HOST -b "你的公网IP或DDNS域名"
```

> **注意**: 需要在路由器上配置端口转发，将公网 22 端口（或自定义端口）映射到 NAS 的 SSH 端口。

#### 方案 B：配置 Tailscale Funnel

如果 NAS 只有 Tailscale 内网 IP，可通过 Tailscale Funnel 暴露 SSH：

1. 在 NAS 上执行：
```bash
# 启用 Funnel（需要 HTTPS 证书）
tailscale funnel --bg 2222
```

2. 配置 SSH 转发：
```bash
# 在 NAS 上创建 socat 转发（将 2222 转发到本地 22）
socat TCP-LISTEN:2222,fork,reuseaddr TCP:127.0.0.1:22 &
```

3. 更新 GitHub Secret：
```bash
# 使用 Tailscale Funnel 域名
gh secret set NAS_HOST -b "你的NAS名称.tailnet-name.ts.net"
```

4. 更新 CI 中 SSH 端口（如使用非标准端口）：
   - 在 `appleboy/ssh-action@v1.2.2` 的 `with` 中添加 `port: 2222`

### 3.3 当前 Secrets 清单

| Secret | 状态 | 说明 |
|--------|------|------|
| `NAS_HOST` | ✅ 已配置 | 需改为公网可达地址 |
| `NAS_USER` | ✅ 已配置 | NAS SSH 用户名 |
| `NAS_SSH_KEY` | ✅ 已配置 | SSH 私钥（对应 NAS 上 `~/.ssh/authorized_keys`） |
| `DOCKER_USERNAME` | ❌ 待配置 | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | ❌ 待配置 | Docker Hub Token/密码 |

---

## 四、NAS 端环境要求

### 4.1 必需服务

| 服务 | 要求 |
|------|------|
| Docker | 已安装并运行 |
| Docker Compose | v2.x+ |
| Git | 已安装，可从 GitHub 拉取 |
| SSH Server | 已启用，接受密钥认证 |

### 4.2 必需文件

NAS 上 `/Volume2/yyc3-33/` 目录需包含：

| 文件 | 说明 |
|------|------|
| `.env` | 环境变量（含 `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET_KEY` 等） |
| `docker-compose.yml` | 服务编排文件 |
| `Dockerfile` | Gateway 镜像构建文件 |

### 4.3 .env 必需变量

CI 部署流程会检查以下变量是否存在，缺失将导致部署中断：

```bash
POSTGRES_PASSWORD     # 数据库密码
REDIS_PASSWORD        # Redis 密码
JWT_SECRET_KEY        # JWT 签名密钥
API_KEYS              # API 密钥列表
ZHIPU_API_KEY         # 智谱 API 密钥
```

---

## 五、配置完成后的 CI 完整流程

```
git push main
    │
    ├─ lint (代码质量检查)
    │   ├─ black --check
    │   ├─ isort --check
    │   ├─ flake8
    │   └─ mypy (advisory)
    │
    ├─ test (单元测试) ← 依赖 lint
    │   └─ pytest --cov
    │
    ├─ security (安全扫描) ← 依赖 lint
    │   ├─ safety check
    │   └─ bandit
    │
    ├─ build (构建镜像) ← 依赖 test + security
    │   ├─ Docker Hub 登录
    │   ├─ 构建 Docker 镜像
    │   └─ 推送到 Docker Hub
    │
    └─ deploy (部署生产) ← 依赖 build
        ├─ 检查 GitHub Secrets
        ├─ 检查 NAS .env 变量
        ├─ SSH 到 NAS
        ├─ git pull origin main
        ├─ docker compose up -d --build gateway
        └─ 全链路健康验证
```

---

## 六、快速恢复命令

```bash
# 进入项目目录
cd /Users/yanyu/YYC-Cube/YYC3-0379-World

# 查看当前 Secrets
gh secret list

# 查看最近 CI 运行状态
gh run list --limit 5

# 手动触发 CI（无需 push）
gh workflow run "YYC3 CI/CD Pipeline" --ref main

# 查看最新 CI 日志
gh run view $(gh run list --limit 1 --json databaseId -q '.[0].databaseId') --log
```

---

## 七、故障排查

### build 阶段失败

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| `Username and password required` | DOCKER_USERNAME/PASSWORD 未配置 | 按第二章配置 |
| `denied: requested access to the resource is denied` | Token 权限不足 | 确认 Token 有 Read & Write 权限 |
| `Dockerfile not found` | 项目根目录缺少 Dockerfile | 检查 Dockerfile 位置 |

### deploy 阶段失败

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| `ssh: connect to host ... port 22: Connection timed out` | NAS_HOST 不可达 | 按第三章配置公网 IP |
| `Permission denied (publickey)` | SSH 密钥不匹配 | 确认 NAS_SSH_KEY 对应 NAS 上 authorized_keys |
| `docker compose: command not found` | NAS 上未安装 docker compose | 安装 Docker Compose v2 |
| `缺少必需的 GitHub Secrets` | Secrets 不完整 | 按第三章检查清单补全 |

---

**下次操作**: 获取 Docker Hub 凭证和 NAS 公网 IP 后，参照本指南配置即可完成全链路 CI/CD 闭环。