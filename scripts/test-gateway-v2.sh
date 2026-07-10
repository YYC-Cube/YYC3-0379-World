#!/bin/bash

# @file test-gateway-v2.sh
# @description Gateway v2.0.0 功能测试脚本
# @author YanYuCloudCube Team <admin@0379.email>
# @version v1.0.0
# @created 2026-04-08
# @updated 2026-04-08
# @status stable
# @license MIT

set -e

BASE_URL="${BASE_URL:-https://api.0379.world}"
API_KEY="${API_KEY:?must_set_API_KEY}"

echo "=========================================="
echo "YYC³ Gateway v2.0.0 功能测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试函数
test_api() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    
    echo -n "测试: $test_name ... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" \
            -H "X-API-Key: $API_KEY" \
            "${BASE_URL}${endpoint}")
    else
        response=$(curl -s -w "\n%{http_code}" \
            -X POST \
            -H "Content-Type: application/json" \
            -H "X-API-Key: $API_KEY" \
            -d "$data" \
            "${BASE_URL}${endpoint}")
    fi
    
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✓ 通过${NC} (HTTP $http_code)"
        return 0
    else
        echo -e "${RED}✗ 失败${NC} (HTTP $http_code)"
        echo "响应: $body"
        return 1
    fi
}

# 测试计数器
total_tests=0
passed_tests=0

# 1. 健康检查测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. 健康检查测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

((total_tests++))
if test_api "健康检查" "GET" "/health"; then
    ((passed_tests++))
fi

echo ""

# 2. 模型列表测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. 模型列表测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

((total_tests++))
if test_api "获取模型列表" "GET" "/v1/models"; then
    ((passed_tests++))
fi

echo ""

# 3. 聊天接口测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. 聊天接口测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 测试智谱GLM
((total_tests++))
if test_api "智谱GLM聊天" "POST" "/v1/chat/completions" \
    '{"model":"glm-4-flash","messages":[{"role":"user","content":"你好"}]}'; then
    ((passed_tests++))
fi

# 测试Ollama
((total_tests++))
if test_api "Ollama聊天" "POST" "/v1/chat/completions" \
    '{"model":"llama3.2","messages":[{"role":"user","content":"你好"}]}'; then
    ((passed_tests++))
fi

echo ""

# 4. 认证测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. 认证测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 测试无认证
((total_tests++))
echo -n "测试: 无认证访问 ... "
response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/v1/models")
http_code=$(echo "$response" | tail -n 1)
if [ "$http_code" -eq 401 ]; then
    echo -e "${GREEN}✓ 通过${NC} (正确返回401)"
    ((passed_tests++))
else
    echo -e "${RED}✗ 失败${NC} (HTTP $http_code, 应该返回401)"
fi

# 测试错误认证
((total_tests++))
echo -n "测试: 错误认证 ... "
response=$(curl -s -w "\n%{http_code}" \
    -H "X-API-Key: invalid_key" \
    "${BASE_URL}/v1/models")
http_code=$(echo "$response" | tail -n 1)
if [ "$http_code" -eq 403 ]; then
    echo -e "${GREEN}✓ 通过${NC} (正确返回403)"
    ((passed_tests++))
else
    echo -e "${RED}✗ 失败${NC} (HTTP $http_code, 应该返回403)"
fi

echo ""

# 5. 监控指标测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. 监控指标测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

((total_tests++))
if test_api "Prometheus指标" "GET" "/metrics"; then
    ((passed_tests++))
fi

echo ""

# 6. API文档测试
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. API文档测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

((total_tests++))
if test_api "Swagger文档" "GET" "/docs"; then
    ((passed_tests++))
fi

((total_tests++))
if test_api "ReDoc文档" "GET" "/redoc"; then
    ((passed_tests++))
fi

echo ""

# 测试总结
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo -e "总测试数: $total_tests"
echo -e "通过: ${GREEN}$passed_tests${NC}"
echo -e "失败: ${RED}$((total_tests - passed_tests))${NC}"

if [ $passed_tests -eq $total_tests ]; then
    echo -e "\n${GREEN}✓ 所有测试通过！${NC}"
    exit 0
else
    echo -e "\n${RED}✗ 部分测试失败${NC}"
    exit 1
fi
