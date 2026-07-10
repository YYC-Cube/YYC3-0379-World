#!/bin/bash

set -e

MASTER_HOST="yyc3-33"
MASTER_PORT="5432"
SLAVE_PORT="6399"
REPLICATOR_USER="replicator"
REPLICATOR_PASS="${REPLICATOR_PASSWORD:?must_set_REPLICATOR_PASSWORD}"
PG_DATA="/var/lib/postgresql/data"

echo "========================================="
echo "PostgreSQL 从库配置脚本"
echo "节点: yyc3-45 (从库)"
echo "========================================="

echo ""
echo "📋 步骤 1/7: 停止从库服务..."
docker stop postgres-slave 2>/dev/null || echo "⚠️  从库未运行"
echo "✅ 从库已停止"

echo ""
echo "📋 步骤 2/7: 备份旧数据..."
if [ -d "${PG_DATA}" ] && [ "$(ls -A ${PG_DATA} 2>/dev/null)" ]; then
    BACKUP_DIR="/data/pg_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p ${BACKUP_DIR}
    mv ${PG_DATA}/* ${BACKUP_DIR}/ 2>/dev/null || true
    echo "✅ 旧数据已备份到: ${BACKUP_DIR}"
fi

echo ""
echo "📋 步骤 3/7: 清空数据目录..."
rm -rf ${PG_DATA}/*
echo "✅ 数据目录已清空"

echo ""
echo "📋 步骤 4/7: 从主库复制基础备份..."
echo "⏳ 这可能需要几分钟时间..."
export PGPASSWORD="${REPLICATOR_PASS}"
pg_basebackup \
    -h ${MASTER_HOST} \
    -p ${MASTER_PORT} \
    -U ${REPLICATOR_USER} \
    -D ${PG_DATA} \
    -Fp \
    -Xs \
    -P \
    -R
echo "✅ 基础备份完成"

echo ""
echo "📋 步骤 5/7: 配置从库参数..."
cat > ${PG_DATA}/postgresql.auto.conf << EOF
primary_conninfo = 'host=${MASTER_HOST} port=${MASTER_PORT} user=${REPLICATOR_USER} password=${REPLICATOR_PASS}'
primary_slot_name = 'replica_slot_yyc3_45'
EOF
chown -R postgres:postgres ${PG_DATA}
chmod 700 ${PG_DATA}
echo "✅ 从库参数配置完成"

echo ""
echo "📋 步骤 6/7: 创建 standby.signal 文件..."
touch ${PG_DATA}/standby.signal
chown postgres:postgres ${PG_DATA}/standby.signal
echo "✅ standby.signal 文件已创建"

echo ""
echo "📋 步骤 7/7: 启动从库服务..."
docker start postgres-slave
sleep 5
echo "✅ 从库已启动"

echo ""
echo "========================================="
echo "✅ 从库配置完成"
echo "========================================="
echo ""
echo "验证命令:"
echo "  docker exec -it postgres-slave psql -U postgres -c \"SELECT pg_is_in_recovery();\""
echo "  docker exec -it postgres-slave psql -U postgres -c \"SELECT * FROM pg_stat_wal_receiver;\""
echo ""
