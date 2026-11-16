#!/bin/bash
# YYC³ LeisureManage · 节假日告警静默(Alertmanager Silences API;2026-11-07)
# 用途:按 holidays.json(同目录,每年核定)为法定节假日批量创建/清理静默,
#      避免节假日值班群被容量类告警刷屏;LeisureApiDown(critical)默认不在静默集。
# 机制:docker exec 进 yyc3-alertmanager 容器(9093 未映射宿主端口)调 /api/v2/silences;
#      幂等标记 = comment "holiday:<name>-<year>",重复 --apply 自动清理旧标记再建。
# 用法(NAS 宿主机):
#   bash am-holiday-silence.sh --dry-run        # 预览将创建的静默
#   bash am-holiday-silence.sh --apply          # 创建/刷新全部节假日静默
#   bash am-holiday-silence.sh --remove         # 清理全部 holiday: 标记静默
#   bash am-holiday-silence.sh --list           # 列出当前 holiday: 静默
# 前置:am-holiday-silence.sh 与 holidays.json 同目录(源:deploy/nas/,流程第十·一条)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
AM_CONTAINER="${AM_CONTAINER:-yyc3-alertmanager}"
JSON="$DIR/holidays.json"
# NAS DockerEngine CLI 不在默认 PATH(容器化 dockerd;宿主 sudo 白名单不含 docker)
DOCKER_BIN="${DOCKER_BIN:-$(command -v docker || echo /Volume3/@apps/DockerEngine/dockerd/bin/docker)}"
[ -f "$JSON" ] || { echo "❌ 缺 $JSON"; exit 1; }
[ -x "$DOCKER_BIN" ] || { echo "❌ docker CLI 不可执行: $DOCKER_BIN"; exit 1; }
command -v python3 >/dev/null || { echo "❌ 需 python3"; exit 1; }

# AM 9093 未映射宿主端口 → docker inspect 取容器网桥 IP,宿主 python3 urllib 直连(GET/POST/DELETE 全方法;
# busybox wget 无 --method=DELETE,已实证删不掉旧静默导致幂等复跑重复累积)
AM_IP="$("$DOCKER_BIN" inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$v.IPAddress}} {{end}}' "$AM_CONTAINER" | awk '{print $1}')"
[ -n "$AM_IP" ] || { echo "❌ 取容器 IP 失败"; exit 1; }
export AM_URL="http://$AM_IP:9093"

am_api() { # $1=method $2=path $3=postbody(可空) → stdout=响应体
  python3 - "$AM_URL$2" "${1}" "${3:-}" <<'PYAPI'
import sys, urllib.request
url, method, body = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''
req = urllib.request.Request(url, method=method, data=(body.encode() if body else None),
                             headers={'Content-Type': 'application/json'} if body else {})
try:
    print(urllib.request.urlopen(req, timeout=10).read().decode())
except Exception as e:
    getattr(getattr(e, 'fp', None), 'read', lambda: b'')()
    sys.exit(0)
PYAPI
}

ACTION="${1:---list}"
case "$ACTION" in
  --list)
    # AM 的 DELETE 语义=标记过期(行仍留列表);只显示未过期静默
    am_api GET "/api/v2/silences" | python3 -c '
import json,sys
rows=json.load(sys.stdin)
mine=[r for r in rows if (r.get("comment") or "").startswith("holiday:") and r["status"]["state"] != "expired"]
if not mine: print("当前无有效 holiday: 静默")
for r in mine:
    print(r["id"], r["comment"], r["startsAt"][:16], "→", r["endsAt"][:16], r["status"]["state"])
'
    ;;
  --remove)
    IDS=$(am_api GET "/api/v2/silences" | python3 -c '
import json,sys
rows=json.load(sys.stdin)
print("\n".join(r["id"] for r in rows if (r.get("comment") or "").startswith("holiday:") and r["status"]["state"] != "expired"))
')
    [ -z "$IDS" ] && { echo "无有效 holiday: 静默可清理"; exit 0; }
    for id in $IDS; do am_api DELETE "/api/v2/silence/$id" >/dev/null; echo "已过期化 $id"; done
    ;;
  --dry-run|--apply)
    # 由 python 生成 silence payload 列表(起点 00:00,终点次日 00:00=全天;本地时区偏移写入 ISO)
    PAYLOADS=$(python3 - "$JSON" <<'PYEOF'
import json, sys, datetime
cfg = json.load(open(sys.argv[1]))
year = cfg["year"]; dms = cfg.get("defaultMatchers", [])
TZ = datetime.datetime.now().astimezone().strftime("%z")
def iso(d): return d + "T00:00:00.000" + TZ
for h in cfg["holidays"]:
    ms = []
    for m in h.get("matchers", dms):
        ms.append({"name": m["name"], "value": m["value"], "isRegex": m.get("isRegex", False)})
    tag = "holiday:%s-%d" % (h["name"], year)
    print(json.dumps({
        "matchers": ms,
        "startsAt": iso(h["start"]), "endsAt": iso(h["end"]),
        "createdBy": "am-holiday-silence.sh", "comment": tag,
    }, ensure_ascii=False))
PYEOF
)
    echo "$PAYLOADS" | python3 -c '
import json,sys
for line in sys.stdin:
    p=json.loads(line)
    ms=",".join((m["name"]+"=~"+m["value"]) if m["isRegex"] else (m["name"]+"=\""+m["value"]+"\"") for m in p["matchers"])
    print(p["comment"], p["startsAt"][:10], "→", p["endsAt"][:10], "|", ms)
'
    if [ "$ACTION" = "--apply" ]; then
        # 幂等:先清旧标记再建
        bash "$0" --remove >/dev/null 2>&1 || true
        echo "$PAYLOADS" | while IFS= read -r line; do
            RESP=$(am_api POST "/api/v2/silences" "$line")
            echo "已创建: $(printf '%s' "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("silenceId","?"))' 2>/dev/null || echo '?')"
        done
        echo "── 当前 holiday: 静默 ──"
        bash "$0" --list
    else
        echo "(dry-run 预览;加 --apply 落地)"
    fi
    ;;
  *) echo "用法: $0 --list|--dry-run|--apply|--remove"; exit 1 ;;
esac
