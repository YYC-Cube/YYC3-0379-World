#!/bin/bash
set -u
cd /Volume2/yyc3-33 || exit 1
D=/Volume3/@apps/DockerEngine/dockerd/bin/docker
LOCK=/tmp/yyc3_autodeploy.lock
LOG=/Volume2/yyc3-33/auto-deploy.log
[ -f "$LOCK" ] && exit 0
trap 'rm -f "$LOCK"' EXIT
touch "$LOCK"
git fetch origin main --quiet 2>/dev/null || exit 0
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/main 2>/dev/null)
[ "$LOCAL" = "$REMOTE" ] && exit 0

# ── 路径过滤（2026-09-26）：纯文档/CI 变更不触发重建 ──
# 命中规则的文件全部出现在本次 diff 中时，仅快进 HEAD 并记录 SKIP。
# 依据：09-24 COMPOSE_FAIL 复盘——docs 提交触发无谓 --build，徒增 NAS OOM 风险。
CHANGED=$(git -c core.quotePath=false diff --name-only "$LOCAL" "$REMOTE" 2>/dev/null)
DEPLOY_NEEDED=0
if [ -n "$CHANGED" ]; then
  while IFS= read -r f; do
    case "$f" in
      docs/*|.github/*|*.md|LICENSE|CONTRIBUTING*) ;;  # 文档类：可安全跳过
      *) DEPLOY_NEEDED=1; break ;;
    esac
  done <<NAMES
$CHANGED
NAMES
fi
if [ -n "$CHANGED" ] && [ "$DEPLOY_NEEDED" = "0" ]; then
  echo "$(date '+%F %T') SKIP_DOCS_ONLY ${REMOTE:0:8} files=$(echo "$CHANGED" | wc -l | tr -d ' ')" >> "$LOG"
  git reset --hard origin/main >> "$LOG" 2>&1
  exit 0
fi

echo "$(date '+%F %T') new commit ${REMOTE:0:8}, deploying" >> "$LOG"
git reset --hard origin/main >> "$LOG" 2>&1
if $D compose --project-directory . -f deploy/nas/docker-compose.nas.yml up -d --build gateway >> "$LOG" 2>&1; then
  # /health 就绪轮询（2026-09-26 防再发整改）：最长 60s（12×5s），消除固定 sleep 20 的启动竞态误报
  READY=0
  for _i in $(seq 1 12); do
    if curl -sf --max-time 5 http://localhost:8000/healthz >/dev/null 2>&1; then READY=1; break; fi
    sleep 5
  done
  if [ "$READY" = "1" ]; then
    echo "$(date '+%F %T') DEPLOY_OK ${REMOTE:0:8}" >> "$LOG"
  else
    echo "$(date '+%F %T') HEALTH_FAIL after ${REMOTE:0:8}" >> "$LOG"
  fi
else
  echo "$(date '+%F %T') COMPOSE_FAIL ${REMOTE:0:8}" >> "$LOG"
fi
