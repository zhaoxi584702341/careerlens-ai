#!/usr/bin/env bash
# =============================================================================
# CareerLens AI 端到端冒烟测试脚本
#
# 用途：对已启动的四层链路（compose 或本地）打真实请求，
#       校验 HTTP 200 + 关键字段 + match.score ∈ [0,100]。
# 被 CI 的 e2e 作业调用；也可本地手动执行。
#
# 用法：
#   BFF_BASE=http://localhost:3000 ./scripts/smoke-test.sh
#
# 退出码：0 = 全部通过；1 = 有失败用例。
# =============================================================================
set -uo pipefail

BFF_BASE="${BFF_BASE:-http://localhost:3000}"
PY_BASE="${PY_BASE:-http://localhost:8000}"
SAMPLE_DIR="${SAMPLE_DIR:-$(cd "$(dirname "$0")/.." && pwd)/samples}"

PASS=0
FAIL=0

log()  { printf '\033[36m[smoke]\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m  PASS\033[0m %s\n' "$*"; PASS=$((PASS + 1)); }
bad()  { printf '\033[31m  FAIL\033[0m %s\n' "$*"; FAIL=$((FAIL + 1)); }

# 用 python 做 JSON 断言（避免依赖 jq）
json_get() { # <json> <python-expr-on-`d`>
  python3 -c "import sys,json;d=json.load(sys.stdin);print($1)" 2>/dev/null
}

# ---------------------------------------------------------------------------
# 0. 等待 BFF 就绪
# ---------------------------------------------------------------------------
log "等待 BFF 就绪：${BFF_BASE}/api/history"
for i in $(seq 1 30); do
  if curl -fsS "${BFF_BASE}/api/history" >/dev/null 2>&1; then
    ok "BFF 已就绪（第 ${i} 次探测）"
    break
  fi
  if [ "$i" -eq 30 ]; then bad "BFF 在 30 次探测后仍不可达"; fi
  sleep 2
done

# ---------------------------------------------------------------------------
# 1. Python /health
# ---------------------------------------------------------------------------
log "GET ${PY_BASE}/health"
resp="$(curl -fsS "${PY_BASE}/health" 2>/dev/null)" || resp=""
if [ -n "$resp" ] && [ "$(echo "$resp" | json_get "d.get('status')")" = "ok" ]; then
  ok "Python /health status=ok"
else
  bad "Python /health 异常：${resp:-<empty>}"
fi

# ---------------------------------------------------------------------------
# 2. BFF /api/analyze-resume（短简历）
# ---------------------------------------------------------------------------
RESUME="$(cat "${SAMPLE_DIR}/resume_short.txt" 2>/dev/null | head -c 4000)"
log "POST ${BFF_BASE}/api/analyze-resume"
resp="$(curl -fsS -X POST "${BFF_BASE}/api/analyze-resume" \
  -H 'Content-Type: application/json' \
  --data-binary "$(python3 -c 'import json,sys;print(json.dumps({"resume_text":sys.argv[1]}))' "$RESUME")" 2>/dev/null)" || resp=""
if [ -n "$resp" ]; then
  n="$(echo "$resp" | json_get "len(d.get('keywords',[]))")"
  s="$(echo "$resp" | json_get "d.get('score')")"
  if [ -n "$s" ] && [ "$s" -ge 0 ] 2>/dev/null && [ "$s" -le 100 ] 2>/dev/null; then
    ok "analyze-resume：keywords=${n}，score=${s}（∈[0,100]）"
  else
    bad "analyze-resume：score 越界或缺失 => ${s:-<none>}"
  fi
else
  bad "analyze-resume：请求失败"
fi

# ---------------------------------------------------------------------------
# 3. BFF /api/match-job（短简历 + Java JD）
# ---------------------------------------------------------------------------
JD="$(cat "${SAMPLE_DIR}/jd_java.txt" 2>/dev/null | head -c 4000)"
log "POST ${BFF_BASE}/api/match-job"
resp="$(curl -fsS -X POST "${BFF_BASE}/api/match-job" \
  -H 'Content-Type: application/json' \
  --data-binary "$(python3 -c 'import json,sys;print(json.dumps({"resume_text":sys.argv[1],"job_description":sys.argv[2]}))' "$RESUME" "$JD")" 2>/dev/null)" || resp=""
if [ -n "$resp" ]; then
  ms="$(echo "$resp" | json_get "d.get('match_score')")"
  if [ -n "$ms" ] && [ "$ms" -ge 0 ] 2>/dev/null && [ "$ms" -le 100 ] 2>/dev/null; then
    ok "match-job：match_score=${ms}（∈[0,100]）"
  else
    bad "match-job：match_score 越界或缺失 => ${ms:-<none>}"
  fi
else
  bad "match-job：请求失败"
fi

# ---------------------------------------------------------------------------
# 4. BFF /api/optimize-resume
# ---------------------------------------------------------------------------
log "POST ${BFF_BASE}/api/optimize-resume"
resp="$(curl -fsS -X POST "${BFF_BASE}/api/optimize-resume" \
  -H 'Content-Type: application/json' \
  --data-binary "$(python3 -c 'import json,sys;print(json.dumps({"resume_text":sys.argv[1],"job_description":sys.argv[2]}))' "$RESUME" "$JD")" 2>/dev/null)" || resp=""
if [ -n "$resp" ] && [ "$(echo "$resp" | json_get "isinstance(d.get('suggestions'),list)")" = "True" ]; then
  ok "optimize-resume：suggestions 为列表"
else
  bad "optimize-resume：响应结构异常 => ${resp:-<empty>}"
fi

# ---------------------------------------------------------------------------
# 5. BFF /api/radar
# ---------------------------------------------------------------------------
log "POST ${BFF_BASE}/api/radar"
resp="$(curl -fsS -X POST "${BFF_BASE}/api/radar" \
  -H 'Content-Type: application/json' \
  --data-binary "$(python3 -c 'import json,sys;print(json.dumps({"resume":sys.argv[1],"jd":sys.argv[2]}))' "$RESUME" "$JD")" 2>/dev/null)" || resp=""
if [ -n "$resp" ] && [ "$(echo "$resp" | json_get "isinstance(d.get('dimensions'),list)")" = "True" ]; then
  ok "radar：dimensions 为列表"
else
  bad "radar：响应结构异常 => ${resp:-<empty>}"
fi

# ---------------------------------------------------------------------------
# 6. BFF /api/history（SQLite 持久化）
# ---------------------------------------------------------------------------
log "GET ${BFF_BASE}/api/history"
resp="$(curl -fsS "${BFF_BASE}/api/history" 2>/dev/null)" || resp=""
if [ -n "$resp" ] && [ "$(echo "$resp" | json_get "isinstance(d.get('records'),list)")" = "True" ]; then
  ok "history：records 为列表（total=$(echo "$resp" | json_get "d.get('total')")）"
else
  bad "history：响应结构异常 => ${resp:-<empty>}"
fi

# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
printf '\n\033[1m[smoke] 汇总：PASS=%d  FAIL=%d\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
log "全部冒烟用例通过 ✅"
