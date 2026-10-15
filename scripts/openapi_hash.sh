#!/usr/bin/env bash
# openapi_hash.sh — 契约冻结哈希回填工具（双端联通 R6 / 冻结快照 v5.2 转正流程）
# 用法: ./scripts/openapi_hash.sh [base_url]   （默认生产网关）
# 输出: sha256 + 端点数, 回填 Token-Console docs 模型网关/开发推进/01 第一部分冻结哈希行
set -euo pipefail
BASE="${1:-https://api.0379.world}"
SPEC_URL="$BASE/openapi.json"

HASH=$(curl -fsS --max-time 15 "$SPEC_URL" | shasum -a 256 | cut -d' ' -f1)
COUNT=$(curl -fsS --max-time 15 "$SPEC_URL" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['paths']))")

echo "base     : $BASE"
echo "sha256   : $HASH"
echo "endpoints: $COUNT"
echo "---"
echo "回填: 模型网关/开发推进/01 第一部分 → 契约冻结哈希行 + 增补端点行 🔓→🔒"
