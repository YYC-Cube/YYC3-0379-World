#!/bin/bash

echo "========================================="
echo "PostgreSQL 主从复制验证脚本"
echo "========================================="

MASTER_HOST="yyc3-33"
MASTER_PORT="5432"
SLAVE_HOST="yyc3-45"
SLAVE_PORT="6399"

echo ""
echo "📋 1. 检查主库复制状态..."
echo "----------------------------------------"
docker exec -it postgres-ecs psql -U postgres -c "
SELECT 
    client_addr AS 从库地址,
    state AS 状态,
    sent_lsn AS 发送位置,
    write_lsn AS 写入位置,
    flush_lsn AS 刷新位置,
    replay_lsn AS 应用位置,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS 延迟字节
FROM pg_stat_replication;
"

echo ""
echo "📋 2. 检查从库恢复状态..."
echo "----------------------------------------"
docker exec -it postgres-slave psql -U postgres -c "
SELECT 
    pg_is_in_recovery() AS 是否从库,
    pg_last_wal_receive_lsn() AS 接收位置,
    pg_last_wal_replay_lsn() AS 应用位置,
    pg_last_xact_replay_timestamp() AS 最后应用时间;
"

echo ""
echo "📋 3. 检查复制槽状态..."
echo "----------------------------------------"
docker exec -it postgres-ecs psql -U postgres -c "
SELECT 
    slot_name AS 槽名称,
    slot_type AS 槽类型,
    active AS 是否活跃,
    restart_lsn AS 重启位置
FROM pg_replication_slots;
"

echo ""
echo "📋 4. 测试数据同步..."
echo "----------------------------------------"

# 在主库创建测试表
TEST_TABLE="replication_test_$(date +%s)"
docker exec -it postgres-ecs psql -U postgres -d yyc3_gpt -c "
CREATE TABLE ${TEST_TABLE} (id serial PRIMARY KEY, data text, created_at timestamp default now());
INSERT INTO ${TEST_TABLE} (data) VALUES ('test_data_1'), ('test_data_2');
"

echo "✅ 主库测试表已创建: ${TEST_TABLE}"

# 等待复制
sleep 2

# 在从库查询测试表
echo ""
echo "从库查询结果:"
docker exec -it postgres-slave psql -U postgres -d yyc3_gpt -c "SELECT * FROM ${TEST_TABLE};"

# 清理测试表
docker exec -it postgres-ecs psql -U postgres -d yyc3_gpt -c "DROP TABLE ${TEST_TABLE};"
echo "✅ 测试表已清理"

echo ""
echo "📋 5. 检查复制延迟..."
echo "----------------------------------------"
docker exec -it postgres-ecs psql -U postgres -c "
SELECT 
    client_addr,
    state,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS 延迟字节,
    CASE 
        WHEN pg_wal_lsn_diff(sent_lsn, replay_lsn) < 1024 THEN '✅ < 1KB'
        WHEN pg_wal_lsn_diff(sent_lsn, replay_lsn) < 1048576 THEN '⚠️  < 1MB'
        ELSE '❌ > 1MB'
    END AS 延迟状态
FROM pg_stat_replication;
"

echo ""
echo "========================================="
echo "✅ 验证完成"
echo "========================================="
echo ""
echo "健康状态判断:"
echo "  ✅ 延迟 < 1KB: 优秀"
echo "  ⚠️  延迟 < 1MB: 良好"
echo "  ❌ 延迟 > 1MB: 需要优化"
echo ""
