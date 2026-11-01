#!/bin/bash
# NAS 手动重建入口（仓库分发副本；2026-11-01 迁移现代化：工作区可经 YYC3_NAS_WS 覆盖，
# 默认 /Volume3/docker/yyc3-0379-world——10-22 自 /Volume2/yyc3-33 迁入，旧路径仅存迁移档）
# 工程名由 deploy/nas/docker-compose.nas.yml 顶层 name: yyc3-0379-world 锚定（勿再 -p 传参，
# 历史 NAS 手改把 name 粘进 version 行曾致 yyc3-0379-world38 幽灵工程名撞固定容器名）
chmod 755 /home/YYC3 2>/dev/null   # 护栏: TOS 复位 777 会导致 StrictModes 拒绝公钥认证(全网锁死)
set -u
WS=${YYC3_NAS_WS:-/Volume3/docker/yyc3-0379-world}
cd "$WS" || exit 1
D=/Volume3/@apps/DockerEngine/dockerd/bin/docker
LOG="$WS/auto-deploy.log"
C=$(git rev-parse --short HEAD)
echo "$(date '+%F %T') rebuild at $C" >> "$LOG"
# 路径过滤（2026-09-26，与 auto-deploy.sh 同款）：纯文档变更不重建，切断无谓 build/OOM 面
CHANGED=$(git -c core.quotePath=false diff --name-only HEAD~1 HEAD 2>/dev/null)
if [ -n "$CHANGED" ] && [ -z "$(printf "%s\n" "$CHANGED" | grep -vE "^(docs/|\.github/|.*\.md$|^LICENSE|^CONTRIBUTING)")" ]; then
  echo "$(date '+%F %T') SKIP_DOCS_ONLY $C files=$(printf "%s\n" "$CHANGED" | wc -l | tr -d ' ')" >> "$LOG"
  exit 0
fi

# ── 部署前上游预检（P3-2：失败仅告警不阻断；python3 缺失或非 JSON 池则静默跳过）──
# 对上游池逐个探 base_url+health_path（与 upstream_registry.probe_all 同一 URL 语义），
# 任一不可达记 PREFLIGHT_WARN——提前暴露「网关起来了但上游指错」的配置漂移（RB-10 类）
UPS=$(grep "^OPENAI_COMPATIBLE_UPSTREAMS=" "$WS/.env" 2>/dev/null | cut -d= -f2-)
if [ -n "$UPS" ] && command -v python3 >/dev/null 2>&1; then
  BAD=$(python3 -c '
import json, sys, urllib.request
try:
    pool = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
if not isinstance(pool, list):
    sys.exit(0)
for u in pool:
    base = str(u.get("base_url", "")).rstrip("/")
    if not base:
        continue
    url = base + str(u.get("health_path", "/health"))
    try:
        urllib.request.urlopen(url, timeout=4)
    except Exception:
        print(u.get("name", "?"))
' "$UPS" 2>/dev/null)
  if [ -n "$BAD" ]; then
    echo "$(date '+%F %T') PREFLIGHT_WARN 上游不可达: $(echo "$BAD" | tr "\n" " ")" >> "$LOG"
  fi
fi

if $D compose --project-directory "$WS" -f deploy/nas/docker-compose.nas.yml up -d --build gateway >> "$LOG" 2>&1; then
  READY=0
  for _i in $(seq 1 12); do
    curl -sf --max-time 5 http://localhost:8000/healthz >/dev/null 2>&1 && { READY=1; break; }
    sleep 5
  done
  [ "$READY" = "1" ] && echo "$(date '+%F %T') DEPLOY_OK $C" >> "$LOG" || echo "$(date '+%F %T') HEALTH_FAIL $C" >> "$LOG"
else
  echo "$(date '+%F %T') COMPOSE_FAIL $C" >> "$LOG"
fi

# ── 部署后冒烟（失败仅告警不阻断；smoke-test.sh 随 repo 分发）──
for i in $(seq 1 30); do curl -s -m 2 -o /dev/null http://127.0.0.1:8000/health && break; sleep 2; done
if [ -x "$WS/deploy/nas/smoke-test.sh" ]; then
  API_KEY=$(grep "^API_KEYS" "$WS/.env" | cut -d= -f2 | cut -d, -f1) GATEWAY_BASE=http://127.0.0.1:8000 bash "$WS/deploy/nas/smoke-test.sh" >> "$WS/auto-deploy.log" 2>&1
  if [ $? -eq 0 ]; then echo "$(date +%F\ %T) SMOKE_PASS" >> "$WS/auto-deploy.log"; else echo "$(date +%F\ %T) SMOKE_FAIL" >> "$WS/auto-deploy.log"; fi
fi
