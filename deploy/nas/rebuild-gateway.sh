#!/bin/bash
chmod 755 /home/YYC3 2>/dev/null   # 护栏: TOS 复位 777 会导致 StrictModes 拒绝公钥认证(全网锁死)
set -u
cd /Volume2/yyc3-33 || exit 1
D=/Volume3/@apps/DockerEngine/dockerd/bin/docker
LOG=/Volume2/yyc3-33/auto-deploy.log
C=$(git rev-parse --short HEAD)
echo "$(date '+%F %T') rebuild at $C" >> "$LOG"
# 路径过滤（2026-09-26，与 auto-deploy.sh 同款）：纯文档变更不重建，切断无谓 build/OOM 面
CHANGED=$(git -c core.quotePath=false diff --name-only HEAD~1 HEAD 2>/dev/null)
if [ -n "$CHANGED" ] && [ -z "$(printf "%s\n" "$CHANGED" | grep -vE "^(docs/|\.github/|.*\.md$|^LICENSE|^CONTRIBUTING)")" ]; then
  echo "$(date '+%F %T') SKIP_DOCS_ONLY $C files=$(printf "%s\n" "$CHANGED" | wc -l | tr -d ' ')" >> "$LOG"
  exit 0
fi
if $D compose --project-directory . -f deploy/nas/docker-compose.nas.yml up -d --build gateway >> "$LOG" 2>&1; then
  sleep 20
  curl -sf --max-time 8 http://localhost:8000/healthz >/dev/null     && echo "$(date '+%F %T') DEPLOY_OK $C" >> "$LOG"     || echo "$(date '+%F %T') HEALTH_FAIL $C" >> "$LOG"
else
  echo "$(date '+%F %T') COMPOSE_FAIL $C" >> "$LOG"
fi

# ── 部署后冒烟（失败仅告警不阻断；smoke-test.sh 随 repo 分发）──
# 等网关就绪（重建后容器启动有延迟，避免 smoke 误报）
for i in $(seq 1 30); do curl -s -m 2 -o /dev/null http://127.0.0.1:8000/health && break; sleep 2; done
if [ -x /Volume2/yyc3-33/deploy/nas/smoke-test.sh ]; then
  API_KEY=$(grep "^API_KEYS" /Volume2/yyc3-33/.env | cut -d= -f2 | cut -d, -f1) GATEWAY_BASE=http://127.0.0.1:8000 bash /Volume2/yyc3-33/deploy/nas/smoke-test.sh >> /Volume2/yyc3-33/auto-deploy.log 2>&1
  if [ $? -eq 0 ]; then echo "$(date +%F\ %T) SMOKE_PASS" >> /Volume2/yyc3-33/auto-deploy.log; else echo "$(date +%F\ %T) SMOKE_FAIL" >> /Volume2/yyc3-33/auto-deploy.log; fi
fi
