#!/bin/bash
# =============================================================================
# @file: setup-container-map.sh
# @description: 容器日志外送 + 容器名映射 一键部署（05 Runbook §2.4）
#               fluent-bit(tail+Path_Key+cn.lua) → NAS Loki + container-map.timer
# @usage:   节点侧执行（本目录需已有仓库 deploy/dgx/ 同步的部署文件）：
#             bash setup-container-map.sh                 # 自动探测 NODE_ID（hostname）
#             NODE_ID=yyc3-102 bash setup-container-map.sh
#           管理机一键（模板）：
#             ssh <node> 'mkdir -p /home/yyc3/logging' && \
#             scp deploy/dgx/{fluent-bit.conf,cn.lua,container-map.sh,container-map.service,container-map.timer,docker-compose.logging.yml} \
#                 <node>:/home/yyc3/logging/ && \
#             ssh <node> 'bash /home/yyc3/logging/setup-container-map.sh'
# @note:    幂等——重复执行安全（compose recreate + unit 覆盖 + timer 重复 enable 无害）
# @deps:    docker + docker compose 插件；systemd；Tailscale 可达 NODE_LOKI_HOST
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$DIR"
NODE_ID="${NODE_ID:-$(hostname)}"
NODE_LOKI_HOST="${NODE_LOKI_HOST:-100.65.172.88}"
NODE_LOKI_PORT="${NODE_LOKI_PORT:-3100}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

# 0. 前置文件校验
for f in fluent-bit.conf cn.lua container-map.sh container-map.service container-map.timer docker-compose.logging.yml; do
  [ -f "$LOG_DIR/$f" ] || { echo "❌ 缺少部署文件: $LOG_DIR/$f（先从仓库 deploy/dgx/ 同步）"; exit 2; }
done
curl -s -o /dev/null -m 5 "http://$NODE_LOKI_HOST:$NODE_LOKI_PORT/ready" \
  || { echo "❌ NAS Loki 不可达: $NODE_LOKI_HOST:$NODE_LOKI_PORT"; exit 2; }

log "节点: $NODE_ID → Loki $NODE_LOKI_HOST:$NODE_LOKI_PORT"

# 1. systemd 单元 + timer（映射表每 5 分钟刷新）
sudo cp "$LOG_DIR/container-map.service" "$LOG_DIR/container-map.timer" /etc/systemd/system/
sudo chmod +x "$LOG_DIR/container-map.sh"
sudo systemctl daemon-reload
sudo systemctl enable --now container-map.timer >/dev/null
log "✓ container-map.timer 已启用（OnUnitActiveSec=5min）"

# 2. 首次生成映射表并注入 fluent-bit 容器（compose 起来后执行）
bash "$LOG_DIR/container-map.sh" 2>/dev/null || log "⚠️ 首次映射注入失败（容器未起？步骤 3 后重跑本脚本）"

# 3. fluent-bit 容器（compose 变量化：NODE_ID/NODE_LOKI_*）
cd "$LOG_DIR"
NODE_ID="$NODE_ID" NODE_LOKI_HOST="$NODE_LOKI_HOST" NODE_LOKI_PORT="$NODE_LOKI_PORT" \
  docker compose -p yyc3-logging -f docker-compose.logging.yml up -d --force-recreate >/dev/null
log "✓ fluent-bit 容器已部署"

# 4. 二次注入（步骤 2 时容器可能未起；docker cp 后 lua 300s 内自刷新，restart 立即生效）
bash "$LOG_DIR/container-map.sh" 2>/dev/null && docker restart yyc3-fluent-bit >/dev/null
MAP_LINES=$(docker cp yyc3-fluent-bit:/fluent-bit/etc/container_map.tsv /tmp/.cm_check.tsv >/dev/null 2>&1 && wc -l < /tmp/.cm_check.tsv && rm -f /tmp/.cm_check.tsv || echo "?")
log "✓ container_map.tsv 已注入（$MAP_LINES 条）"

# 5. 验证
sleep 5
FAILED=0
systemctl is-active --quiet container-map.timer || { log "❌ timer 未运行"; FAILED=1; }
docker ps --format '{{.Names}} {{.Status}}' | grep -q "yyc3-fluent-bit Up" || { log "❌ fluent-bit 未运行"; FAILED=1; }
docker logs yyc3-fluent-bit --since 2m 2>&1 | grep -qi " error " && { log "❌ fluent-bit 有错误日志"; FAILED=1; }
[ "$FAILED" -eq 0 ] && log "✅ 部署完成：fluent-bit 运行中 + timer 活跃 + Loki 收流（Grafana 看板 job=dgx-containers,host=$NODE_ID）"
exit $FAILED
