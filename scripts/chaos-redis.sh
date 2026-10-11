#!/bin/bash
# =============================================================================
# @file: chaos-redis.sh
# @description: Redis 宕机故障演练（注入-观测-恢复三段，管理机执行）
#               验收口径（审计报告 §四中期项）：
#                 1. 存活探针：/healthz 全程 200（Redis 不参与存活判定）
#                 2. 故障识别：/health services.redis.status=unreachable
#                 3. 三能力降级有定义：chat/embeddings/rerank 全程 200（fail-open）
#                 4. 告警有触发：Prometheus RedisDown firing（yyc3_redis_up=0 持续 1m）
#                 5. 恢复有回切：Redis 回来后 /health 转 healthy，限流日志见「已恢复」
# @usage:   bash scripts/chaos-redis.sh                    # 标准档：宕机 120s
#           CHAOS_HOLD=300 bash scripts/chaos-redis.sh      # 发布门禁档：宕机 5 分钟
#           CHAT_MODEL=xxx EMB_MODEL=xxx RERANK_MODEL=xxx bash scripts/chaos-redis.sh
# @note:    注入 docker stop（restart=unless-stopped 不会自动拉起已手动停止容器）；
#           trap 双保险：任何退出路径都会尝试拉起 Redis，杜绝演练变事故；
#           演练范围=网关三能力；A2A worker 在宕机期消费受阻属预期（PEL 保护，
#           恢复后 XAUTOCLAIM 回收，不计 FAIL）
# =============================================================================
set -uo pipefail

TS_IP="${TS_IP:-100.65.172.88}"
NAS="${NAS_SSH:-yyc3-45}"
GW="http://$TS_IP:8000"
REDIS_CONTAINER="0379-world-redis-1"
PROM_CONTAINER="yyc3-prometheus"
GATEWAY_CONTAINER="0379-world-gateway-1"

HOLD="${CHAOS_HOLD:-120}"           # 宕机保持秒数
ALERT_BUDGET="${ALERT_BUDGET:-180}" # 注入后 RedisDown firing 观测预算（秒）
POLL=15                             # 保持期采样间隔

CHAT_MODEL="${CHAT_MODEL:-deepseek-v4-flash}"
EMB_MODEL="${EMB_MODEL:-qwen3-embedding-0.6b}"
RERANK_MODEL="${RERANK_MODEL:-qwen3-reranker-0.6b}"

PASS=0; FAIL=0
INJECTED=0

log()  { echo "[$(date +%H:%M:%S)] $*"; }
ok()   { echo "  [PASS] $*"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $*"; FAIL=$((FAIL+1)); }
code() { curl -s -o /dev/null -w '%{http_code}' -m "$2" "$1"; }

# ── 安全网：任何退出路径都确保 Redis 被拉起 ──
cleanup() {
  if [ "$INJECTED" = "1" ]; then
    log "── 安全网：确保 Redis 恢复 ──"
    ssh_nas "docker start $REDIS_CONTAINER" >/dev/null 2>&1 \
      && log "Redis 已拉起（cleanup）" || log "!! cleanup 拉起失败，请人工执行: ssh $NAS docker start $REDIS_CONTAINER"
    INJECTED=0
  fi
}
trap cleanup EXIT
# TERM/INT 显式接 cleanup：仅有 EXIT trap 时，信号若在 sleep 内到达，bash 会等 sleep
# 结束才处理，极端情况（等待期进程被杀）安全网被跳过——2026-10-12 首跑实证。
# pause() 用 `sleep & wait` 使信号即刻打断等待，trap 及时执行。
trap 'exit 130' TERM INT
pause() { sleep "$1" & wait $!; }

# 远端执行必须经登录 shell（bash -lc）恢复 PATH：非交互 SSH 下 docker 不在 PATH，
# 裸执行会「command not found」静默落空——与 load-prom-rule.sh 同一坑。
# 引用约定：调用方命令串中不得含未转义双引号（经 ssh 远端 sh 双引号层传递）。
ssh_nas() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$NAS" "bash -lc \"$*\"" 2>/dev/null; }

# ── 凭据（同 health-full.sh 口径：NAS .env 经 SSH 读取不落盘）
# 注意：tr 删引号用八进制 \042 而非字面 "——命令串整体经 ssh 远端 sh 双引号层传递，
# 字面双引号会提前闭合远端引用导致解析错位。
KEY=$(ssh_nas "grep '^ADMIN_API_KEYS=' /Volume2/yyc3-33/.env | cut -d= -f2- | tr -d '\042' | cut -d, -f1")
SK=$(ssh_nas  "grep '^API_KEYS=' /Volume2/yyc3-33/.env | cut -d= -f2- | tr -d '\042' | cut -d, -f1")

# ── 能力探测（三能力；期望全 200 = fail-open 降级有定义）
# 注意：不得复用 code()（签名 code URL TIMEOUT，不支持 flag 前置）；POST 场景直接 curl。
probe_capabilities() {
  local tag="$1" rc
  rc=$(curl -s -o /dev/null -w '%{http_code}' -m 25 -X POST "$GW/v1/chat/completions" \
    -H "Content-Type: application/json" -H "Authorization: Bearer $SK" \
    -d "{\"model\":\"$CHAT_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":2}")
  [ "$rc" = "200" ] && ok "[$tag] chat ($CHAT_MODEL) → 200" || bad "[$tag] chat → ${rc}（应 200）"

  rc=$(curl -s -o /dev/null -w '%{http_code}' -m 25 -X POST "$GW/v1/embeddings" \
    -H "Content-Type: application/json" -H "Authorization: Bearer $SK" \
    -d "{\"model\":\"$EMB_MODEL\",\"input\":\"hi\"}")
  [ "$rc" = "200" ] && ok "[$tag] embeddings ($EMB_MODEL) → 200" || bad "[$tag] embeddings → ${rc}（应 200）"

  rc=$(curl -s -o /dev/null -w '%{http_code}' -m 30 -X POST "$GW/v1/rerank" \
    -H "Content-Type: application/json" -H "Authorization: Bearer $SK" \
    -d "{\"model\":\"$RERANK_MODEL\",\"query\":\"hi\",\"documents\":[\"hello world\"]}")
  [ "$rc" = "200" ] && ok "[$tag] rerank ($RERANK_MODEL) → 200" || bad "[$tag] rerank → ${rc}（应 200）"
}

# ── Prometheus RedisDown 查询（经 NAS 容器内 wget，管理机本地 python3 解析）──
redisdown_firing() {
  ssh_nas "docker exec $PROM_CONTAINER wget -qO- http://localhost:9090/api/v1/alerts" \
    | /usr/bin/python3 -c '
import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
for a in d.get("data", {}).get("alerts", []):
    if a.get("labels", {}).get("alertname") == "RedisDown" and a.get("state") == "firing":
        sys.exit(0)
sys.exit(1)'
}

# ── ① 前置检查：演练前系统须全绿 ──
log "── ① 前置检查 ──"
R=$(ssh_nas "docker ps --format '{{.Names}} {{.Status}}' | grep '$REDIS_CONTAINER '")
echo "$R" | grep -q "Up" && ok "Redis 容器运行中（$R）" || { bad "Redis 容器未运行，终止演练"; exit 1; }
[ "$(code "$GW/healthz" 6)" = "200" ] && ok "基线 /healthz → 200" || { bad "基线 /healthz 异常，终止演练"; exit 1; }
H=$(curl -s -m 8 "$GW/health")
echo "$H" | grep -q '"redis":{"status":"healthy"}' \
  && ok "基线 /health redis=healthy" || { bad "基线 Redis 已不健康（$H），终止演练"; exit 1; }
probe_capabilities "基线"

# ── ② 注入：停止 Redis ──
log "── ② 注入：docker stop $REDIS_CONTAINER ──"
ssh_nas "docker stop $REDIS_CONTAINER" >/dev/null && INJECTED=1
pause 3
R=$(ssh_nas "docker ps -a --format '{{.Names}} {{.Status}}' | grep '$REDIS_CONTAINER '")
echo "$R" | grep -q "Exited" && ok "Redis 已停止（$R）" || bad "注入失败：容器仍在运行"
[ "$(code "$GW/healthz" 6)" = "200" ] && ok "宕机后 /healthz 仍 200（存活探针不受 Redis 影响）" \
  || bad "宕机后 /healthz 非 200（存活探针被 Redis 污染）"
H=$(curl -s -m 10 "$GW/health")
echo "$H" | grep -q '"redis":{"status":"unreachable"}' \
  && ok "宕机后 /health redis=unreachable（故障被正确识别）" \
  || bad "宕机后 /health redis 未报 unreachable：$(echo "$H" | grep -o '\"redis\":{[^}]*}')"

# ── ③ 保持期：三能力持续可用采样 ──
log "── ③ 保持期 ${HOLD}s（每 ${POLL}s 采样三能力）──"
ELAPSED=0; ROUNDS=0
while [ "$ELAPSED" -lt "$HOLD" ]; do
  probe_capabilities "T+${ELAPSED}s"
  ROUNDS=$((ROUNDS+1))
  pause "$POLL"
  ELAPSED=$((ELAPSED+POLL))
done
[ "$ROUNDS" -ge 1 ] && ok "保持期完成 $ROUNDS 轮采样" || bad "保持期无采样轮次"

# ── ④ 告警验收：RedisDown firing ──
log "── ④ 告警验收：RedisDown firing（预算 ${ALERT_BUDGET}s）──"
ALERT_OK=0; AB=0
while [ "$AB" -lt "$ALERT_BUDGET" ]; do
  if redisdown_firing; then ALERT_OK=1; break; fi
  pause 15; AB=$((AB+15))
done
[ "$ALERT_OK" = "1" ] && ok "RedisDown 已 firing（注入后约 $(( (HOLD > AB ? HOLD : 0) + AB ))s 内）" \
  || bad "预算 ${ALERT_BUDGET}s 内 RedisDown 未 firing（查 yyc3_redis_up 指标与规则装载）"

# ── ⑤ 恢复：拉起 Redis + 回切验收 ──
log "── ⑤ 恢复：docker start + 回切验收 ──"
ssh_nas "docker start $REDIS_CONTAINER" >/dev/null 2>&1
INJECTED=0
# 等容器健康检查转 healthy（healthcheck interval 10s）
HB=0; HOK=0
while [ "$HB" -lt 60 ]; do
  S=$(ssh_nas "docker inspect -f '{{.State.Health.Status}}' $REDIS_CONTAINER")
  [ "$S" = "healthy" ] && { HOK=1; break; }
  pause 5; HB=$((HB+5))
done
[ "$HOK" = "1" ] && ok "Redis 容器恢复 healthy（${HB}s）" || bad "Redis 健康检查未转 healthy（=${S:-unknown}）"

# 网关视角恢复：探活轮询 60s 一轮 + /health 事件驱动，给 90s 预算
RB=0; ROK=0
while [ "$RB" -lt 90 ]; do
  H=$(curl -s -m 10 "$GW/health")
  echo "$H" | grep -q '"redis":{"status":"healthy"}' && { ROK=1; break; }
  pause 10; RB=$((RB+10))
done
[ "$ROK" = "1" ] && ok "网关 /health redis 恢复 healthy（${RB}s）" || bad "网关视角 Redis 未恢复"

probe_capabilities "恢复后"

# 限流回切：请求触发 10s 冷却重探测，日志应现「Redis 限流后端已恢复」
pause 12
curl -s -o /dev/null -m 10 "$GW/healthz"
L=$(ssh_nas "docker logs $GATEWAY_CONTAINER --since 5m 2>&1 | grep -c 'Redis 限流后端已恢复'")
[ "${L:-0}" -ge 1 ] && ok "限流已回切 Redis 模式（日志「Redis 限流后端已恢复」×$L）" \
  || bad "未见限流回切日志（应现「Redis 限流后端已恢复」）"

log "═══ 演练汇总: PASS=$PASS FAIL=$FAIL ═══"
[ "$FAIL" -eq 0 ] && log "✅ 全项通过：降级有定义 / 告警有触发 / 恢复有回切" \
                  || log "❌ $FAIL 项未达标，按上方 FAIL 清单跟进"
exit $((FAIL > 0))
