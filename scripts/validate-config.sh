#!/bin/bash

set -e

echo "========================================="
echo "YYC³ 配置验证脚本"
echo "========================================="

NODE=$1

if [ -z "$NODE" ]; then
    echo "❌ 请指定节点名称"
    echo "用法: $0 <node-name>"
    echo "示例: $0 yyc3-33"
    exit 1
fi

CONFIG_FILE="/opt/yyc3/${NODE}/.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: ${CONFIG_FILE}"
    exit 1
fi

echo ""
echo "📋 验证配置文件: ${CONFIG_FILE}"
echo ""

# 加载环境变量
set -a
source ${CONFIG_FILE}
set +a

echo "✅ 配置文件加载成功"
echo ""

echo "========================================="
echo "节点信息"
echo "========================================="
echo "节点名称: ${NODE_NAME}"
echo "节点角色: ${NODE_ROLE}"
echo "节点 IP: ${NODE_IP}"
echo "节点位置: ${NODE_LOCATION}"
echo ""

echo "========================================="
echo "数据库配置"
echo "========================================="
echo "主机: ${DB_HOST}"
echo "端口: ${DB_PORT}"
echo "数据库: ${DB_NAME}"
echo "用户: ${DB_USER}"
echo "密码: ******"
echo ""

echo "========================================="
echo "Redis 配置"
echo "========================================="
echo "主机: ${REDIS_HOST}"
echo "端口: ${REDIS_PORT}"
echo "数据库: ${REDIS_DB}"
echo ""

echo "========================================="
echo "API 配置"
echo "========================================="
echo "端口: ${API_PORT}"
echo "工作进程: ${API_WORKERS}"
echo "超时: ${API_TIMEOUT}"
echo ""

echo "========================================="
echo "验证数据库连接"
echo "========================================="

# 测试数据库连接
if command -v psql &> /dev/null; then
    if PGPASSWORD=${DB_PASSWORD} psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1;" &> /dev/null; then
        echo "✅ 数据库连接成功"
    else
        echo "❌ 数据库连接失败"
    fi
else
    echo "⚠️  psql 未安装，跳过数据库连接测试"
fi

echo ""
echo "========================================="
echo "验证 Redis 连接"
echo "========================================="

# 测试 Redis 连接
if command -v redis-cli &> /dev/null; then
    if redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} ping &> /dev/null; then
        echo "✅ Redis 连接成功"
    else
        echo "❌ Redis 连接失败"
    fi
else
    echo "⚠️  redis-cli 未安装，跳过 Redis 连接测试"
fi

echo ""
echo "========================================="
echo "验证 API 服务"
echo "========================================="

# 测试 API 服务
if command -v curl &> /dev/null; then
    if curl -f -s http://localhost:${API_PORT}/health &> /dev/null; then
        echo "✅ API 服务正常"
    else
        echo "⚠️  API 服务未响应"
    fi
else
    echo "⚠️  curl 未安装，跳过 API 服务测试"
fi

echo ""
echo "========================================="
echo "配置验证完成"
echo "========================================="
echo ""
