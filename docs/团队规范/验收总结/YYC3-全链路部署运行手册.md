# YYC³ 全链路部署运行手册

> **版本**: v2.0 (Tailscale 拓扑适配) | **适用场景**: 首次部署 / 滚动升级 / 故障恢复
> **硬件矩阵**: yyc3-33(ECS) + yyc3-22(MacMax) + yyc3-45(NAS) + yyc3-101(DGX) + yyc3-102(DGX)
> **主网络**: Tailscale VPN（替代原 WireGuard 设计）
> **核心原则**: 有序启动 · 端到端验证 · 可回滚

---

## 一、前置准备

### 1.1 GitHub Secrets 配置清单

在 GitHub 仓库 → **Settings → Secrets and variables → Actions** 中配置以下 Secrets：

| Secret 名称 | 示例值 | 说明 |
|------------|--------|------|
| `DOCKER_USERNAME` | `yyc3` | Docker Hub 用户名 |
| `DOCKER_PASSWORD` | `dckr_pat_xxx` | Docker Hub Token |
| `SSH_PRIVATE_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----\n...` | 所有节点的统一 SSH 私钥 |
| `ECS_HOST` | `39.97.53.176` | yyc3-33 公网 IP |
| `ECS_USER` | `root` | |
| `MACBOOK_HOST` | `100.87.159.21` | yyc3-22 Tailscale IP |
| `MACBOOK_USER` | `yanyu` | |
| `NAS_HOST` | `100.65.172.88` | yyc3-45 Tailscale IP |
| `NAS_USER` | `YYC3` | |
| `NAS_SSH_PORT` | `22` | |
| `DGX101_HOST` | `100.65.64.49` | yyc3-101 Tailscale IP |
| `DGX101_USER` | `nvidia` | |
| `DGX102_HOST` | `100.76.167.103` | yyc3-102 Tailscale IP |
| `DGX102_USER` | `nvidia` | |
| `SLACK_WEBHOOK` | `https://hooks.slack.com/...` | 可选：部署通知 |
| `ZHIPU_API_KEY` | — | ⚠️ 当前已过期，需重新申请 |
| `JWT_SECRET_KEY` | — | 生产环境必填 |
| `API_KEYS` | `sk-yyc3-prod-key-001` | 生产环境必填 |

### 1.2 SSH 密钥分发（一次性）

```bash
# 生成统一部署密钥
ssh-keygen -t ed25519 -f ~/.ssh/yyc3_deploy -N ""

# 分发到各节点（使用 Tailscale IP 或 Host Name）
ssh-copy-id -i ~/.ssh/yyc3_deploy.pub root@39.97.53.176           # yyc3-33 ECS
ssh-copy-id -i ~/.ssh/yyc3_deploy.pub yanyu@100.87.159.21        # yyc3-22 MacMax (Tailscale)
ssh-copy-id -i ~/.ssh/yyc3_deploy.pub YYC3@100.65.172.88         # yyc3-45 NAS (Tailscale)
ssh-copy-id -i ~/.ssh/yyc3_deploy.pub nvidia@100.65.64.49        # yyc3-101 DGX (Tailscale)
ssh-copy-id -i ~/.ssh/yyc3_deploy.pub nvidia@100.76.167.103      # yyc3-102 DGX (Tailscale)

# 将私钥内容复制到 GitHub Secret `SSH_PRIVATE_KEY`
cat ~/.ssh/yyc3_deploy

# 验证 SSH 配置（推荐写入 ~/.ssh/config）
cat >> ~/.ssh/config << 'EOF'
Host yyc3-33
    HostName 39.97.53.176
    User root
Host yyc3-22
    HostName 100.87.159.21
    User yanyu
Host yyc3-45
    HostName 100.65.172.88
    User YYC3
Host yyc3-n1
    HostName 100.65.64.49
    User nvidia
Host yyc3-n2
    HostName 100.76.167.103
    User nvidia
EOF
```

### 1.3 各节点环境检查清单

```bash
# ── 1. 创建部署目录 ──
sudo mkdir -p /opt/yyc3/production
sudo chown $USER:$USER /opt/yyc3/production

# ── 2. 安装 Docker ──
# Ubuntu (ECS/NAS/DGX):
sudo apt update && sudo apt install -y docker.io docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# macOS (MacMax):
brew install --cask docker
open /Applications/Docker.app

# ── 3. 验证 Docker ──
docker --version && docker compose version

# ── 4. 克隆代码库 ──
git clone https://github.com/yyc3/YYC3-0379-World.git /opt/yyc3/production
cd /opt/yyc3/production && git checkout main

# ── 5. 配置环境变量 ──
cp .env.example .env
# 编辑 .env 填入生产密钥
vim .env
```

---

## 二、部署拓扑（实际网络 — Tailscale）

```
                        公网 (HTTPS 443)
                            │
                       ┌────┴────┐
                       │ yyc3-33 │  阿里云ECS 8G/100M
                       │ Traefik │  Prometheus + Grafana + Loki
                       └────┬────┘
                            │ Tailscale VPN (100.x.x.x)
         ┌──────────────────┼────────────────────┐
         │                  │                    │
    ┌────┴────┐     ┌───────┴───────┐    ┌──────┴──────┐
    │ yyc3-22 │     │ yyc3-45      │    │ yyc3-101    │
    │ MacMax  │     │ NAS/工作站     │    │ yyc3-102    │
    │ 128G/4T │     │ 32G RAID      │    ├── DGX GB10 ─┤
    │ macOS   │     │ Gateway v5   │    │ 模型部署主阵地│
    │ 代码中心 │     │ PG + Redis   │    │ Ollama GPU   │
    │ SSH枢纽  │     │ NFS共享存储   │    │ 双机互联     │
    └─────────┘     └──────────────┘    └──────────────┘

  ⚠️ yyc3-77 (iMac) 当前 offline，不参与部署
  ⚠️ 网络已从 WireGuard 切换为 Tailscale（100.x.x.x 网段）
  ⚠️ NAS 宿主机直接运行 PostgreSQL + Redis（非 Docker 容器）
  ⚠️ NAS 提供 NFS 共享存储（/mnt/models），DGX 和 MacMax 挂载使用
  ⚠️ DGX GB10 双机为模型推理主阵地，通过 Tailscale 互联
```

### 2.1 节点信息速查

| 节点 | Host Name | Tailscale IP | SSH 用户 | 角色 | 运行服务 |
|------|-----------|-------------|---------|------|---------|
| yyc3-33 | ECS | — (公网) | root | 公网入口 | Traefik + Prometheus + Grafana + Loki |
| yyc3-22 | MacMax | 100.87.159.21 | yanyu | 代码中心 | 开发机 + SSH枢纽 + Ollama CPU |
| yyc3-45 | NAS | 100.65.172.88 | YYC3 | **API网关 + 存储** | **gateway:8000** + PG + Redis + NFS |
| yyc3-101 | DGX GB10 | 100.65.64.49 | nvidia | **模型部署 Node-1** | Ollama GPU 主推理 |
| yyc3-102 | DGX GB10 | 100.76.167.103 | nvidia | **模型部署 Node-2** | Ollama GPU 热备推理 | │ 128G/4T   │ │ 128G/4T  │    │  128G/4T      │
 │ API+Ollama│ │ GPU推理  │    │  GPU推理      │
 │ PG Primary│ │ Node-1   │    │  Node-2       │
 └─────┬─────┘ └──────────┘    └───────────────┘

       │
 ┌─────┴─────┐
 │ yyc3-45   │
 │ 32G RAID  │
 │ PG备用+备份│
 └───────────┘

```

### 2.2 Step-by-Step 部署步骤

```bash
# ═══════════════════════════════════════════════════════════════
# Step 0: 环境准备（各节点一次性）
# ═══════════════════════════════════════════════════════════════
# 在各节点执行 "节点环境检查清单" 中的 1-5 步

# ═══════════════════════════════════════════════════════════════
# Step 1: 基础设施层 — PostgreSQL + Redis
# ═══════════════════════════════════════════════════════════════

# 在 yyc3-22 (MacMax) 上执行:
cd /opt/yyc3/production

# 启动 PostgreSQL (Patroni 主库)
docker compose -f core/database/docker/docker-compose.stable.yml up -d postgres
# 等待 30s 确认就绪
docker compose -f core/database/docker/docker-compose.stable.yml logs postgres | tail -5
# 预期: "database system is ready to accept connections"

# 启动 Redis
docker compose -f core/database/docker/docker-compose.stable.yml up -d redis
docker compose exec redis redis-cli ping
# 预期: PONG

# 初始化数据库 schema
docker compose -f core/database/docker/docker-compose.stable.yml exec -T postgres \
  psql -U postgres -d yyc3_gpt < core/database/init/002_knowledge_base_schema.sql
echo "✅ 数据库初始化完成"

# ═══════════════════════════════════════════════════════════════
# Step 2: 推理层 — Ollama 本地模型
# ═══════════════════════════════════════════════════════════════

# 在 yyc3-22 (MacMax) 上执行:
docker compose -f core/database/docker/docker-compose.stable.yml up -d ollama
# 等待模型加载
sleep 15
curl http://localhost:11434/api/tags
# 预期: 返回模型列表 JSON

# 拉取基础模型（首次只需一次）
ollama pull llama3.2
ollama pull qwen2.5:7b
ollama pull nomic-embed-text  # 用于 RAG embedding

# ═══════════════════════════════════════════════════════════════
# Step 3: 应用层 — API Gateway
# ═══════════════════════════════════════════════════════════════

# 在 yyc3-22 (MacMax) 上执行:
docker compose -f core/database/docker/docker-compose.stable.yml up -d api
sleep 10

# 验证 API 服务
curl -s http://localhost:8000/health | python3 -m json.tool
# 预期: status=healthy, 所有服务 reachable

# ═══════════════════════════════════════════════════════════════
# Step 4: 配置同步到其他节点
# ═══════════════════════════════════════════════════════════════

# 从 yyc3-22 同步 .env 和配置到其他节点
rsync -avz --progress /opt/yyc3/production/.env yyc3-45:/opt/yyc3/production/.env
rsync -avz --progress /opt/yyc3/production/.env root@yyc3-33:/opt/yyc3/production/.env
rsync -avz --progress /opt/yyc3/production/.env nvidia@yyc3-101:/opt/yyc3/production/.env
rsync -avz --progress /opt/yyc3/production/.env nvidia@yyc3-102:/opt/yyc3/production/.env

# ═══════════════════════════════════════════════════════════════
# Step 5: 负载均衡层 — HAProxy（仅在 yyc3-33 ECS）
# ═══════════════════════════════════════════════════════════════

# 在 yyc3-33 (ECS) 上执行:
cd /opt/yyc3/production
docker compose -f core/database/docker/docker-compose.stable.yml up -d haproxy
sleep 5

# 验证 HAProxy 状态
echo "show stat" | socat stdio /var/run/haproxy/admin.sock 2>/dev/null || \
  curl -s http://localhost:8404/stats | head -20

# ═══════════════════════════════════════════════════════════════
# Step 6: 监控层 — Prometheus + Loki + Grafana
# ═══════════════════════════════════════════════════════════════

# 在 yyc3-33 (ECS) 上执行:
docker compose -f core/database/docker/docker-compose.stable.yml up -d prometheus loki grafana
sleep 10

# 验证
curl -s http://localhost:9090/-/healthy
# 预期: Prometheus is Healthy
curl -s http://localhost:3100/ready
# 预期: Ready

# ═══════════════════════════════════════════════════════════════
# Step 7: GPU 推理节点（如果启用 DGX Spark）
# ═══════════════════════════════════════════════════════════════

# 在 yyc3-101 (DGX Spark) 上执行:
cd /opt/yyc3/production
docker compose -f core/database/docker/docker-compose.stable.yml up -d ollama-gpu
sleep 15
curl -s http://localhost:11434/api/tags
# 预期: GPU模型列表

# 在 yyc3-102 (DGX Spark) 上执行（同上）
cd /opt/yyc3/production
docker compose -f core/database/docker/docker-compose.stable.yml up -d ollama-gpu
```

### 2.3 使用 CI/CD 一键部署（推荐）

```bash
# 推送 main 分支 → 自动触发完整 CI/CD 流水线
git checkout main
git add .
git commit -m "chore: production deployment $(date +%Y%m%d)"
git push origin main
```

CI/CD 将自动执行:

1. ✅ 代码质量检查 (lint)
2. ✅ 单元测试 + 集成测试
3. ✅ 安全扫描
4. ✅ Docker 多平台构建
5. ✅ **5节点并行部署**（矩阵策略，`fail-fast: false`）
6. ✅ 配置同步
7. ✅ 全链路 API 验证
8. ✅ 部署通知

> ⚠️ 确保 GitHub Secrets 中已配置所有 5 节点的 SSH 密钥

---

## 三、全链路验证

### 3.1 核心 API 验证

```bash
BASE_URL="https://api.0379.world"

# ── 1. 健康检查 ──
echo "=== 健康检查 ==="
curl -sf $BASE_URL/health | python3 -m json.tool

# ── 2. Ping ──
echo "=== Ping ==="
curl -sf $BASE_URL/v1/ping

# ── 3. 模型列表 ──
echo "=== 模型列表 ==="
curl -sf $BASE_URL/v1/models -H "X-API-Key: $API_KEY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data:
    print(f'  [{m[\"backend\"]:8s}] {m[\"id\"]:20s} {m[\"display_name\"]}')
print(f'  总计: {len(data)} 模型')
"

# ── 4. 模型类型路由 ──
echo "=== GPU感知路由 ==="
curl -sf "$BASE_URL/v1/model/type?model=llama3.2"
curl -sf "$BASE_URL/v1/model/type?model=glm-4-flash"
curl -sf "$BASE_URL/v1/model/type?model=deepseek-chat"

# ── 5. 聊天补全 ──
echo "=== 聊天补全 ==="
curl -sf -X POST $BASE_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "你好，回复 5 个字以内"}],
    "max_tokens": 50
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
content = data['choices'][0]['message']['content']
print(f'  Llama3.2: {content}')
"

# ── 6. 流式补全 ──
echo "=== 流式补全 ==="
curl -sfN -X POST $BASE_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "数到 3"}],
    "max_tokens": 100,
    "stream": true
  }' | head -5
echo ""
echo "  流式响应 ✅"

# ── 7. API 版本管理 ──
echo "=== API 版本 ==="
curl -sf $BASE_URL/v1/versions

# ── 8. 缓存统计 ──
echo "=== 缓存统计 ==="
curl -sf $BASE_URL/v1/cache/stats

# ── 9. 路由统计 ──
echo "=== 路由器统计 ==="
curl -sf $BASE_URL/v1/router/stats | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    for n in data[:3]:
        print(f'  Node: {n.get(\"node_id\",\"?\")} | status={n.get(\"status\",\"?\")} | weight={n.get(\"dynamic_weight\",\"?\")}')
"

# ── 10. RAG 检索 ──
echo "=== RAG 检索 ==="
curl -sf -X POST $BASE_URL/v1/rag/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"test","knowledge_base_ids":["00000000-0000-0000-0000-000000000000"],"top_k":1}' 2>&1 | head -3

echo ""
echo "═══════════════════════════════════════"
echo "  🎉 全链路验证完成"
echo "═══════════════════════════════════════"
```

### 3.2 多端跑通矩阵验证

| 端 | 命令 | 预期结果 | 验证结果 |
|----|------|---------|---------|
| **REST** | `curl https://api.0379.world/v1/chat/completions` | 200 + chat completion JSON | ⬜ |
| **SSE流式** | `curl -N https://api.0379.world/v1/chat/completions?stream=true` | 流式 SSE 事件 | ⬜ |
| **OpenAI SDK** | `python3 -c "from openai import OpenAI; ..."` | 正常返回 | ⬜ |
| **WebSocket** | `wscat -c wss://api.0379.world/ws/chat?api_key=...` | 双向消息 | ⬜ |
| **健康检查** | `curl https://api.0379.world/health` | 所有服务 healthy | ⬜ |
| **模型列表** | `curl https://api.0379.world/v1/models` | 模型列表 JSON | ⬜ |
| **/v1/model/type** | `curl https://api.0379.world/v1/model/type?model=llama3.2` | `local_cpu` | ⬜ |

### 3.3 一键验证脚本

```bash
# 运行项目自带的全链路验证
make ops-test-gateway

# 或者直接调用测试脚本
python3 tests/test_gateway_api.py
```

---

## 四、回滚流程

### 4.1 Docker 回滚

```bash
# 回滚到上一个版本
docker compose -f core/database/docker/docker-compose.stable.yml down api
docker compose -f core/database/docker/docker-compose.stable.yml pull api
docker compose -f core/database/docker/docker-compose.stable.yml up -d api

# # 回滚到指定版本
# docker compose -f core/database/docker/docker-compose.stable.yml down api
# docker pull yyc3/api:previous-tag
# docker compose -f core/database/docker/docker-compose.stable.yml up -d api
```

### 4.2 Git 回滚

```bash
# 回滚代码并重新部署
git revert HEAD~1 --no-edit
git push origin main
# CI/CD will auto-deploy
```

### 4.3 数据库回滚

```bash
# 使用 Alembic 回滚数据库
alembic downgrade -1

# 或者从备份恢复
make ops-db-backup
# 如果需要恢复:
# psql -h localhost -U postgres -d yyc3_gpt < backups/yyc3_gpt_YYYYMMDD.sql
```

### 4.4 故障恢复检查清单

| 症状 | 检查项 | 快速恢复 |
|------|--------|---------|
| API 503 | HAProxy 后端是否健康 | `docker compose restart api haproxy` |
| Redis 不可用 | `redis-cli ping` | `docker compose restart redis` |
| PostgreSQL 故障 | Patroni leader 选举 | `patronictl list` → `patronictl switchover` |
| Ollama 无响应 | `curl localhost:11434/api/tags` | `docker compose restart ollama` |
| 模型加载失败 | `ollama list` | 重新 `ollama pull <model>` |
| GPU 不可用 | `nvidia-smi` | 检查 `nvidia-docker` runtime |

---

## 五、部署后健康监控

### 5.1 7x24 监控面板

| 仪表盘 | 访问地址 | 默认凭据 |
|--------|---------|---------|
| Grafana | `https://api.0379.world:3000` | `admin` / `admin` |
| Prometheus | `https://api.0379.world:9090` | 内部访问 |
| HAProxy | `https://api.0379.world:8404/stats` | 内部访问 |

### 5.2 核心告警阈值

| 告警规则 | 阈值 | 响应 |
|---------|------|------|
| API 5xx 率过高 | > 5% in 5min | 检查日志 `docker compose logs api` |
| P95 延迟 > 3s | > 3s in 5min | 检查模型负载/GPU利用率 |
| Redis 不可用 | ping fail | `docker compose restart redis` |
| PostgreSQL 无 leader | pg_up == 0 | `patronictl list` 手动切换 |
| Ollama 无响应 | 探针 fail | `docker compose restart ollama` |
| 磁盘使用率 > 85% | df 检查 | 清理日志 / 扩展 NFS |

### 5.3 日志快速定位

```bash
# API 日志
docker compose logs -f --tail=100 api

# 数据库日志
docker compose logs -f --tail=50 postgres

# Ollama 日志
docker compose logs -f --tail=50 ollama

# HAProxy 日志
docker compose logs -f --tail=50 haproxy

# 结构化日志落盘
tail -f logs/api-*.log
```

---

## 六、有序启动速查卡

```
make ops-startup    # 一键有序启动（DB→Redis→Ollama→API→Monitor→LB）

# 等价于手动执行:
Step 1: docker compose up -d postgres          # 数据库
Step 2: docker compose up -d redis             # 缓存
Step 3: docker compose up -d ollama            # 推理
Step 4: docker compose up -d api               # API 网关
Step 5: docker compose up -d prometheus loki   # 监控
Step 6: docker compose up -d haproxy           # 负载均衡
Step 7: make ops-test-gateway                  # 全链路验证
```

---

## 七、环境变量配置文件

创建 `.env` 文件（**不要提交到 Git**）：

```bash
# ═══════════════════════════════════════════
# YYC³ 生产环境配置
# ═══════════════════════════════════════════

# 基础
ENVIRONMENT=production
HOST_IP=10.200.0.2
HOST_IP_SUFFIX=22

# 数据库
POSTGRES_PASSWORD=<生成强密码: openssl rand -base64 32>
REPLICATOR_PASSWORD=<生成强密码>
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_NAME=yyc3_gpt

# Redis
REDIS_PASSWORD=<生成强密码>
REDIS_HOST=redis
REDIS_PORT=6379

# Ollama
OLLAMA_HOST=0.0.0.0
OLLAMA_PORT=11434
OLLAMA_MODELS=/mnt/models

# API Key（生成多个以便轮换）
JWT_SECRET_KEY=<生成: openssl rand -base64 64>
API_KEYS=sk-yyc3-prod-key-001,sk-yyc3-prod-key-002

# CORS（生产环境限定来源）
ALLOWED_ORIGINS=https://api.0379.world,https://yyc3-admin.0379.world

# Traefik/HAProxy
LETSENCRYPT_EMAIL=admin@0379.world
CLOUDFLARE_API_TOKEN=<从 Cloudflare Dashboard 获取>
```

---

## 八、CI/CD 流水线工作流

```
                    main 分支推送
                         │
                    ┌────▼────┐
                    │  Lint   │ ← black + flake8 + mypy
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │  Test   │ ← pytest + coverage 80%
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Security│ ← safety + bandit
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │  Build  │ ← Docker Buildx 多平台
                    └────┬────┘
                         │
               ┌─────────┼─────────┐
               │         │         │
         ┌─────▼──┐ ┌───▼───┐ ┌───▼───┐
         │yyc3-33 │ │yyc3-22│ │yyc3-45│ ...
         │  ECS   │ │MacMax │ │ 工作站│
         └────┬───┘ └───┬───┘ └───┬───┘
              │         │         │
         ┌────▼─────────▼─────────▼───┐
         │      配置同步 (SCP)         │
         └────────────┬───────────────┘
                      │
               ┌──────▼───────┐
               │   全链路验证   │ ← 验证所有端点
               └──────┬───────┘
                      │
               ┌──────▼───────┐
               │   Slack通知   │
               └──────────────┘
```

---

## 附录 A: 常用运维命令速查

```bash
# ── 服务管理 ──
make ops-health             # 全节点健康检查
make ops-db-backup          # 数据库备份
make ops-failover           # 手动故障转移
make ops-lb-verify          # 验证负载均衡
make ops-sync-all           # 全量同步配置

# ── 容器管理 ──
docker compose ps           # 查看所有服务状态
docker compose logs -f api  # 跟踪 API 日志
docker compose restart api  # 重启 API 服务
docker compose down && docker compose up -d  # 完整重启

# ── 数据库 ──
psql -h localhost -U postgres -d yyc3_gpt    # 直接连接
patronictl list                               # 查看 Patroni 集群状态
patronictl switchover --master yyc3-22 --candidate yyc3-45  # 手动切换

# ── 网络 ──
wg show                                       # 查看 WireGuard 状态
ping -c 3 10.200.0.{1,2,3,4,5}               # 全节点 ping

# ── 存储 ──
df -h | grep /mnt                             # 查看 NFS 挂载状态
rsync -avz --progress /opt/yyc3/production/ yyc3-45:/opt/yyc3/production/  # 手动同步
```

---

## 附录 B: Node 角色速查

| 节点 | 主机名 | IP (Tailscale) | 规格 | 角色 | 运行服务 |
|------|--------|--------------|------|------|---------|
| yyc3-33 | ECS | 公网 | 8G/100M | 公网入口 | HAProxy + Prometheus + Loki + Grafana |
| yyc3-22 | MacMax | `100.87.159.21` | 128G/4T | 代码中心 | 开发机 + SSH枢纽 + Ollama CPU |
| yyc3-45 | NAS | `100.65.172.88` | 32G/RAID | **API网关 + 存储** | **Gateway v5** + PG Primary + Redis + NFS |
| yyc3-101 | DGX GB10 | `100.65.64.49` | 128G/4T | **模型部署 Node-1** | Ollama GPU 主推理（大模型负载） |
| yyc3-102 | DGX GB10 | `100.76.167.103` | 128G/4T | **模型部署 Node-2** | Ollama GPU 热备推理（故障转移） |

---

*本手册应与 [现状审核报告](file:///Users/yanyu/YYC-Cube/YYC3-0379-World/docs/YYC3-团队通用-标准规范/YYC3-验收闭环-建议总结/YYC3-现状审核-全链路五高分析报告.md) 和 [差距分析报告](file:///Users/yanyu/YYC-Cube/YYC3-0379-World/docs/YYC3-团队通用-标准规范/YYC3-验收闭环-建议总结/YYC3-设计原型差距分析报告.md) 配套使用。*
