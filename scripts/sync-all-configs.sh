#!/bin/bash

set -e

echo "========================================="
echo "YYC³ 批量配置同步脚本"
echo "========================================="

NODES=("yyc3-22" "yyc3-33" "yyc3-45" "yyc3-77")
CONFIG_REPO="/opt/yyc3/config"

echo ""
echo "📋 目标节点: ${NODES[@]}"
echo ""

echo "📋 步骤 1/3: 拉取最新配置..."
cd ${CONFIG_REPO}
git pull origin main
echo "✅ 配置已更新"

echo ""
echo "📋 步骤 2/3: 同步配置到各节点..."
for node in "${NODES[@]}"; do
    echo ""
    echo "----------------------------------------"
    echo "同步配置到 ${node}..."
    echo "----------------------------------------"
    
    # 检查节点是否在线
    if ping -c 1 ${node} &> /dev/null; then
        # 同步配置文件
        rsync -avz --delete \
            ${CONFIG_REPO}/.env.common \
            ${CONFIG_REPO}/.env.production \
            ${CONFIG_REPO}/.env.development \
            ${CONFIG_REPO}/nodes/${node}/.env \
            ${node}:/opt/yyc3/${node}/
        
        echo "✅ ${node} 配置同步完成"
    else
        echo "⚠️  ${node} 节点离线，跳过"
    fi
done

echo ""
echo "📋 步骤 3/3: 验证配置..."
for node in "${NODES[@]}"; do
    echo ""
    echo "验证 ${node} 配置..."
    ssh ${node} "cd /opt/yyc3/${node} && ls -la .env" 2>/dev/null || echo "⚠️  ${node} 配置验证失败"
done

echo ""
echo "========================================="
echo "✅ 批量配置同步完成"
echo "========================================="
echo ""
echo "下一步操作:"
echo "  1. 检查各节点配置: ssh <node> 'cat /opt/yyc3/<node>/.env'"
echo "  2. 重启服务: ssh <node> 'cd /opt/yyc3/<node> && docker-compose restart'"
echo "  3. 验证服务: curl http://<node>:<port>/health"
echo ""
