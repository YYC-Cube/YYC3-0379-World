#!/bin/bash

set -e

echo "========================================="
echo "YYC³ E2E 测试执行脚本"
echo "========================================="

BASE_URL=${1:-"https://api.0379.world"}
API_KEY=${2:-${API_KEY:?must_provide_API_KEY}}
TEST_TYPE=${3:-"all"}

TESTS_DIR="tests/e2e"
REPORTS_DIR="tests/e2e/reports"

echo ""
echo "📋 测试配置:"
echo "  目标 URL: ${BASE_URL}"
echo "  测试类型: ${TEST_TYPE}"
echo "  报告目录: ${REPORTS_DIR}"
echo ""

echo "📋 步骤 1/5: 准备测试环境..."
mkdir -p ${REPORTS_DIR}/playwright
mkdir -p ${REPORTS_DIR}/cypress
echo "✅ 测试环境准备完成"

echo ""
echo "📋 步骤 2/5: 检查依赖..."
cd ${TESTS_DIR}

if [ ! -d "node_modules" ]; then
    echo "安装依赖..."
    npm install
fi

if ! command -v npx &> /dev/null; then
    echo "❌ npx 未安装"
    exit 1
fi
echo "✅ 依赖检查完成"

echo ""
echo "📋 步骤 3/5: 执行 Playwright 测试..."
echo "----------------------------------------"

export BASE_URL=${BASE_URL}
export API_KEY=${API_KEY}

case $TEST_TYPE in
    "smoke")
        echo "执行烟雾测试..."
        npx playwright test tests/smoke
        ;;
    "regression")
        echo "执行回归测试..."
        npx playwright test tests/regression
        ;;
    "e2e")
        echo "执行 E2E 测试..."
        npx playwright test tests/e2e
        ;;
    "all")
        echo "执行所有测试..."
        npx playwright test
        ;;
    *)
        echo "❌ 未知的测试类型: ${TEST_TYPE}"
        echo "可用类型: smoke, regression, e2e, all"
        exit 1
        ;;
esac

echo "✅ Playwright 测试完成"

echo ""
echo "📋 步骤 4/5: 执行 Cypress 测试..."
echo "----------------------------------------"

npx cypress run \
    --config baseUrl=${BASE_URL} \
    --env API_KEY=${API_KEY} \
    --reporter mochawesome \
    --reporter-options reportDir=${REPORTS_DIR}/cypress,overwrite=false,html=true,json=true

echo "✅ Cypress 测试完成"

echo ""
echo "📋 步骤 5/5: 生成测试报告..."
echo "----------------------------------------"

# 合并测试结果
cat << EOF > ${REPORTS_DIR}/test-summary.md
# YYC³ E2E 测试报告

**测试时间**: $(date '+%Y-%m-%d %H:%M:%S')
**测试类型**: ${TEST_TYPE}
**目标 URL**: ${BASE_URL}

## 测试结果

### Playwright 测试结果
- HTML 报告: ${REPORTS_DIR}/playwright/index.html
- JSON 结果: ${REPORTS_DIR}/playwright/results.json
- JUnit XML: ${REPORTS_DIR}/playwright/junit.xml

### Cypress 测试结果
- HTML 报告: ${REPORTS_DIR}/cypress/mochawesome.html
- JSON 结果: ${REPORTS_DIR}/cypress/mochawesome.json

## 下一步

1. 查看测试报告: open ${REPORTS_DIR}/playwright/index.html
2. 分析失败用例: 查看报告中的失败详情
3. 修复问题: 根据测试结果修复代码
EOF

echo "✅ 测试报告生成完成"

cd -

echo ""
echo "========================================="
echo "✅ E2E 测试完成"
echo "========================================="
echo ""
echo "测试结果:"
echo "  Playwright 报告: ${REPORTS_DIR}/playwright/index.html"
echo "  Cypress 报告: ${REPORTS_DIR}/cypress/mochawesome.html"
echo "  测试摘要: ${REPORTS_DIR}/test-summary.md"
echo ""
echo "查看报告:"
echo "  open ${REPORTS_DIR}/playwright/index.html"
echo "  open ${REPORTS_DIR}/cypress/mochawesome.html"
echo ""
