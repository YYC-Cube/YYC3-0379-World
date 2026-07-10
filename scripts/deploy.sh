#!/bin/bash

set -e

DEPLOY_ENV=${1:-staging}
VERSION=${2:-latest}
PROJECT_DIR="/opt/yyc3/${DEPLOY_ENV}"

echo "========================================="
echo "YYC³ 自动化部署脚本"
echo "========================================="
echo "环境: ${DEPLOY_ENV}"
echo "版本: ${VERSION}"
echo "目录: ${PROJECT_DIR}"
echo "========================================="

if [ ! -d "${PROJECT_DIR}" ]; then
    echo "❌ 项目目录不存在: ${PROJECT_DIR}"
    exit 1
fi

cd "${PROJECT_DIR}"

echo ""
echo "📋 步骤 1/6: 拉取最新代码..."
git pull origin main

echo ""
echo "📋 步骤 2/6: 拉取最新 Docker 镜像..."
docker-compose pull

echo ""
echo "📋 步骤 3/6: 备份数据库..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backups/db_backup_${TIMESTAMP}.sql"
mkdir -p backups
docker exec postgres pg_dump -U postgres yyc3_gpt > "${BACKUP_FILE}"
echo "✅ 数据库备份完成: ${BACKUP_FILE}"

echo ""
echo "📋 步骤 4/6: 停止旧服务..."
docker-compose down

echo ""
echo "📋 步骤 5/6: 启动新服务..."
docker-compose up -d

echo ""
echo "📋 步骤 6/6: 健康检查..."
sleep 10

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ 服务健康检查通过"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⏳ 等待服务启动... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ 服务健康检查失败"
    echo "📋 查看日志:"
    docker-compose logs --tail=100 gateway
    exit 1
fi

echo ""
echo "========================================="
echo "✅ 部署完成"
echo "========================================="
echo "服务状态:"
docker-compose ps

echo ""
echo "访问地址:"
if [ "${DEPLOY_ENV}" = "production" ]; then
    echo "  API: https://api.0379.world"
    echo "  文档: https://api.0379.world/docs"
else
    echo "  API: https://staging-api.0379.world"
    echo "  文档: https://staging-api.0379.world/docs"
fi

echo ""
echo "查看日志: docker-compose logs -f gateway"
echo "========================================="
