#!/bin/bash
# =============================================================================
# @file: canary-manage.sh
# @description: Canary 灰度全生命周期封装（管理机 → NAS Registry 三端点）
#               03 §4-§5 半自动闭环：set → promote 扩量 → rollback 回退 → finalize 正式切换
# @usage:   bash scripts/canary-manage.sh status   <model>                         # 查看灰度态
#           bash scripts/canary-manage.sh set      <model> <canary_id> <weight> [shadow]
#           bash scripts/canary-manage.sh promote  <model> <weight>              # 扩量
#           bash scripts/canary-manage.sh rollback <model>                      # 紧急回退（weight=0）
#           bash scripts/canary-manage.sh finalize <model>                      # 正式切换：alias PUT + DELETE canary
#           bash scripts/canary-manage.sh delete   <model>
# @note:    alias = 客户端调用的 model 名；经 Tailscale 直连 NAS :8000（100.65.172.88）；
#           ADMIN key 经 SSH 从 NAS .env 读取不落盘；bash 3.2 兼容
# =============================================================================
set -uo pipefail

TS_IP="${TS_IP:-100.65.172.88}"   # NAS Tailscale IP（gateway :8000 绑定于此）
GW="${GW_URL:-http://$TS_IP:8000}"
CMD="${1:-}"; shift || true

log() { echo "[$(date +%H:%M:%S)] $*"; }

get_key() {
  KEY=$(ssh -o BatchMode=yes -o ConnectTimeout=10 yyc3-45 \
    "grep '^ADMIN_API_KEYS=' /Volume2/yyc3-33/.env | cut -d= -f2- | tr -d '\"' | cut -d, -f1") \
    && [ -n "$KEY" ] || { echo "❌ ADMIN_API_KEYS 读取失败"; exit 2; }
}

api() { # api METHOD PATH [JSON] → 输出 body
  local M=$1 P=$2 B=${3:-}
  if [ -n "$B" ]; then
    curl -s -m 10 -X "$M" "$GW$P" -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d "$B"
  else
    curl -s -m 10 -X "$M" "$GW$P" -H "X-API-Key: $KEY"
  fi
}

field() { echo "$1" | grep -oE "\"$2\":\"[^\"]*\"" | cut -d'"' -f4; }

# 参数防护（Q-1 整改，2026-10-05 终审）：缺参打印用法并 exit 2，禁 unbound 裸奔
usage() { grep '^# @usage' -A 8 "$0" | sed 's/^# //'; }
need() { [ -n "${1:-}" ] || { echo "❌ 缺少参数，期望：$2" >&2; usage >&2; exit 2; }; }

get_key
case "$CMD" in
  status)
    need "${1:-}" "status <model>"
    R=$(api GET "/registry/v1/canary/$1")
    echo "$R" | grep -q canary_not_found && { echo "（无灰度配置）"; exit 0; }
    echo "  baseline: $(field "$R" baseline)"
    echo "  canary  : $(field "$R" canary)"
    echo "  weight  : $(field "$R" weight)"
    echo "  shadow  : $(field "$R" shadow)"
    echo "  started : $(field "$R" started_at)"
    ;;
  set)
    need "${1:-}" "set <model> <canary_id> <weight> [shadow]"
    M=$1; CANARY=$2; W=$3; SHADOW=${4:-}
    need "${CANARY:-}" "set <model> <canary_id> <weight> [shadow]"
    need "${W:-}" "set <model> <canary_id> <weight> [shadow]"
    BODY="{\"baseline\":\"$M\",\"canary\":\"$CANARY\",\"weight\":$W"
    [ -n "$SHADOW" ] && BODY="$BODY,\"shadow\":\"$SHADOW\""
    BODY="$BODY}"
    log "⚡ canary set: alias=$M canary=$CANARY weight=$W${SHADOW:+ shadow=$SHADOW}"
    api PUT "/registry/v1/canary/$M" "$BODY"
    ;;
  promote)
    need "${1:-}" "promote <model> <weight>"
    M=$1; W=$2
    need "${W:-}" "promote <model> <weight>"
    CUR=$(api GET "/registry/v1/canary/$M")
    B=$(field "$CUR" baseline); C=$(field "$CUR" canary)
    [ -z "$B" ] && { echo "❌ 无灰度配置，先 set"; exit 1; }
    log "⚡ canary promote: alias=$M → weight=$W（观察 yyc3_backend_requests_total / yyc3_backend_ttft_seconds）"
    api PUT "/registry/v1/canary/$M" "{\"baseline\":\"$B\",\"canary\":\"$C\",\"weight\":$W}"
    ;;
  rollback)
    need "${1:-}" "rollback <model>"
    M=$1
    CUR=$(api GET "/registry/v1/canary/$M")
    B=$(field "$CUR" baseline); C=$(field "$CUR" canary)
    log "⚡ canary 紧急回退: weight→0（全量回 baseline $B）"
    api PUT "/registry/v1/canary/$M" "{\"baseline\":\"$B\",\"canary\":\"$C\",\"weight\":0}"
    ;;
  finalize)
    need "${1:-}" "finalize <model>"
    M=$1
    CUR=$(api GET "/registry/v1/canary/$M")
    C=$(field "$CUR" canary)
    [ -z "$C" ] && { echo "❌ 无灰度配置"; exit 1; }
    log "⚡ finalize: alias $M → $C（公网名正式切换）+ DELETE canary"
    api PUT "/registry/v1/aliases/$M" "{\"model_id\":\"$C\",\"reason\":\"canary finalize\"}"
    api DELETE "/registry/v1/canary/$M"
    ;;
  delete)
    need "${1:-}" "delete <model>"
    api DELETE "/registry/v1/canary/$1"
    ;;
  *) usage; exit 2 ;;
esac
