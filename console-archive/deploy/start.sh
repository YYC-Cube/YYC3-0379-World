#!/bin/bash
# ============================================================
# YYC³ CloudPivot Intelli-Matrix — 一键部署脚本
# ============================================================
#
# 用法:
#   chmod +x deploy/start.sh
#   ./deploy/start.sh
#
# 前提:
#   - Node.js >= 18
#   - pnpm (或 npm)
#   - Ollama 已运行 (ollama serve)
#
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo ""
echo "  ╔════════════════════════════════════════════════════╗"
echo "  ║  YYC³ CloudPivot Intelli-Matrix · Deploy Script   ║"
echo "  ╚════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: 检查 Node.js ──
if ! command -v node &> /dev/null; then
  echo "  ❌ Node.js 未安装。请先安装 Node.js >= 18"
  echo "     brew install node"
  exit 1
fi
echo "  ✅ Node.js $(node -v)"

# ── Step 2: 检查 Ollama ──
if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
  MODEL_COUNT=$(curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "?")
  echo "  ✅ Ollama 运行中 ($MODEL_COUNT 个模型)"
else
  echo "  ⚠️  Ollama 未运行。启动后 Dashboard 的 AI 功能才可用"
  echo "     运行: ollama serve"
fi

# ── Step 3: 安装依赖 ──
if [ ! -d "node_modules" ]; then
  echo ""
  echo "  📦 安装依赖..."
  if command -v pnpm &> /dev/null; then
    pnpm install
  else
    npm install
  fi
fi

# ── Step 4: 构建 ──
echo ""
echo "  🔨 构建生产版本..."
if command -v pnpm &> /dev/null; then
  pnpm build
else
  npm run build
fi

# ── Step 5: 检查构建产物 ──
if [ ! -f "dist/index.html" ]; then
  echo "  ❌ 构建失败: dist/index.html 不存在"
  exit 1
fi

DIST_SIZE=$(du -sh dist | cut -f1)
echo "  ✅ 构建完成 (dist/ $DIST_SIZE)"

# ── Step 6: 启动服务器 ──
echo ""
echo "  🚀 启动本地服务器..."
echo ""

node deploy/server.mjs
