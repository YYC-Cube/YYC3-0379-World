#!/bin/bash

set -e

echo "========================================="
echo "YYC³ 配置同步脚本"
echo "========================================="

CONFIG_REPO="/opt/yyc3/config"
NODE=$1

if [ -z "$NODE" ]; then
    echo "❌ 请指定节点名称"
    echo "用法: $0 <node-name>"
    echo "示例: $0 yyc3-33"
    exit 1
fi

NODE_CONFIG_DIR="${CONFIG_REPO}/nodes/${NODE}"

if [ ! -d "$NODE_CONFIG_DIR" ]; then
    echo "❌ 节点配置目录不存在: ${NODE_CONFIG_DIR}"
    exit 1
fi

echo ""
echo "📋 步骤 1/5: 拉取最新配置..."
cd ${CONFIG_REPO}
git pull origin main
echo "✅ 配置已更新"

echo ""
echo "📋 步骤 2/5: 验证配置文件..."
if [ ! -f "${NODE_CONFIG_DIR}/.env" ]; then
    echo "❌ 节点配置文件不存在: ${NODE_CONFIG_DIR}/.env"
    exit 1
fi

if [ ! -f "${CONFIG_REPO}/.env.common" ]; then
    echo "❌ 通用配置文件不存在: ${CONFIG_REPO}/.env.common"
    exit 1
fi
echo "✅ 配置文件验证通过"

echo ""
echo "📋 步骤 3/5: 合并配置文件..."
TARGET_DIR="/opt/yyc3/${NODE}"
mkdir -p ${TARGET_DIR}

# 合并通用配置和节点配置
cat ${CONFIG_REPO}/.env.common > ${TARGET_DIR}/.env
echo "" >> ${TARGET_DIR}/.env
echo "# ==================== 节点特定配置 ====================" >> ${TARGET_DIR}/.env
cat ${NODE_CONFIG_DIR}/.env >> ${TARGET_DIR}/.env

# 如果是生产环境，合并生产配置
if [ "$NODE" == "yyc3-33" ] || [ "$NODE" == "yyc3-45" ]; then
    echo "" >> ${TARGET_DIR}/.env
    echo "# ==================== 生产环境配置 ====================" >> ${TARGET_DIR}/.env
    cat ${CONFIG_REPO}/.env.production >> ${TARGET_DIR}/.env
fi

# 如果是开发环境，合并开发配置
if [ "$NODE" == "yyc3-22" ]; then
    echo "" >> ${TARGET_DIR}/.env
    echo "# ==================== 开发环境配置 ====================" >> ${TARGET_DIR}/.env
    cat ${CONFIG_REPO}/.env.development >> ${TARGET_DIR}/.env
fi

echo "✅ 配置文件已合并"

echo ""
echo "📋 步骤 4/5: 验证必需的环境变量..."
REQUIRED_VARS=(
    "NODE_NAME"
    "NODE_ROLE"
    "NODE_IP"
    "DB_HOST"
    "DB_PORT"
    "DB_NAME"
    "DB_USER"
    "DB_PASSWORD"
    "REDIS_HOST"
    "REDIS_PORT"
)

MISSING_VARS=0
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" ${TARGET_DIR}/.env; then
        echo "❌ 缺少必需的环境变量: ${var}"
        MISSING_VARS=1
    fi
done

if [ $MISSING_VARS -eq 1 ]; then
    echo "❌ 配置验证失败"
    exit 1
fi
echo "✅ 所有必需的环境变量已配置"

echo ""
echo "📋 步骤 5/5: 重启服务..."
read -p "是否重启服务? (yes/no): " restart

if [ "$restart" == "yes" ]; then
    cd ${TARGET_DIR}
    docker-compose down
    docker-compose up -d
    echo "✅ 服务已重启"
else
    echo "⚠️  跳过服务重启"
fi

echo ""
echo "========================================="
echo "✅ 配置同步完成"
echo "========================================="
echo ""
echo "配置文件位置: ${TARGET_DIR}/.env"
echo ""
echo "验证命令:"
echo "  cat ${TARGET_DIR}/.env"
echo "  docker-compose config"
echo ""
