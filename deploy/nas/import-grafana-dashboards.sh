#!/bin/bash
# =============================================================================
# @file: import-grafana-dashboards.sh
# @description: 管理机一键导入 Grafana 看板（05 Runbook §2.4 看板/告警）
#               含 Loki 数据源幂等补建（uid=loki，panel 引用依赖）
# @usage:   管理机（yyc3-22，Tailscale 可达 Grafana）执行：
#             bash deploy/nas/import-grafana-dashboards.sh                          # 默认导入 dgx-container-logs.json
#             bash deploy/nas/import-grafana-dashboards.sh path/to/board.json ...   # 指定看板
#           可覆盖：GRAFANA_HOST（默认 http://100.65.172.88:3000）
#                   GRAFANA_ADMIN_PASSWORD（默认经 ssh yyc3-45 从生产 .env 读取，不回显）
# @note:    幂等（overwrite:true 重复导入 = 版本+1）；bash 3.2 兼容；密码不落盘不回显
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DASHBOARDS_DIR="$REPO_ROOT/core/config/grafana/dashboards"
GRAFANA_HOST="${GRAFANA_HOST:-http://100.65.172.88:3000}"

BOARDS=("$@")
[ ${#BOARDS[@]} -eq 0 ] && BOARDS=("$DASHBOARDS_DIR/dgx-container-logs.json")

log() { echo "[$(date +%H:%M:%S)] $*"; }

# 1. 密码（环境变量优先；否则经 SSH 从 NAS 生产 .env 读取）
if [ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]; then
  log "从 NAS yyc3-45 读取 GRAFANA_ADMIN_PASSWORD（不回显）..."
  GRAFANA_ADMIN_PASSWORD=$(ssh -o BatchMode=yes -o ConnectTimeout=10 yyc3-45 \
    'grep "^GRAFANA_ADMIN_PASSWORD=" /Volume2/yyc3-33/.env | cut -d= -f2-') || {
    echo "❌ 密码读取失败（检查 ssh yyc3-45 或手动 export GRAFANA_ADMIN_PASSWORD）"; exit 2; }
fi
AUTH="admin:$GRAFANA_ADMIN_PASSWORD"

# 2. Loki 数据源幂等补建（dgx 日志看板 panel 依赖 uid=loki）
log "Loki 数据源检查/补建（uid=loki → yyc3-loki:3100）..."
DS_RESP=$(curl -s -m 10 -u "$AUTH" -X POST "$GRAFANA_HOST/api/datasources" \
  -H "Content-Type: application/json" \
  -d '{"name":"Loki","type":"loki","uid":"loki","url":"http://yyc3-loki:3100","access":"proxy","isDefault":false}')
echo "$DS_RESP" | grep -q '"uid":"loki"' && log "✓ Loki 数据源已就绪" \
  || { echo "$DS_RESP" | grep -qi "already exist" && log "✓ Loki 数据源已存在" \
       || { log "❌ Loki 数据源创建异常: $(echo "$DS_RESP" | head -c 150)"; exit 2; }; }

# 3. 逐个导入（shell 拼 wrap：{"dashboard":<文件>,"overwrite":true}——无需 python）
FAIL=0
for BOARD in "${BOARDS[@]}"; do
  [ -f "$BOARD" ] || { log "❌ 看板文件不存在: $BOARD"; FAIL=$((FAIL+1)); continue; }
  NAME=$(basename "$BOARD")
  WRAP="/tmp/.grafana_import_$$.json"
  { printf '{"dashboard":'; cat "$BOARD"; printf ',"overwrite":true,"message":"imported %s"}' "$(date +%FT%T)"; } > "$WRAP"
  RESP=$(curl -s -m 15 -u "$AUTH" -X POST "$GRAFANA_HOST/api/dashboards/db" \
    -H "Content-Type: application/json" -d @"$WRAP")
  rm -f "$WRAP"
  UID_OUT=$(echo "$RESP" | grep -o '"uid":"[^"]*"' | cut -d'"' -f4)
  STATUS=$(echo "$RESP" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
  if [ -n "$UID_OUT" ] && [ "$STATUS" = "success" ]; then
    log "✅ $NAME → uid=$UID_OUT  $GRAFANA_HOST/d/$UID_OUT"
  else
    log "❌ $NAME 导入失败: $(echo "$RESP" | head -c 180)"
    FAIL=$((FAIL+1))
  fi
done

# 4. 汇总
[ "$FAIL" -eq 0 ] && log "✅ 全部看板导入成功（$GRAFANA_HOST/dashboards）" || log "❌ $FAIL 个看板失败"
exit "$FAIL"
