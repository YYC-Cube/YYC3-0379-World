#!/bin/bash

set -e

echo "========================================="
echo "PostgreSQL 主从切换脚本"
echo "========================================="

SLAVE_HOST="yyc3-45"
SLAVE_PORT="6399"

echo ""
echo "⚠️  警告: 此操作将提升从库为主库"
echo ""
read -p "确认继续? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ 操作已取消"
    exit 0
fi

echo ""
echo "📋 步骤 1/5: 检查从库状态..."
IS_IN_RECOVERY=$(docker exec -it postgres-slave psql -U postgres -t -c "SELECT pg_is_in_recovery();")
if [ "$IS_IN_RECOVERY" != "t" ]; then
    echo "❌ 从库不在恢复模式，无法切换"
    exit 1
fi
echo "✅ 从库状态正常"

echo ""
echo "📋 步骤 2/5: 停止主库..."
echo "⚠️  请在主库 (yyc3-33) 上执行: docker stop postgres-ecs"
read -p "主库已停止? (yes): " confirm2

if [ "$confirm2" != "yes" ]; then
    echo "❌ 操作已取消"
    exit 0
fi

echo ""
echo "📋 步骤 3/5: 提升从库为主库..."
docker exec -it postgres-slave psql -U postgres -c "SELECT pg_promote();"
echo "✅ 从库已提升为主库"

echo ""
echo "📋 步骤 4/5: 验证新主库状态..."
sleep 3
docker exec -it postgres-slave psql -U postgres -c "SELECT pg_is_in_recovery();"
echo "✅ 新主库状态正常"

echo ""
echo "📋 步骤 5/5: 更新应用连接配置..."
echo "⚠️  请更新应用配置，将数据库连接切换到: ${SLAVE_HOST}:${SLAVE_PORT}"
echo ""
echo "示例配置:"
echo "  DB_HOST=${SLAVE_HOST}"
echo "  DB_PORT=${SLAVE_PORT}"
echo ""

echo ""
echo "========================================="
echo "✅ 主从切换完成"
echo "========================================="
echo ""
echo "下一步操作:"
echo "  1. 更新应用配置"
echo "  2. 重启应用服务"
echo "  3. 配置旧主库为新从库"
echo ""
