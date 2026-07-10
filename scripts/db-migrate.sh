#!/bin/bash

set -e

echo "========================================="
echo "YYC³ 数据库迁移脚本"
echo "========================================="

DEPLOY_ENV=${1:-production}
PROJECT_DIR="/opt/yyc3/${DEPLOY_ENV}"

if [ ! -d "${PROJECT_DIR}" ]; then
    echo "❌ 项目目录不存在: ${PROJECT_DIR}"
    exit 1
fi

cd "${PROJECT_DIR}"

echo ""
echo "📋 步骤 1/4: 备份数据库..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backups/db_migration_backup_${TIMESTAMP}.sql"
mkdir -p backups
docker exec postgres pg_dump -U postgres yyc3_gpt > "${BACKUP_FILE}"
echo "✅ 数据库备份完成: ${BACKUP_FILE}"

echo ""
echo "📋 步骤 2/4: 检查待执行的迁移..."
MIGRATIONS_DIR="migrations"
if [ -d "${MIGRATIONS_DIR}" ]; then
    PENDING_MIGRATIONS=$(find ${MIGRATIONS_DIR} -name "*.sql" -type f | wc -l)
    echo "发现 ${PENDING_MIGRATIONS} 个迁移文件"
    
    if [ ${PENDING_MIGRATIONS} -eq 0 ]; then
        echo "✅ 没有待执行的迁移"
        exit 0
    fi
else
    echo "✅ 迁移目录不存在，跳过迁移"
    exit 0
fi

echo ""
echo "📋 步骤 3/4: 执行数据库迁移..."
for migration in ${MIGRATIONS_DIR}/*.sql; do
    if [ -f "$migration" ]; then
        echo "执行迁移: $(basename $migration)"
        docker exec -i postgres psql -U postgres -d yyc3_gpt < "$migration"
        
        if [ $? -eq 0 ]; then
            echo "✅ 迁移成功: $(basename $migration)"
            mv "$migration" "${MIGRATIONS_DIR}/executed/"
        else
            echo "❌ 迁移失败: $(basename $migration)"
            echo "正在恢复备份..."
            docker exec -i postgres psql -U postgres -d yyc3_gpt < "${BACKUP_FILE}"
            exit 1
        fi
    fi
done

echo ""
echo "📋 步骤 4/4: 验证迁移结果..."
docker exec postgres psql -U postgres -d yyc3_gpt -c "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1;"

echo ""
echo "========================================="
echo "✅ 数据库迁移完成"
echo "========================================="
