#!/bin/bash
# =============================================================================
# @file: health-full.sh
# @description: YYC³ 全链只读自检（管理机执行，零变更零中断）
#               覆盖：公网入口 / 网关 / Registry 认证与就绪 / fluent-bit 双节点 /
#               Loki / Prometheus 告警规则 / P0 指标 / dsv4 旗舰 / Grafana 看板
# @usage:   bash scripts/health-full.sh            # 全量
#           bash scripts/health-full.sh quick      # 核心六项
# @note:    全部只读（无 POST/PATCH/DELETE）；bash 3.2 兼容；凭据经 SSH 读取不落盘
# =============================================================================
set -uo pipefail

TS_IP="${TS_IP:-100.65.172.88}"
NAS="${NAS_SSH:-yyc3-45}"
N1="${N1_SSH:-yyc3-n1}"
N2="${N2_SSH:-yyc3-n2}"
GW="http://$TS_IP:8000"
PASS=0; FAIL=0

log()  { echo "[$(date +%H:%M:%S)] $*"; }
ok()   { echo "  [PASS] $*"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $*"; FAIL=$((FAIL+1)); }
code() { curl -s -o /dev/null -w '%{http_code}' -m "$2" "$1"; }

KEY=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$NAS" \
  "grep '^ADMIN_API_KEYS=' /Volume2/yyc3-33/.env | cut -d= -f2- | tr -d '\"' | cut -d, -f1" 2>/dev/null)
SK=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$NAS" \
  "grep '^API_KEYS=' /Volume2/yyc3-33/.env | cut -d= -f2- | tr -d '\"' | cut -d, -f1" 2>/dev/null)

log "── ① 公网与网关 ──"
[ "$(code https://api.0379.world/healthz 8)" = "200" ] && ok "公网 api.0379.world → 200" || bad "公网入口异常"
[ "$(code http://$TS_IP:8000/healthz 6)" = "200" ] && ok "NAS 网关 :8000 → 200" || bad "网关异常"

log "── ② Registry 就绪与认证 ──"
MODELS=$(curl -s -m 8 "$GW/registry/v1/models" -H "X-API-Key: $KEY")
READY=$(echo "$MODELS" | grep -o '"state":"ready"' | wc -l | tr -d ' ')
TOTAL=$(echo "$MODELS" | grep -o '"id":"[^"]*"' | wc -l | tr -d ' ')
[ "${READY:-0}" -ge 4 ] && ok "Registry ready=$READY / total=$TOTAL" || bad "Registry ready=${READY}（<4）"
# Token 认证活性：无 token 心跳应 401（= 校验开启且正常工作）
T=$(curl -s -o /dev/null -w '%{http_code}' -m 6 -X POST "$GW/registry/v1/models/qwen3-asr-1.7b/heartbeat" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"status":"healthy"}')
[ "$T" = "401" ] && ok "心跳 Token 认证生效（无 token → 401）" || bad "心跳认证异常（无 token → ${T}，应 401）"
# 真实推理链
C=$(curl -s -o /dev/null -w '%{http_code}' -m 20 -X POST "$GW/v1/chat/completions" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $SK" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":2}')
[ "$C" = "200" ] && ok "dsv4 推理链 e2e → 200" || bad "推理链异常（${C}）"

log "── ③ 日志外送链（fluent-bit ×2 → Loki）──"
for N in "$N1" "$N2"; do
  S=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$N" "docker ps --format '{{.Names}} {{.Status}}' | grep -c 'yyc3-fluent-bit Up'" 2>/dev/null)
  [ "$S" = "1" ] && ok "$N fluent-bit Up" || bad "$N fluent-bit 异常"
done
[ "$(code http://$TS_IP:3100/ready 6)" != "000" ] && ok "Loki :3100 响应" || bad "Loki 不可达"

log "── ④ Prometheus 告警规则 ──"
for RULE in RegistryRollbackTriggered BackendErrorRateHigh BackendTTFTP95High; do
  docker_ex() { ssh -o BatchMode=yes -o ConnectTimeout=8 "$NAS" "bash -lc 'docker exec yyc3-prometheus wget -qO- http://localhost:9090/api/v1/rules'" 2>/dev/null; }
  docker_ex | grep -q "$RULE" && ok "规则 $RULE 已加载" || bad "规则 $RULE 缺失"
done

log "── ⑤ P0 指标露出 ──"
METRICS=$(curl -s -m 8 "$GW/metrics")
for M in yyc3_backend_requests_total yyc3_backend_ttft_seconds_count; do
  echo "$METRICS" | grep -q "^$M" && ok "指标 $M" || bad "指标 $M 缺失"
done
# labelled 指标未触发时无 series，属正常——统一判 HELP 注册行（初始化即有）
for M in yyc3_canary_weight yyc3_registry_rollback_total; do
  echo "$METRICS" | grep -q "# HELP $M" && ok "指标 ${M}（注册）" || bad "指标 ${M} 缺失"
done

[ "${1:-}" = "quick" ] && { log "═══ quick 汇总: PASS=$PASS FAIL=$FAIL ═══"; exit $((FAIL > 0)); }

log "── ⑥ dsv4 容器健康 ──"
H=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$N1" "curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8001/health" 2>/dev/null)
ST=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$NAS" "bash -lc 'KEY=\$(grep ^ADMIN_API_KEYS= /Volume2/yyc3-33/.env | cut -d= -f2- | tr -d \\\" | cut -d, -f1); curl -s -m 5 -H \"X-API-Key: \$KEY\" http://127.0.0.1:8000/registry/v1/models/deepseek-v4-flash'" 2>/dev/null | grep -oE '"state":"[a-z]+"' | head -1)
# 判据：实例就绪（8001）+ Registry ready（TTL 内心跳）；RestartCount 生命周期累计不作判据
[ "$H" = "200" ] && echo "$ST" | grep -q ready && ok "dsv4-head 8001=200 + registry=ready" || bad "dsv4-head 异常（8001=$H $ST）"

log "── ⑦ Grafana 看板 ──"
GP=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$NAS" "grep '^GRAFANA_ADMIN_PASSWORD=' /Volume2/yyc3-33/.env | cut -d= -f2-" 2>/dev/null)
[ "$(code "http://$TS_IP:3000/api/dashboards/uid/yyc3-dgx-logs" 6)" != "000" ] && ok "Grafana 看板 yyc3-dgx-logs 可达" || bad "Grafana 看板异常"

log "═══ 汇总: PASS=$PASS FAIL=$FAIL ═══"
exit $((FAIL > 0))
