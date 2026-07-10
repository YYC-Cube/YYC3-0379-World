#!/bin/bash

# YYC³ 项目清理脚本
# 清理临时文件和检查脚本

PROJECT_ROOT="/Volumes/Development/项目提示词/0379-world"

echo "=========================================="
echo "YYC³ 项目清理"
echo "=========================================="
echo ""

# 删除临时文件
echo "删除临时文件..."
rm -f "$PROJECT_ROOT/compliance-report.md"
rm -f "$PROJECT_ROOT/check-compliance.sh"
rm -f "$PROJECT_ROOT/fix-compliance.sh"
rm -f "$PROJECT_ROOT/core/config/.env.0379-world/README-FIXED.md"

# 删除检查脚本（保留有用的工具）
# 如果需要保留这些工具，可以注释掉以下行
# rm -f "$PROJECT_ROOT/check_code_compliance.py"
# rm -f "$PROJECT_ROOT/check_naming_convention.py"
# rm -f "$PROJECT_ROOT/check_directory_structure.py"
# rm -f "$PROJECT_ROOT/fix_documentation.py"
# rm -f "$PROJECT_ROOT/fix_code_headers.py"

echo "✅ 清理完成"
echo ""

# 显示项目结构
echo "=========================================="
echo "项目最终结构"
echo "=========================================="
echo ""

tree -L 2 -I '__pycache__|*.pyc|node_modules' "$PROJECT_ROOT" 2>/dev/null || find "$PROJECT_ROOT" -maxdepth 2 -type d | head -20

echo ""
echo "=========================================="
echo "✅ 项目清理和合规性统一完成"
echo "=========================================="
echo ""
echo "📊 合规性报告: $PROJECT_ROOT/COMPLIANCE_REPORT.md"
echo "📖 项目说明: $PROJECT_ROOT/README.md"
echo ""
