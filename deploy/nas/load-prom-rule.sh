#!/bin/bash
# =============================================================================
# @file: load-prom-rule.sh
# @description: Prometheus 告警规则装载（管理机 → NAS yyc3-prometheus）
#               固化手工链：scp 规则 → docker cp 进容器 → prometheus.yml 追加去重 → 热加载 → 验证
# @usage:   管理机仓库根目录执行：
#             bash deploy/nas/load-prom-rule.sh                          # 装载 deploy/nas/prometheus-rules/ 全部
#             bash deploy/nas/load-prom-rule.sh deploy/nas/prometheus-rules/hotswap-gate.rules.yml
# @note:    幂等（prometheus.yml 追加前查重）；busybox wget 语法（--post-data 非 -X POST）；
#           prometheus-conf 卷对容器内只读 → 必须 docker cp 整文件替换（勿容器内 sed）
# =============================================================================
set -uo pipefail

NAS_HOST="${NAS_HOST:-yyc3-45}"
RULES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/prometheus-rules" && pwd)"
CONTAINER="yyc3-prometheus"

RULES=("$@")
if [ ${#RULES[@]} -eq 0 ]; then
  RULES=("$RULES_DIR"/*.rules.yml)
fi

log() { echo "[$(date +%H:%M:%S)] $*"; }
# 远端执行（bash -lc 恢复 PATH；参数本地展开进命令串；</dev/null 防止 ssh 吞本地 heredoc）
nas() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$NAS_HOST" \
  "bash -lc 'bash /tmp/.load_rule_remote.sh /tmp/$1'" 2>&1; }

# 远端装载函数（生成远端脚本执行，避免多层引号）
cat > /tmp/.load_rule_remote.sh <<'REMOTE'
#!/bin/bash
set -e
RULE_SRC="$1"
CONTAINER="yyc3-prometheus"
BASE=$(basename "$RULE_SRC")
DEST="/etc/prometheus/$BASE"
docker cp "$RULE_SRC" "$CONTAINER:$DEST"
# prometheus.yml 追加（查重幂等）
docker cp "$CONTAINER:/etc/prometheus/prometheus.yml" /tmp/.prom.yml.tmp
if grep -qF "$DEST" /tmp/.prom.yml.tmp; then
  echo "already-loaded: $BASE"
else
  echo "  - $DEST" >> /tmp/.prom.yml.tmp
  docker cp /tmp/.prom.yml.tmp "$CONTAINER:/etc/prometheus/prometheus.yml"
  echo "appended: $BASE"
fi
rm -f /tmp/.prom.yml.tmp
# 热加载 + 规则验证（busybox wget：POST 用 --post-data）
docker exec "$CONTAINER" wget -qO- --post-data "" http://localhost:9090/-/reload >/dev/null 2>&1
sleep 2
GROUP=$(grep -oE "^groups:|name: [a-z0-9-]+" "$RULE_SRC" | head -2 | tail -1 | awk '{print $2}')
docker exec "$CONTAINER" wget -qO- http://localhost:9090/api/v1/rules | grep -q "$GROUP" \
  && echo "verified: $GROUP" || { echo "verify-FAILED: $GROUP"; exit 1; }
REMOTE
chmod +x /tmp/.load_rule_remote.sh

FAIL=0
for RULE in "${RULES[@]}"; do
  [ -f "$RULE" ] || { log "❌ 规则文件不存在: $RULE"; FAIL=$((FAIL+1)); continue; }
  NAME=$(basename "$RULE")
  scp -q -o BatchMode=yes "$RULE" "$NAS_HOST:/tmp/$NAME" || { log "❌ scp 失败: $NAME"; FAIL=$((FAIL+1)); continue; }
  scp -q -o BatchMode=yes /tmp/.load_rule_remote.sh "$NAS_HOST:/tmp/" || { log "❌ 远端脚本 scp 失败"; FAIL=$((FAIL+1)); continue; }
  OUT=$(nas "$NAME")
  if echo "$OUT" | grep -q "verify-FAILED"; then
    log "❌ $NAME: $(echo "$OUT" | tr '\n' ' ')"
    FAIL=$((FAIL+1))
  else
    log "✅ $NAME: $(echo "$OUT" | grep -E 'already-loaded|appended|verified' | tr '\n' ' ')"
  fi
done

rm -f /tmp/.load_rule_remote.sh
[ "$FAIL" -eq 0 ] && log "✅ 全部规则装载成功" || log "❌ $FAIL 条规则装载失败"
exit "$FAIL"
