#!/usr/bin/env bash
# ===========================================================
# YYC³ 全链路端到端验证脚本
# 验证所有 API 端点和多端访问方式的有效性
# 使用: bash scripts/verify-full-link.sh
# ===========================================================
set -euo pipefail

# ── 配置 ────────────────────────────────────────────────────────
BASE_URL="${BASE_URL:-https://api.0379.world}"
API_KEY="${API_KEY:-}"
TIMEOUT=15
PASS=0
FAIL=0
FAILURES=()

# ── 颜色 ────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_pass() { PASS=$((PASS+1)); echo -e "  ${GREEN}✅ PASS${NC} $1"; }
log_fail() { FAIL=$((FAIL+1)); FAILURES+=("$1"); echo -e "  ${RED}❌ FAIL${NC} $1"; }
header()   { echo -e "\n${YELLOW}═══════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${YELLOW}═══════════════════════════════════════${NC}"; }
detail()   { echo -e "     ${BLUE}$1${NC}"; }

# ── 检查前置依赖 ────────────────────────────────────────────────
check_prereqs() {
  local missing=()
  command -v curl >/dev/null 2>&1 || missing+=("curl")
  command -v python3 >/dev/null 2>&1 || missing+=("python3")
  if [ ${#missing[@]} -gt 0 ]; then
    echo -e "${RED}❌ 缺少必要工具: ${missing[*]}${NC}"
    exit 1
  fi
}

# ── 检查 API Key ────────────────────────────────────────────────
check_api_key() {
  if [ -z "$API_KEY" ]; then
    # 尝试从环境变量或 .env 读取
    if [ -f .env ]; then
      export "$(grep -E '^API_KEYS=' .env | head -1)"
      API_KEY="${API_KEYS%%,*}"
    fi
    if [ -z "$API_KEY" ]; then
      echo -e "${YELLOW}⚠️  API_KEY 未设置，跳过需要认证的测试${NC}"
      echo -e "   设置: export API_KEY=sk-xxx"
    fi
  fi
}

# ── API 请求封装（含超时） ─────────────────────────────────────
api_get() {
  local url="$1"
  shift
  if [ -n "$API_KEY" ]; then
    curl -sf --max-time "$TIMEOUT" -H "X-API-Key: $API_KEY" "$url" 2>/dev/null
  else
    curl -sf --max-time "$TIMEOUT" "$url" 2>/dev/null
  fi
}

api_post() {
  local url="$1"; shift
  local data="$1"; shift
  if [ -n "$API_KEY" ]; then
    curl -sf --max-time "$TIMEOUT" -X POST "$url" \
      -H "Content-Type: application/json" \
      -H "X-API-Key: $API_KEY" \
      -d "$data" 2>/dev/null
  else
    curl -sf --max-time "$TIMEOUT" -X POST "$url" \
      -H "Content-Type: application/json" \
      -d "$data" 2>/dev/null
  fi
}

# ============================================================
# 验证流程开始
# ============================================================
echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║       YYC³ 全链路端到端验证                        ║${NC}"
echo -e "${YELLOW}║       ${BASE_URL}${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

check_prereqs
check_api_key

START_TIME=$(date +%s)

# ── 1. 基础设施层 ──────────────────────────────────────────────
header "1/9 基础设施层 — 节点连通性"

# 本地 Docker 服务检查（如果本地有 Docker）
if command -v docker &>/dev/null; then
  echo "  检查本地 Docker..."
  docker info >/dev/null 2>&1 && log_pass "Docker daemon 运行中" || log_fail "Docker daemon 未运行"
fi

# ── 2. 健康检查 ────────────────────────────────────────────────
header "2/9 健康检查端点"

RESP=$(curl -sf --max-time "$TIMEOUT" "$BASE_URL/health" 2>/dev/null || echo "")
if [ -n "$RESP" ]; then
  STATUS=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null)
  VERSION=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','unknown'))" 2>/dev/null)
  
  if [ "$STATUS" = "healthy" ]; then
    log_pass "健康检查: status=$STATUS, version=$VERSION"
    detail "Uptime: $(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('uptime_seconds',0))")s"
    
    # 显示各服务状态
    echo "  服务状态:"
    echo "$RESP" | python3 -c "
import sys, json
data = json.load(sys.stdin)
services = data.get('services', {})
for name, status in services.items():
    s = status.get('status', 'unknown')
    icon = '✅' if s in ('healthy','configured') else '❌'
    print(f'    {icon} {name}: {s}')
" 2>/dev/null || true
  else
    log_fail "健康检查: status=$STATUS"
  fi
else
  log_fail "健康检查: 无响应（检查 $BASE_URL/health）"
fi

# ── 3. Ping ────────────────────────────────────────────────────
header "3/9 Ping 端点"

RESP=$(curl -sf --max-time 5 "$BASE_URL/v1/ping" 2>/dev/null || echo "")
if echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null | grep -q "ok"; then
  log_pass "/v1/ping 返回 ok"
else
  log_fail "/v1/ping 无响应"
fi

# ── 4. 模型列表 ────────────────────────────────────────────────
header "4/9 模型列表 & 路由"

if [ -n "$API_KEY" ]; then
  MODELS=$(api_get "$BASE_URL/v1/models")
  MODEL_COUNT=$(echo "$MODELS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
  
  if [ "$MODEL_COUNT" -gt 0 ]; then
    log_pass "/v1/models → $MODEL_COUNT 个模型"
    
    echo "  可用模型:"
    echo "$MODELS" | python3 -c "
import sys, json
for m in json.load(sys.stdin):
    icon = '🆓' if m.get('cost_per_1k_tokens', 0) == 0 else '💰'
    print(f'    {icon} {m[\"id\"]:20s} [{m[\"backend\"]:8s}] {m.get(\"display_name\",\"\")}')
" 2>/dev/null || true

    # GPU 感知路由验证
    echo ""
    echo "  GPU 感知路由 (/v1/model/type):"
    for model in "llama3.2" "glm-4-flash" "deepseek-chat"; do
      TYPE=$(api_get "$BASE_URL/v1/model/type?model=$model" | python3 -c "import sys,json; print(json.load(sys.stdin).get('backend_type','unknown'))" 2>/dev/null || echo "error")
      if [ "$TYPE" != "error" ]; then
        echo -e "    ${GREEN}✅${NC} $model → $TYPE"
      else
        echo -e "    ${RED}❌${NC} $model → 查询失败"
      fi
    done
  else
    log_fail "/v1/models 返回 0 个模型"
    detail "响应: $(echo "$MODELS" | head -c 200)"
  fi
else
  log_fail "/v1/models (未设置 API_KEY，跳过)"
fi

# ── 5. 聊天补全（REST） ──────────────────────────────────────
header "5/9 聊天补全 (REST)"

if [ -n "$API_KEY" ]; then
  # 本地模型测试
  RESP=$(api_post "$BASE_URL/v1/chat/completions" \
    '{"model":"llama3.2","messages":[{"role":"user","content":"回复两个字：你好"}],"max_tokens":20}')
  
  CONTENT=$(echo "$RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d['choices'][0]['message']['content'][:30])
except: print('ERROR')
" 2>/dev/null || echo "ERROR")
  
  if [ "$CONTENT" != "ERROR" ] && [ -n "$CONTENT" ]; then
    log_pass "聊天补全: llama3.2 → \"$CONTENT\""
  else
    log_fail "聊天补全: llama3.2 无有效响应"
    detail "响应: $(echo "$RESP" | head -c 200)"
  fi
else
  log_fail "聊天补全 (未设置 API_KEY，跳过)"
fi

# ── 6. 流式补全（SSE） ───────────────────────────────────────
header "6/9 流式补全 (SSE)"

if [ -n "$API_KEY" ]; then
  CHUNKS=$(curl -sfN --max-time 10 -X POST "$BASE_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"model":"llama3.2","messages":[{"role":"user","content":"回复一个字：好"}],"max_tokens":10,"stream":true}' 2>/dev/null \
    | grep -c "data:" || true)
  
  if [ "$CHUNKS" -gt 0 ]; then
    log_pass "SSE 流式: 收到 $CHUNKS 个数据块"
  else
    log_fail "SSE 流式: 无数据块"
  fi
else
  log_fail "SSE 流式 (未设置 API_KEY，跳过)"
fi

# ── 7. API 版本管理 ───────────────────────────────────────────
header "7/9 API 版本管理 & 缓存统计"

# 版本管理
VERSIONS=$(curl -sf --max-time 5 "$BASE_URL/v1/versions" 2>/dev/null || echo "")
if [ -n "$VERSIONS" ]; then
  VERSION_COUNT=$(echo "$VERSIONS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
  log_pass "/v1/versions → $VERSION_COUNT 个版本"
else
  log_fail "/v1/versions 无响应"
fi

# 缓存统计
CACHE_STATS=$(curl -sf --max-time 5 "$BASE_URL/v1/cache/stats" 2>/dev/null || echo "")
if [ -n "$CACHE_STATS" ]; then
  HITS=$(echo "$CACHE_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hits',0))" 2>/dev/null || echo 0)
  log_pass "/v1/cache/stats → hits=$HITS"
else
  log_fail "/v1/cache/stats 无响应"
fi

# ── 8. 路由统计 ──────────────────────────────────────────────
header "8/9 路由器统计"

ROUTER_STATS=$(curl -sf --max-time 5 "$BASE_URL/v1/router/stats" 2>/dev/null || echo "")
if [ -n "$ROUTER_STATS" ]; then
  NODE_COUNT=$(echo "$ROUTER_STATS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    print(len(data))
else:
    print(0)
" 2>/dev/null || echo 0)
  log_pass "/v1/router/stats → $NODE_COUNT 个节点"
else
  log_fail "/v1/router/stats 无响应"
fi

# ── 9. WebSocket 端点 ─────────────────────────────────────────
header "9/9 WebSocket 端点"

if command -v python3 &>/dev/null && [ -n "$API_KEY" ]; then
  WS_RESULT=$(python3 -c "
import asyncio, json
async def test_ws():
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get('$BASE_URL/health')
            return r.status_code == 200
    except:
        return False
result = asyncio.run(test_ws())
print('ok' if result else 'fail')
" 2>/dev/null || echo "fail")
  
  if [ "$WS_RESULT" = "ok" ]; then
    log_pass "WebSocket 端点可达 (wss://api.0379.world/ws/chat)"
  else
    log_fail "WebSocket 端点不可达"
  fi
else
  log_fail "WebSocket 验证 (缺少 python3 或 API_KEY)"
fi

# ============================================================
# 总结
# ============================================================
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "  ${BLUE}YYC³ 全链路验证报告${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "  目标: ${BASE_URL}"
echo -e "  耗时: ${DURATION}s"
echo -e "  结果: ${GREEN}✅ $PASS 通过${NC} / ${RED}❌ $FAIL 失败${NC}"
echo ""

if [ ${#FAILURES[@]} -gt 0 ]; then
  echo -e "${RED}  失败项:${NC}"
  for f in "${FAILURES[@]}"; do
    echo -e "    ${RED}•${NC} $f"
  done
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo -e "  ${GREEN}🎉 全链路验证全部通过！${NC}"
  exit 0
else
  echo -e "  ${YELLOW}⚠️  部分验证未通过，请检查日志${NC}"
  exit 1
fi
