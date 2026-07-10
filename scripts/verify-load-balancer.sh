#!/bin/bash

set -e

echo "========================================="
echo "YYC³ 负载均衡验证脚本"
echo "========================================="

VIRTUAL_IP="192.168.3.100"
DOMAIN="api.0379.world"

echo ""
echo "📋 1. 检查虚拟 IP..."
echo "----------------------------------------"
if ip addr show | grep -q "${VIRTUAL_IP}"; then
    echo "✅ 虚拟 IP ${VIRTUAL_IP} 已配置在当前节点"
else
    echo "⚠️  虚拟 IP ${VIRTUAL_IP} 未在当前节点"
    echo "可能在其他节点或未启动"
fi

echo ""
echo "📋 2. 检查 Nginx 状态..."
echo "----------------------------------------"
if docker ps | grep -q nginx-lb; then
    echo "✅ Nginx 容器运行中"
    docker exec nginx-lb nginx -t
    echo ""
    echo "Nginx 统计:"
    curl -s http://localhost/nginx_status 2>/dev/null || echo "⚠️  Nginx 状态页面不可用"
else
    echo "❌ Nginx 容器未运行"
fi

echo ""
echo "📋 3. 检查 HAProxy 状态..."
echo "----------------------------------------"
if docker ps | grep -q haproxy-lb; then
    echo "✅ HAProxy 容器运行中"
    echo ""
    echo "HAProxy 统计页面: http://localhost:8404/stats"
else
    echo "❌ HAProxy 容器未运行"
fi

echo ""
echo "📋 4. 测试负载均衡..."
echo "----------------------------------------"

# 测试健康检查
echo "测试健康检查端点..."
for i in {1..5}; do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://${VIRTUAL_IP}/health 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        echo "  请求 ${i}: ✅ 200 OK"
    else
        echo "  请求 ${i}: ❌ ${RESPONSE}"
    fi
    sleep 0.5
done

echo ""
echo "📋 5. 测试 API 端点..."
echo "----------------------------------------"
for i in {1..5}; do
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://${VIRTUAL_IP}/v1/ping 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        echo "  请求 ${i}: ✅ 200 OK"
    else
        echo "  请求 ${i}: ⚠️  ${RESPONSE}"
    fi
    sleep 0.5
done

echo ""
echo "📋 6. 测试 HTTPS..."
echo "----------------------------------------"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN}/health 2>/dev/null || echo "000")
if [ "$RESPONSE" == "200" ]; then
    echo "✅ HTTPS 连接成功"
else
    echo "⚠️  HTTPS 连接失败: ${RESPONSE}"
fi

echo ""
echo "📋 7. 检查后端服务器状态..."
echo "----------------------------------------"
echo "yyc3-33 (主节点):"
curl -s -o /dev/null -w "  状态码: %{http_code}\n" http://yyc3-33:8000/health 2>/dev/null || echo "  ❌ 连接失败"

echo ""
echo "yyc3-45 (备用节点):"
curl -s -o /dev/null -w "  状态码: %{http_code}\n" http://yyc3-45:8002/health 2>/dev/null || echo "  ❌ 连接失败"

echo ""
echo "📋 8. 性能测试..."
echo "----------------------------------------"
echo "并发测试（100 请求）..."
START=$(date +%s%N)
for i in {1..100}; do
    curl -s -o /dev/null http://${VIRTUAL_IP}/health &
done
wait
END=$(date +%s%N)
DURATION=$(( ($END - $START) / 1000000 ))
echo "✅ 100 请求完成，耗时: ${DURATION}ms"
echo "平均响应时间: $(( ${DURATION} / 100 ))ms"

echo ""
echo "========================================="
echo "✅ 验证完成"
echo "========================================="
echo ""
echo "负载均衡状态:"
echo "  虚拟 IP: ${VIRTUAL_IP}"
echo "  域名: ${DOMAIN}"
echo "  Nginx: $(docker ps | grep -c nginx-lb || echo 0) 个容器运行中"
echo "  HAProxy: $(docker ps | grep -c haproxy-lb || echo 0) 个容器运行中"
echo ""
