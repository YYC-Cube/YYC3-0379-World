#!/bin/bash

set -e

echo "========================================="
echo "YYC³ 性能测试执行脚本"
echo "========================================="

BASE_URL=${1:-"https://api.0379.world"}
API_KEY=${2:-${API_KEY:?must_provide_API_KEY}}
TEST_TYPE=${3:-"load"}

RESULTS_DIR="tests/performance/results"
LOGS_DIR="tests/performance/logs"

echo ""
echo "📋 测试配置:"
echo "  目标 URL: ${BASE_URL}"
echo "  测试类型: ${TEST_TYPE}"
echo "  结果目录: ${RESULTS_DIR}"
echo ""

echo "📋 步骤 1/5: 准备测试环境..."
mkdir -p ${RESULTS_DIR}
mkdir -p ${LOGS_DIR}
echo "✅ 测试环境准备完成"

echo ""
echo "📋 步骤 2/5: 检查依赖..."
if ! command -v k6 &> /dev/null; then
    echo "❌ k6 未安装"
    echo "安装命令: brew install k6"
    exit 1
fi

if ! command -v locust &> /dev/null; then
    echo "❌ Locust 未安装"
    echo "安装命令: pip install locust"
    exit 1
fi
echo "✅ 依赖检查完成"

echo ""
echo "📋 步骤 3/5: 执行 k6 性能测试..."
echo "----------------------------------------"

case $TEST_TYPE in
    "smoke")
        echo "执行烟雾测试..."
        k6 run \
            --vus 10 \
            --duration 5m \
            --out json=${RESULTS_DIR}/k6-smoke.json \
            tests/performance/load-test.js
        ;;
    "load")
        echo "执行负载测试..."
        k6 run \
            --vus 100 \
            --duration 10m \
            --out json=${RESULTS_DIR}/k6-load.json \
            tests/performance/load-test.js
        ;;
    "stress")
        echo "执行压力测试..."
        k6 run \
            --vus 300 \
            --duration 15m \
            --out json=${RESULTS_DIR}/k6-stress.json \
            tests/performance/load-test.js
        ;;
    "comprehensive")
        echo "执行综合测试..."
        BASE_URL=${BASE_URL} API_KEY=${API_KEY} k6 run \
            --out json=${RESULTS_DIR}/k6-comprehensive.json \
            tests/performance/comprehensive-test.js
        ;;
    *)
        echo "❌ 未知的测试类型: ${TEST_TYPE}"
        echo "可用类型: smoke, load, stress, comprehensive"
        exit 1
        ;;
esac

echo "✅ k6 测试完成"

echo ""
echo "📋 步骤 4/5: 执行 Locust 性能测试..."
echo "----------------------------------------"

cd tests/performance

locust \
    -f locust_test.py \
    --host ${BASE_URL} \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless \
    --html ${RESULTS_DIR}/locust-report.html \
    --csv ${RESULTS_DIR}/locust-results \
    --logfile ${LOGS_DIR}/locust.log

cd -

echo "✅ Locust 测试完成"

echo ""
echo "📋 步骤 5/5: 生成测试报告..."
echo "----------------------------------------"

# 合并测试结果
cat << EOF > ${RESULTS_DIR}/test-summary.md
# YYC³ 性能测试报告

**测试时间**: $(date '+%Y-%m-%d %H:%M:%S')
**测试类型**: ${TEST_TYPE}
**目标 URL**: ${BASE_URL}

## 测试结果

### k6 测试结果
- 结果文件: ${RESULTS_DIR}/k6-${TEST_TYPE}.json
- HTML 报告: ${RESULTS_DIR}/report.html

### Locust 测试结果
- HTML 报告: ${RESULTS_DIR}/locust-report.html
- CSV 数据: ${RESULTS_DIR}/locust-results_*.csv
- 日志文件: ${LOGS_DIR}/locust.log

## 下一步

1. 查看测试报告: open ${RESULTS_DIR}/report.html
2. 分析性能数据: 查看 ${RESULTS_DIR}/k6-${TEST_TYPE}.json
3. 优化性能瓶颈: 根据测试结果优化系统
EOF

echo "✅ 测试报告生成完成"

echo ""
echo "========================================="
echo "✅ 性能测试完成"
echo "========================================="
echo ""
echo "测试结果:"
echo "  k6 报告: ${RESULTS_DIR}/report.html"
echo "  Locust 报告: ${RESULTS_DIR}/locust-report.html"
echo "  测试摘要: ${RESULTS_DIR}/test-summary.md"
echo ""
echo "查看报告:"
echo "  open ${RESULTS_DIR}/report.html"
echo "  open ${RESULTS_DIR}/locust-report.html"
echo ""
