#!/bin/bash
# @file: deploy-nas-gateway.sh
# @description: YYC³ NAS 网关一键部署脚本
#   - 从仓库代码源同步最新 core/api 到部署目录
#   - 确保 .env 环境变量文件就绪（缺失时引导从模板创建）
#   - 确保 docker-compose.yml 为 .env 变量化版本（检测到硬编码凭据自动替换）
#   - 构建并启动服务 + 健康检查
# @author: YanYuCloudCube Team <admin@0379.email>
# @version: v1.0.0
# @created: 2026-08-29
# @updated: 2026-08-29
# @status: stable
# @tags: bash,nas,gateway,deploy,env
# @usage: bash scripts/deploy-nas-gateway.sh   # 需在 NAS 上运行

set -euo pipefail

# ---------- 路径常量 ----------
NAS_DEPLOY_DIR="/Volume2/yyc3-33"                   # 实际部署目录（compose/Dockerfile/app）
NAS_CODE_DIR="/Volume3/yyc3-app/YYC3-0379-World"    # 仓库代码源（git 同步目录）
DOCKER_BIN="/Volume3/@apps/DockerEngine/dockerd/bin/docker"
GATEWAY_CONTAINER="0379-world-gateway-1"
APP_SRC="$NAS_CODE_DIR/core/api"
REQ_SRC="$NAS_CODE_DIR/requirements.txt"
COMPOSE_TEMPLATE="$NAS_CODE_DIR/deploy/nas/docker-compose.nas.yml"
ENV_TEMPLATE="$NAS_CODE_DIR/deploy/nas/gateway.env.example"

# ---------- 颜色与日志 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "[$(date '+%F %T')] $*"; }
ok()   { echo -e "${GREEN}✓ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
fail() { echo -e "${RED}✗ $*${NC}"; exit 1; }

echo "=========================================="
echo "  YYC³ NAS 网关一键部署脚本"
echo "=========================================="
echo ""

# ---------- 前置校验 ----------
[ -d "$NAS_DEPLOY_DIR" ]            || fail "未检测到部署目录 $NAS_DEPLOY_DIR（脚本需在 NAS 上运行）"
[ -d "$APP_SRC" ]                   || fail "未检测到仓库代码源 $APP_SRC"
[ -x "$DOCKER_BIN" ]                || fail "未找到 Docker: $DOCKER_BIN"
[ -f "$COMPOSE_TEMPLATE" ]          || fail "缺少 compose 模板: $COMPOSE_TEMPLATE"

# ---------- 步骤 1: 同步最新代码 ----------
log "步骤 1/5: 同步最新网关代码"
rsync -a --delete "$APP_SRC/" "$NAS_DEPLOY_DIR/app/"
cp "$REQ_SRC" "$NAS_DEPLOY_DIR/requirements.txt"
ok "代码已同步: $NAS_DEPLOY_DIR/app/"

# ---------- 步骤 2: 确保 .env 就绪 ----------
log "步骤 2/5: 检查环境变量文件"
if [ ! -f "$NAS_DEPLOY_DIR/.env" ]; then
    warn ".env 不存在，从模板创建"
    cp "$ENV_TEMPLATE" "$NAS_DEPLOY_DIR/.env"
    fail "已生成 .env 模板，请先编辑 $NAS_DEPLOY_DIR/.env 填写真实凭据后重新运行"
fi
MISSING=""
for var in POSTGRES_PASSWORD DB_PASSWORD REDIS_PASSWORD ZHIPU_API_KEY JWT_SECRET_KEY API_KEYS; do
    grep -q "^${var}=[^C]" "$NAS_DEPLOY_DIR/.env" || MISSING="$MISSING $var"
done
[ -z "$MISSING" ] || fail ".env 缺少或未配置:${MISSING}（请编辑 $NAS_DEPLOY_DIR/.env）"
ok "环境变量文件就绪"

# ---------- 步骤 3: 确保 compose 为 .env 变量化版本 ----------
log "步骤 3/5: 检查 docker-compose.yml"
if grep -qE 'My151001|redis_0379|sk-yyc3-prod|58b7aa8756' "$NAS_DEPLOY_DIR/docker-compose.yml" 2>/dev/null; then
    warn "检测到硬编码凭据，替换为 .env 变量化模板"
    cp "$COMPOSE_TEMPLATE" "$NAS_DEPLOY_DIR/docker-compose.yml"
    ok "docker-compose.yml 已替换为 .env 变量化版本"
elif ! grep -q '\${POSTGRES_PASSWORD}' "$NAS_DEPLOY_DIR/docker-compose.yml" 2>/dev/null; then
    warn "compose 未使用 .env 变量，替换为模板"
    cp "$COMPOSE_TEMPLATE" "$NAS_DEPLOY_DIR/docker-compose.yml"
    ok "docker-compose.yml 已替换为模板"
else
    ok "docker-compose.yml 已使用 .env 变量"
fi

# ---------- 步骤 4: 清理旧 gateway 容器（避免端口冲突） ----------
log "步骤 4/5: 清理旧 gateway 容器"
"$DOCKER_BIN" rm -f "$GATEWAY_CONTAINER" 2>/dev/null || true
ok "旧容器已清理"

# ---------- 步骤 5: 构建并启动 ----------
log "步骤 5/5: 构建并启动服务"
cd "$NAS_DEPLOY_DIR"
export PATH="$(dirname "$DOCKER_BIN"):$PATH"   # 确保 docker compose 插件可被 CLI 发现
"$DOCKER_BIN" compose up -d --build
ok "服务已启动"

# ---------- 健康检查 ----------
log "等待服务就绪 (15s)..."
sleep 15
if curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
    ok "API 服务正常: http://localhost:8000/docs"
else
    warn "API 暂未响应，请查看日志: $DOCKER_BIN logs -f $GATEWAY_CONTAINER"
fi
"$DOCKER_BIN" ps --filter "name=$GATEWAY_CONTAINER" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "=========================================="
echo -e "${GREEN}✓ NAS 网关部署流程完成${NC}"
echo "=========================================="
