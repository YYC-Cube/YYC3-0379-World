#!/bin/bash

set -e

echo "========================================="
echo "YYC³ 负载均衡故障切换测试脚本"
echo "========================================="

VIRTUAL_IP="192.168.3.100"
DOMAIN="api.0379.world"

echo ""
echo "⚠️  警告: 此脚本将测试故障切换功能"
echo "可能会短暂影响服务可用性"
echo ""
read -p "确认继续? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ 操作已取消"
    exit 0
fi

echo ""
echo "📋 1. 记录当前状态..."
echo "----------------------------------------"
echo "虚拟 IP 所在节点:"
ip addr show | grep "${VIRTUAL_IP}" && echo "当前节点持有虚拟 IP" || echo "当前节点未持有虚拟 IP"

echo ""
echo "后端服务器状态:"
echo "  yyc3-33: $(curl -s -o /dev/null -w '%{http_code}' http://yyc3-33:8000/health 2>/dev/null || echo 'DOWN')"
echo "  yyc3-45: $(curl -s -o /dev/null -w '%{http_code}' http://yyc3-45:8002/health 2>/dev/null || echo 'DOWN')"

echo ""
echo "📋 2. 模拟主节点故障..."
echo "----------------------------------------"
echo "停止 yyc3-33 上的 Nginx..."
docker stop nginx-lb 2>/dev/null || echo "Nginx 未运行"

echo ""
echo "等待 5 秒，观察故障切换..."
sleep 5

echo ""
echo "📋 3. 验证故障切换..."
echo "----------------------------------------"
echo "虚拟 IP 所在节点:"
ip addr show | grep "${VIRTUAL_IP}" && echo "当前节点持有虚拟 IP" || echo "当前节点未持有虚拟 IP"

echo ""
echo "测试服务可用性..."
for i in {1..10}; do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://${VIRTUAL_IP}/health 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        echo "  请求 ${i}: ✅ 200 OK"
    else
        echo "  请求 ${i}: ❌ ${RESPONSE}"
    fi
    sleep 0.5
done

echo ""
echo "📋 4. 恢复主节点..."
echo "----------------------------------------"
echo "启动 yyc3-33 上的 Nginx..."
docker start nginx-lb 2>/dev/null || echo "Nginx 已运行"

echo ""
echo "等待 5 秒，观察恢复..."
sleep 5

echo ""
echo "📋 5. 验证恢复状态..."
echo "----------------------------------------"
echo "虚拟 IP 所在节点:"
ip addr show | grep "${VIRTUAL_IP}" && echo "当前节点持有虚拟 IP" || echo "当前节点未持有虚拟 IP"

echo ""
echo "后端服务器状态:"
echo "  yyc3-33: $(curl -s -o /dev/null -w '%{http_code}' http://yyc3-33:8000/health 2>/dev/null || echo 'DOWN')"
echo "  yyc3-45: $(curl -s -o /dev/null -w '%{http_code}' http://yyc3-45:8002/health 2>/dev/null || echo 'DOWN')"

echo ""
echo "测试服务可用性..."
for i in {1..10}; do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://${VIRTUAL_IP}/health 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        echo "  请求 ${i}: ✅ 200 OK"
    else
        echo "  请求 ${i}: ❌ ${RESPONSE}"
    fi
    sleep 0.5
done

echo ""
echo "========================================="
echo "✅ 故障切换测试完成"
echo "========================================="
echo ""
echo "测试结果:"
echo "  1. 主节点故障后，虚拟 IP 是否切换: [观察上方输出]"
echo "  2. 服务是否保持可用: [观察上方输出]"
echo "  3. 主节点恢复后，是否正常工作: [观察上方输出]"
echo ""
