#!/bin/bash
# file: smoke-test.sh
# description: 网关部署后冒烟测试——健康/模型列表/旗舰对话(同步+流式)/路由观测
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-09-03
# status: active
# tags: [smoke],[deploy],[gateway]
#
# 用法:
#   GATEWAY_BASE=http://127.0.0.1:8000 API_KEY=sk-xxx ./smoke-test.sh
#   GATEWAY_BASE=https://api.0379.world API_KEY=sk-xxx ./smoke-test.sh   # 公网模式
# 可选: SMOKE_MODEL=deepseek-v4-flash  REQUIRE_UPSTREAM_HEADER=1
# 退出码: 0=全部通过, 1=有失败项

set -u
BASE="${GATEWAY_BASE:-http://127.0.0.1:8000}"
KEY="${API_KEY:-}"
MODEL="${SMOKE_MODEL:-deepseek-v4-flash}"
REQUIRE_UPSTREAM="${REQUIRE_UPSTREAM_HEADER:-1}"

PASS=0
FAIL=0
ok()   { echo "✅ $1"; PASS=$((PASS + 1)); }
bad()  { echo "❌ $1"; FAIL=$((FAIL + 1)); }

echo "═══ YYC³ 网关冒烟测试 → $BASE (model=$MODEL) ═══"

# ── 1. /health ──────────────────────────────────────────────
CODE=$(curl -s -o /tmp/st_h.json -w "%{http_code}" -m 15 "$BASE/health" || echo 000)
if [ "$CODE" = "200" ] && grep -q '"status"' /tmp/st_h.json 2>/dev/null; then
  ok "/health → $CODE ($(python3 -c "import json;d=json.load(open('/tmp/st_h.json'));print(d.get('status'))" 2>/dev/null))"
else
  bad "/health → $CODE"
fi

# ── 2. /v1/models 含旗舰（需认证）──────────────────────────
if [ -n "$KEY" ]; then
  CODE=$(curl -s -o /tmp/st_m.json -w "%{http_code}" -m 15 -H "X-API-Key: $KEY" "$BASE/v1/models" || echo 000)
  if [ "$CODE" = "200" ] && python3 -c "import json,sys; ids=[m['id'] for m in json.load(open('/tmp/st_m.json'))]; sys.exit(0 if '$MODEL' in ids else 1)" 2>/dev/null; then
    ok "/v1/models 认证通过且含 $MODEL"
  elif [ "$CODE" = "200" ]; then
    bad "/v1/models 200 但缺 $MODEL（上游池未注入?）"
  else
    bad "/v1/models → $CODE"
  fi
else
  echo "⏭ /v1/models 跳过（无 API_KEY）"
fi

# ── 3. 旗舰同步对话 + 上游头 ────────────────────────────────
if [ -n "$KEY" ]; then
  CODE=$(curl -s -o /tmp/st_c.json -D /tmp/st_c.h -w "%{http_code}" -m 120 \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"回复ok两个字母即可\"}],\"max_tokens\":16}" \
    "$BASE/v1/chat/completions" || echo 000)
  CONTENT=$(python3 -c "import json;d=json.load(open('/tmp/st_c.json'));print(d['choices'][0]['message']['content'][:40])" 2>/dev/null)
  UPSTREAM=$(grep -i "^x-yyc3-upstream" /tmp/st_c.h 2>/dev/null | tr -d '\r' | cut -d' ' -f2)
  if [ "$CODE" = "200" ] && [ -n "$CONTENT" ]; then
    ok "旗舰对话 200 → “${CONTENT}”"
    if [ "$REQUIRE_UPSTREAM" = "1" ]; then
      if [ -n "$UPSTREAM" ]; then ok "X-YYC3-Upstream: $UPSTREAM"; else bad "缺 X-YYC3-Upstream 头（未走上游池?）"; fi
    fi
  else
    bad "旗舰对话 → $CODE $CONTENT"
  fi
else
  echo "⏭ 旗舰对话跳过（无 API_KEY）"
fi

# ── 4. 流式 SSE ─────────────────────────────────────────────
if [ -n "$KEY" ]; then
  FIRST=$(curl -s -N -m 60 -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"数到3\"}],\"max_tokens\":24,\"stream\":true}" \
    "$BASE/v1/chat/completions" 2>/dev/null | head -c 200)
  if echo "$FIRST" | grep -q "^data: .*choices" 2>/dev/null; then
    ok "流式 SSE 正常（首 chunk 含 choices）"
  else
    bad "流式 SSE 异常: ${FIRST:0:80}"
  fi
else
  echo "⏭ 流式跳过（无 API_KEY）"
fi

# ── 5. 路由观测 ─────────────────────────────────────────────
if [ -n "$KEY" ]; then
  CODE=$(curl -s -o /tmp/st_r.json -w "%{http_code}" -m 15 -H "X-API-Key: $KEY" "$BASE/v1/router/stats" || echo 000)
  if [ "$CODE" = "200" ] && python3 -c "import json;d=json.load(open('/tmp/st_r.json'));assert 'upstream_pool' in d" 2>/dev/null; then
    ok "/v1/router/stats 含 upstream_pool"
  else
    bad "/v1/router/stats → $CODE"
  fi
else
  echo "⏭ 路由观测跳过（无 API_KEY）"
fi

echo "═══ 结果: $PASS 通过 / $FAIL 失败 ═══"
rm -f /tmp/st_h.json /tmp/st_m.json /tmp/st_c.json /tmp/st_c.h /tmp/st_r.json
[ "$FAIL" = "0" ]
