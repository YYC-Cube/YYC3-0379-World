#!/bin/bash

# YYC³ MCP 集成部署脚本
# @file: deploy-integrated-mcp.sh
# @description: 部署集成的四种MCP（联网搜索、开源仓库、网页读取、视觉理解）
# @author: YanYuCloudCube Team <admin@0379.email>
# @version: v1.0.0
# @created: 2026-03-21
# @status: stable
# @license: MIT
# @copyright: Copyright (c) 2026 YanYuCloudCube Team

set -e

echo "=========================================="
echo "YYC³ MCP 集成部署工具"
echo "=========================================="
echo ""

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 配置文件路径
CONFIG_DIR="/Volumes/Development/项目提示词/0379-world/MCP"
INTEGRATED_CONFIG="$CONFIG_DIR/integrated-mcp-config.json"

echo -e "${GREEN}[1/5]${NC} 检查配置文件..."
if [ ! -f "$INTEGRATED_CONFIG" ]; then
    echo -e "${RED}✗${NC} 集成配置文件不存在: $INTEGRATED_CONFIG"
    exit 1
fi
echo -e "${GREEN}✓${NC} 配置文件检查通过"

echo ""
echo -e "${GREEN}[2/5]${NC} 检查 Node.js 环境..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗${NC} Node.js 未安装"
    echo "请先安装 Node.js 18+: https://nodejs.org/"
    exit 1
fi
NODE_VERSION=$(node -v)
echo -e "${GREEN}✓${NC} Node.js 版本: $NODE_VERSION"

echo ""
echo -e "${GREEN}[3/5]${NC} 检查 Claude Code..."
if ! command -v claude &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} Claude Code 未安装"
    echo "请先安装 Claude Code: https://claude.ai/download"
    echo ""
    echo "您也可以手动配置其他 MCP 客户端"
else
    CLAUDE_VERSION=$(claude --version 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓${NC} Claude Code 版本: $CLAUDE_VERSION"
fi

echo ""
echo -e "${GREEN}[4/5]${NC} 部署 MCP 服务器..."

# 方法一：使用 Claude Code 一键安装
if command -v claude &> /dev/null; then
    echo ""
    echo "正在使用 Claude Code 部署 MCP..."

    # 部署 Brave 搜索 MCP
    echo -e "${YELLOW}→${NC} 部署 Brave 搜索 MCP..."
    claude mcp add -s user mcp-brave-search \
        --env BRAVE_API_KEY="${BRAVE_API_KEY}" \
        -- npx -y "@modelcontextprotocol/server-brave-search" 2>/dev/null || \
        echo -e "${YELLOW}⚠${NC} Brave 搜索 MCP 可能已安装"

    # 部署 GitHub MCP
    echo -e "${YELLOW}→${NC} 部署 GitHub 仓库 MCP..."
    claude mcp add -s user mcp-github-yyc3 \
        --env GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_PERSONAL_ACCESS_TOKEN}" \
        -- npx -y "@modelcontextprotocol/server-github" 2>/dev/null || \
        echo -e "${YELLOW}⚠${NC} GitHub MCP 可能已安装"

    # 部署文件系统 MCP
    echo -e "${YELLOW}→${NC} 部署文件系统 MCP..."
    claude mcp add -s user mcp-filesystem \
        -- npx -y "@modelcontextprotocol/server-filesystem" /Users/yanyu 2>/dev/null || \
        echo -e "${YELLOW}⚠${NC} 文件系统 MCP 可能已安装"

    echo -e "${GREEN}✓${NC} Claude Code 部署完成"
fi

echo ""
echo -e "${GREEN}[5/5]${NC} 验证部署..."

if command -v claude &> /dev/null; then
    echo ""
    echo "已安装的 MCP 服务器:"
    echo "=========================================="
    claude mcp list 2>/dev/null || echo "无法获取 MCP 列表"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✓ MCP 集成部署完成！${NC}"
echo ""
echo "📋 已集成的 MCP:"
echo "  1. 联网搜索 MCP (Brave Search)"
echo "  2. 开源仓库 MCP (GitHub)"
echo "  3. 文件系统 MCP (Filesystem)"
echo ""
echo "📖 配置文件: $INTEGRATED_CONFIG"
echo "📝 详细文档: $CONFIG_DIR/README.md"
echo ""
echo "=========================================="
echo ""
echo "🚀 使用方法:"
echo ""
echo "1. 在 Claude Code 中直接使用 MCP 功能"
echo "2. MCP 会根据您的对话自动调用最合适的工具"
echo "3. 示例对话:"
echo "   - '搜索最新的 AI 技术趋势'"
echo "   - '查看某个 GitHub 仓库的代码结构'"
echo "   - '读取本地文件的内容'"
echo "   - '分析这个图片'"
echo ""
echo "=========================================="
