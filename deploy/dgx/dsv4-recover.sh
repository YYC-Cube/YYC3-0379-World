#!/bin/bash
# =============================================================================
# @file: dsv4-recover.sh
# @description: dsv4 旗舰 TP2 跨机 · 诊断/恢复/取证/守护 剧本（管理机执行）
#               事故复盘：2026-10-05 六天心跳停滞（三层根因见资产文档 v1.4.0）
# @usage:   bash deploy/dgx/dsv4-recover.sh check            # 只读诊断（安全，随时可跑）
#           bash deploy/dgx/dsv4-recover.sh recover          # 编排时序恢复（需维护窗口；已健康则跳过，--force 强制）
#           bash deploy/dgx/dsv4-recover.sh rootcause        # 崩溃取证（日志错误段/显存/Ray/RestartCount 轨迹）
#           bash deploy/dgx/dsv4-recover.sh logs [head|worker] [N]   # 快捷日志 tail（默认 head 30）
#           bash deploy/dgx/dsv4-recover.sh watch [间隔秒=300]        # 守护循环：异常自动 recover（≤3 次）
# @deps:    管理机 ssh 免密 yyc3-n1/yyc3-n2/yyc3-45；recover 会产生 <1min 双节点中断
# =============================================================================
set -uo pipefail

N1="${N1:-yyc3-n1}"
N2="${N2:-yyc3-n2}"
GW="${GW:-yyc3-45}"
MODE="${1:-check}"   # 无参数默认 check（安全只读）
[ $# -gt 0 ] && shift # 弹出模式名，余参传递给子命令

log() { echo "[$(date +%H:%M:%S)] $*"; }
sh1() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$N1" "$1" 2>/dev/null; }
sh2() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$N2" "$1" 2>/dev/null; }

do_check() {
  log "── dsv4 只读诊断 ──"
  C1=$(sh1 "docker inspect dsv4-head --format '{{.State.Status}} RestartCount={{.RestartCount}}' 2>/dev/null" || echo "not-found")
  C2=$(sh2 "docker inspect dsv4-worker --format '{{.State.Status}} RP={{.HostConfig.RestartPolicy.Name}}' 2>/dev/null" || echo "not-found")
  H=$(sh1 "curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8001/health" || echo 000)
  ST=$(ssh -o BatchMode=yes "$GW" "bash -lc 'cd /Volume2/yyc3-33 && KEY=\$(grep ^ADMIN_API_KEYS= .env | cut -d= -f2- | tr -d \\\" | cut -d, -f1); curl -s -m 5 -H \"X-API-Key: \$KEY\" http://127.0.0.1:8000/registry/v1/models/deepseek-v4-flash'" 2>/dev/null \
    | grep -oE '"state":"[a-z]+"' | head -1)
  log "head : ${C1}（RestartCount 为容器生命周期累计，恢复操作也会 +1）"
  log "worker: $C2"
  log "8001  : $H"
  log "registry: ${ST}（state=ready 即心跳 TTL 内，服务端权威判定）"
  # 健康判据 = 实例就绪 + Registry ready（TTL 内心跳）；RestartCount 仅展示不作判据
  if [ "$H" = "200" ] && echo "$ST" | grep -q '"state":"ready"'; then
    log "✅ 健康"
    return 0
  fi
  log "⚠️ 异常 → bash $0 recover"
  return 1
}

do_recover() {
  # 健康则跳过（--force 强制）
  if ! [ "${FORCE:-0}" = "1" ] && do_check; then
    log "当前健康，跳过恢复（FORCE=1 可强制）"
    return 0
  fi
  log "── dsv4 编排时序恢复（中断 <1min）──"
  log "① head 停"
  sh1 "docker stop dsv4-head" >/dev/null
  log "② worker 清态起"
  sh2 "docker restart dsv4-worker" >/dev/null
  sleep 10
  log "③ head 起（GCS/ Ray cluster 就绪）"
  sh1 "docker start dsv4-head" >/dev/null
  log "④ 50s 后 worker 对准 PG 注册窗口接入"
  sleep 50
  sh2 "docker restart dsv4-worker" >/dev/null
  # ⑤ 健康等待（加载+autotune 约 8-12 分钟；加载窗口内 8001 必为 000——以日志特征判定而非端口）
  for i in $(seq 1 20); do
    sleep 60
    RC=$(sh1 "docker inspect dsv4-head --format '{{.RestartCount}}'" 2>/dev/null || echo "?")
    TAIL=$(sh1 "docker logs dsv4-head --tail 2 2>&1" | tr '\n' ' ')
    H=$(sh1 "curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8001/health" || echo 000)
    log "⑤[$i/20] 8001=$H RC=$RC tail=${TAIL:0:80}"
    # 就绪信号：健康探测被 APIServer 正常应答（日志 200 OK）或端口 200
    if [ "$H" = "200" ] || echo "$TAIL" | grep -qE "GET /health HTTP.1.1. 200|GET /v1/models.*200"; then
      log "✅ vLLM 就绪（unless-stopped 自愈闭环下允许中途崩 1-2 轮，RC=$RC）；等待 Registry 转 ready"
      sleep 40
      do_check || return 1
      # 恢复后 e2e：真实推理一发（经 Registry ready 路由，同时刷新 canary/baseline 指标）
      log "⑥ 恢复后 e2e 推理验证"
      E2E=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$GW" "bash -lc 'cd /Volume2/yyc3-33 && SK=\$(grep ^API_KEYS= .env | cut -d= -f2- | tr -d \\\" | cut -d, -f1); curl -s -o /dev/null -w \"%{http_code}\" -m 20 -X POST http://127.0.0.1:8000/v1/chat/completions -H \"Content-Type: application/json\" -H \"Authorization: Bearer \$SK\" -d \"{\\\"model\\\":\\\"deepseek-v4-flash\\\",\\\"messages\\\":[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"hi\\\"}],\\\"max_tokens\\\":2}\"'" 2>/dev/null)
      [ "$E2E" = "200" ] && log "✅ e2e 推理 → 200（全链恢复）" || { log "⚠️ e2e → $E2E（实例就绪但链路待查，见 health-full.sh ②）"; }
      return 0
    fi
    echo "$TAIL" | grep -qE "Engine core initialization failed|died unexpectedly" \
      && log "⏳ 本轮崩（自愈中，unless-stopped 会拉起）——继续等待"
  done
  log "❌ 20 轮未就绪——人工介入（Loki {job=\"dgx-containers\",host=\"yyc3-101\"} 查崩溃段）；可再跑 recover 或 rootcause 取证"
  return 1
}

# ── rootcause：崩溃取证（只读）──────────────────────────────────
do_rootcause() {
  log "── dsv4 崩溃取证（只读）──"
  log "① 容器生命周期轨迹"
  sh1 "docker inspect dsv4-head --format 'head : Started={{.State.StartedAt}} RC={{.RestartCount}} OOM={{.State.OOMKilled}} Exit={{.State.ExitCode}}'"
  sh2 "docker inspect dsv4-worker --format 'worker: Started={{.State.StartedAt}} RC={{.RestartCount}} Exit={{.State.ExitCode}}'"
  log "② 崩溃特征段（近 2000 行内致命错误，最多 8 条）"
  sh1 "docker logs dsv4-head --tail 2000 2>&1 | grep -nE 'died unexpectedly|Engine core initialization failed|RuntimeError|OOM|out of memory|CUDA error|NCCL error' | tail -8 | cut -c1-200"
  log "③ 显存证据（加载行 + Free memory 行）"
  sh1 "docker logs dsv4-head 2>&1 | grep -E 'Model loading took|Free memory on device|Available KV cache' | tail -4 | cut -c1-180"
  log "④ Ray 集群节点/PG 残留"
  sh1 "docker exec dsv4-head ray status 2>/dev/null | head -12 || echo '(容器内 ray CLI 不可用，跳过)'"
  log "⑤ Registry 当前判定"
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$GW" "bash -lc 'cd /Volume2/yyc3-33 && KEY=\$(grep ^ADMIN_API_KEYS= .env | cut -d= -f2- | tr -d \\\" | cut -d, -f1); curl -s -m 5 -H \"X-API-Key: \$KEY\" http://127.0.0.1:8000/registry/v1/models/deepseek-v4-flash/health'" 2>/dev/null | head -c 300
  echo
  log "── 取证指引 ──"
  log "· 历史崩溃段（30 天外送）：Grafana {job=\"dgx-containers\",host=\"yyc3-101\",container_name=\"dsv4-head\"} |~ \"died unexpectedly|Traceback\""
  log "· 根因矩阵（三层叠加）见 docs/架构与部署/YYC3-Models-资产详情.md v1.4.0"
  log "· 处置：bash $0 recover（编排时序）；复发则评估 max-model-len/util 再下调或迁移共置容器"
}

# ── logs：快捷日志 ──────────────────────────────────────────────
do_logs() {
  local TARGET=${1:-head} LINES=${2:-30}
  case "$TARGET" in
    head)   sh1 "docker logs dsv4-head --tail $LINES 2>&1" ;;
    worker) sh2 "docker logs dsv4-worker --tail $LINES 2>&1" ;;
    *) echo "目标仅 head|worker"; exit 2 ;;
  esac
}

# ── watch：守护自愈（异常自动 recover，≤3 次）───────────────────
do_watch() {
  local INTERVAL=${1:-300} RECOVERS=0 MAX=3
  log "── dsv4 守护启动（每 ${INTERVAL}s check，异常自动 recover，上限 $MAX 次；Ctrl-C 退出）──"
  while true; do
    sleep "$INTERVAL"
    if do_check; then
      log "watch: 正常"
      continue
    fi
    RECOVERS=$((RECOVERS+1))
    if [ "$RECOVERS" -gt "$MAX" ]; then
      log "watch: recover 次数达上限 $MAX——停止守护，人工介入（rootcause 取证）"
      return 1
    fi
    log "watch: 第 $RECOVERS/$MAX 次自动恢复"
    do_recover || log "watch: 本轮恢复未确认，下轮继续"
  done
}

case "$MODE" in
  check)     do_check ;;
  recover)   do_recover ;;
  rootcause) do_rootcause ;;
  logs)      do_logs "${1:-head}" "${2:-30}" ;;
  watch)     do_watch "$@" ;;
  *) grep '^# @usage' -A 7 "$0" | sed 's/^# //'; exit 2 ;;
esac
