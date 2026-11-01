#!/bin/bash
# NAS cron 自动部署脚本（仓库分发副本；2026-11-01 迁移现代化：工作区可经 YYC3_NAS_WS 覆盖，
# 默认 /Volume3/docker/yyc3-0379-world。拉取通道 origin=github https——私有仓需 NAS 侧凭据，
# 未配凭据时本脚本静默跳过，主部署通道为 Mac 部署桥 ~/yyc3-deploy/watch.sh 的 ssh push）
set -u
WS=${YYC3_NAS_WS:-/Volume3/docker/yyc3-0379-world}
cd "$WS" || exit 1
D=/Volume3/@apps/DockerEngine/dockerd/bin/docker
LOCK=/tmp/yyc3_autodeploy.lock
LOG="$WS/auto-deploy.log"
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
# 工程名由 compose 文件顶层 name: 锚定（2026-11-01 修正），不传 -p
if $D compose --project-directory "$WS" -f deploy/nas/docker-compose.nas.yml up -d --build gateway >> "$LOG" 2>&1; then
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
