#!/bin/bash

# ⚠️ RETIRED 2026-10-05：目标架构已退役——ECS yyc3-33 现仅运行 Traefik 公网边缘（无 PG/LB 容器），
# 现役数据面 = NAS yyc3-45 compose 栈内建 PG15/Redis（deploy/nas/docker-compose.nas.yml）。
# 本脚本保留作历史参考；确认要执行已退役流程时显式放行：YYC3_ALLOW_RETIRED=1 $0
if [ "${YYC3_ALLOW_RETIRED:-0}" != "1" ]; then
    echo "❌ [RETIRED] 本脚本面向已退役的 yyc3-33 PG/LB 架构；现役 DB 备份: core/scripts/yyc3_db_backup.sh" >&2
    exit 1
fi


set -e

echo "========================================="
echo "PostgreSQL 主库配置脚本"
echo "节点: yyc3-33 (主库)"
echo "========================================="

PG_DATA="/var/lib/postgresql/data"
PG_CONFIG="/etc/postgresql"
PG_ARCHIVE="/data/nas_yyc3/pg_archive"

echo ""
echo "📋 步骤 1/6: 创建归档目录..."
mkdir -p ${PG_ARCHIVE}
chown -R postgres:postgres ${PG_ARCHIVE}
chmod 700 ${PG_ARCHIVE}
echo "✅ 归档目录创建完成: ${PG_ARCHIVE}"

echo ""
echo "📋 步骤 2/6: 备份原配置文件..."
if [ -f "${PG_DATA}/postgresql.conf" ]; then
    cp ${PG_DATA}/postgresql.conf ${PG_DATA}/postgresql.conf.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ 配置文件已备份"
fi

if [ -f "${PG_DATA}/pg_hba.conf" ]; then
    cp ${PG_DATA}/pg_hba.conf ${PG_DATA}/pg_hba.conf.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ 访问控制文件已备份"
fi

echo ""
echo "📋 步骤 3/6: 复制新配置文件..."
cp /opt/yyc3/config/postgresql/master/postgresql.conf ${PG_DATA}/postgresql.conf
cp /opt/yyc3/config/postgresql/master/pg_hba.conf ${PG_DATA}/pg_hba.conf
chown postgres:postgres ${PG_DATA}/postgresql.conf ${PG_DATA}/pg_hba.conf
chmod 600 ${PG_DATA}/postgresql.conf ${PG_DATA}/pg_hba.conf
echo "✅ 配置文件已更新"

echo ""
echo "📋 步骤 4/6: 创建复制用户..."
sudo -u postgres psql -c "CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD '${REPLICATOR_PASSWORD:?must_set_REPLICATOR_PASSWORD}';" 2>/dev/null || echo "⚠️  复制用户已存在"
echo "✅ 复制用户配置完成"

echo ""
echo "📋 步骤 5/6: 创建复制槽..."
sudo -u postgres psql -c "SELECT pg_create_physical_replication_slot('replica_slot_yyc3_45');" 2>/dev/null || echo "⚠️  复制槽已存在"
sudo -u postgres psql -c "SELECT pg_create_physical_replication_slot('replica_slot_yyc3_77');" 2>/dev/null || echo "⚠️  复制槽已存在"
echo "✅ 复制槽创建完成"

echo ""
echo "📋 步骤 6/6: 重启 PostgreSQL..."
docker restart postgres-ecs
sleep 5
echo "✅ PostgreSQL 已重启"

echo ""
echo "========================================="
echo "✅ 主库配置完成"
echo "========================================="
echo ""
echo "验证命令:"
echo "  docker exec -it postgres-ecs psql -U postgres -c \"SELECT * FROM pg_replication_slots;\""
echo "  docker exec -it postgres-ecs psql -U postgres -c \"SELECT * FROM pg_stat_replication;\""
echo ""
