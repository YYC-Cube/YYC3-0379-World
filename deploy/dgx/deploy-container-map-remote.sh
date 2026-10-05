#!/bin/bash
# =============================================================================
# @file: deploy-container-map-remote.sh
# @description: 管理机一键远程部署 · 容器日志外送 + 容器名映射（05 Runbook §2.4）
#               批量节点：同步 deploy/dgx/ 七件套 → 远程执行 setup-container-map.sh
# @usage:   管理机（yyc3-22）仓库根目录执行：
#             bash deploy/dgx/deploy-container-map-remote.sh                # 默认 yyc3-n1 yyc3-n2
#             bash deploy/dgx/deploy-container-map-remote.sh yyc3-n1       # 指定节点（ssh config Host 名）
#             NODE_ID=yyc3-102 bash deploy/dgx/deploy-container-map-remote.sh yyc3-n2   # 覆盖 NODE_ID 探测
# @deps:    管理机 ~/.ssh/config 已含目标节点条目（BatchMode 免密）；目标节点满足 setup-container-map.sh deps
# @note:    幂等；任一节点失败则脚本以非零退出（失败清单见汇总）
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES=(setup-container-map.sh fluent-bit.conf cn.lua container-map.sh container-map.service container-map.timer docker-compose.logging.yml)
LOG_DIR_REMOTE="/home/yyc3/logging"
NODES=("$@")
[ ${#NODES[@]} -eq 0 ] && NODES=(yyc3-n1 yyc3-n2)

SSH="ssh -o BatchMode=yes -o ConnectTimeout=10"
SCP="scp -q -o BatchMode=yes -o ConnectTimeout=10"

RESULT_NODES=()
RESULT_VALUES=()
FAILED=()

log() { echo "[$(date +%H:%M:%S)] $*"; }
record() { RESULT_NODES+=("$1"); RESULT_VALUES+=("$2"); }

for NODE in "${NODES[@]}"; do
  log "── $NODE ──"
  # 1. 前置：连通性 + 远端目录
  if ! $SSH "$NODE" "mkdir -p $LOG_DIR_REMOTE" 2>/dev/null; then
    log "❌ $NODE: SSH 不可达或目录创建失败"; record "$NODE" "unreachable"; FAILED+=("$NODE"); continue
  fi
  # 2. 同步部署文件（脚本自身 + 六件套）
  SYNC_FAIL=0
  for f in "${FILES[@]}"; do
    [ -f "$SCRIPT_DIR/$f" ] || { log "❌ 管理机缺文件: deploy/dgx/$f"; SYNC_FAIL=1; break; }
    $SCP "$SCRIPT_DIR/$f" "$NODE:$LOG_DIR_REMOTE/$f" || SYNC_FAIL=1
  done
  [ "$SYNC_FAIL" -ne 0 ] && { log "❌ $NODE: 文件同步失败"; record "$NODE" "sync-failed"; FAILED+=("$NODE"); continue; }
  # 3. 远程执行安装（NODE_ID 环境变量透传：未设置则远端 hostname 自动探测）
  if OUT=$($SSH "$NODE" "NODE_ID='${NODE_ID:-}' bash $LOG_DIR_REMOTE/setup-container-map.sh" 2>&1); then
    log "$OUT" | sed 's/^/    /'
    record "$NODE" "✅"
  else
    log "$OUT" | sed 's/^/    /'
    log "❌ $NODE: 远程安装失败"; record "$NODE" "setup-failed"; FAILED+=("$NODE")
  fi
done

# 汇总
log "═══ 部署汇总 ═══"
for i in "${!RESULT_NODES[@]}"; do
  printf "  %-12s %s\n" "${RESULT_NODES[$i]}" "${RESULT_VALUES[$i]}"
done
[ ${#FAILED[@]} -eq 0 ] && log "✅ 全部节点部署成功" || log "❌ 失败节点: ${FAILED[*]}"
exit ${#FAILED[@]}
