#!/usr/bin/env bash
# examples/scripts/smoke_test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

API_KEY_HEADER=()
if [[ -n "${AGINGOS_API_KEY:-}" ]]; then
  API_KEY_HEADER=(-H "X-API-Key: ${AGINGOS_API_KEY}")
fi

echo "== AgingOS smoke test =="
echo "BASE_URL: $BASE_URL"
echo

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

echo "[0/8] DB ready (docker compose db)"
for i in $(seq 1 30); do
  if docker compose exec -T db psql -U agingos -d agingos -c "select 1;" >/dev/null 2>&1; then
    echo "OK"
    break
  fi
  sleep 1
done

# (Recommended) deterministic run: clear events so fixed IDs always work
docker compose exec -T db psql -U agingos -d agingos -c "TRUNCATE TABLE events;" >/dev/null || true

# 1) Health
echo "[1/8] GET /health"
health_json="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/health" || true)"
echo "$health_json" | grep -q '"status"' || fail "/health did not return expected JSON"
echo "OK"
echo

# 2) POST /event (deterministic)
EVENT_ID="00000000-0000-0000-0000-000000000001"
EVENT_TS="2025-12-15T10:00:00Z"

echo "[2/8] POST /event (motion)"
post_json="$(curl -sS -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"$EVENT_ID\",
    \"timestamp\": \"$EVENT_TS\",
    \"category\": \"motion\",
    \"payload\": {\"state\": \"on\", \"smoke\": true}
  }" || true)"
echo "$post_json" | grep -q '"received"' || fail "POST /event did not return expected JSON"
echo "OK"
echo

# Extra events for R-002 test (door open at night), and motion in the same window so R-001 does NOT trigger there
curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"00000000-0000-0000-0000-000000000110",
    "timestamp":"2025-12-15T02:00:00Z",
    "category":"door",
    "payload":{"state":"open","door":"front","smoke":true}
  }' >/dev/null

curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"00000000-0000-0000-0000-000000000111",
    "timestamp":"2025-12-15T01:30:00Z",
    "category":"motion",
    "payload":{"state":"on","smoke":true}
  }' >/dev/null

# Extra events for R-003 test (daytime door open; NO motion in next 10 minutes; motion later to avoid R-001)
curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"00000000-0000-0000-0000-000000000210",
    "timestamp":"2025-12-15T14:00:00Z",
    "category":"door",
    "payload":{"state":"open","door":"front","smoke":true}
  }' >/dev/null

curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"00000000-0000-0000-0000-000000000211",
    "timestamp":"2025-12-15T14:15:00Z",
    "category":"motion",
    "payload":{"state":"on","smoke":true}
  }' >/dev/null

# 3) GET /events?limit=10
echo "[3/8] GET /events?limit=10"
events_json="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/events?limit=10" || true)"
echo "$events_json" | grep -q "$EVENT_ID" || fail "Posted event id not found in /events?limit=10"
echo "OK"
echo

# 4) GET /events?category=motion&limit=10
echo "[4/8] GET /events?category=motion&limit=10"
motion_json="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/events?category=motion&limit=10" || true)"
echo "$motion_json" | grep -q "$EVENT_ID" || fail "Posted event id not found in /events filtered by category"
echo "OK"
echo

# 5) GET /events with time window that includes EVENT_TS
echo "[5/8] GET /events?since=...&until=...&limit=10"
SINCE_UTC="2025-12-15T09:00:00Z"
UNTIL_UTC="2025-12-15T11:00:00Z"
tw_json="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/events?since=${SINCE_UTC}&until=${UNTIL_UTC}&limit=10" || true)"
echo "$tw_json" | grep -q "$EVENT_ID" || fail "Posted event id not found in /events time-window query"
echo "OK"
echo

# 6) GET /deviations/evaluate (R-001 boundary test, until is exclusive)
echo "[6/8] GET /deviations/evaluate (R-001, until eksklusiv)"

# Window ends exactly at the event timestamp -> event NOT included -> expect 1 deviation (R-001)
dev_a="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T08:00:00Z&until=2025-12-15T10:00:00Z" || true)"
echo "$dev_a" | jq -e 'type=="array" and length==1 and .[0].rule_id=="R-001" and ((.[0].evidence|length)==0)' >/dev/null \
  || fail "/deviations/evaluate expected 1 deviation for window [08:00,10:00)"

# Window ends 1 second after event timestamp -> event included -> expect 0 deviations
dev_b="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T08:00:00Z&until=2025-12-15T10:00:01Z" || true)"
echo "$dev_b" | jq -e 'type=="array" and length==0' >/dev/null \
  || fail "/deviations/evaluate expected 0 deviations for window [08:00,10:00:01)"

echo "OK"
echo

# 7) GET /deviations/evaluate (R-002 should trigger; R-001 should NOT trigger in this window)
echo "[7/8] GET /deviations/evaluate (R-002 trigges, R-001 trigges ikke)"

dev_r2="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T01:00:00Z&until=2025-12-15T03:00:00Z" || true)"
echo "$dev_r2" | jq -e '
  type=="array"
  and (map(.rule_id) | index("R-002") != null)
  and (map(.rule_id) | index("R-001") == null)
' >/dev/null || fail "Expected R-002 and not R-001 in window 01:00–03:00"

echo "OK"
echo

# 8) GET /deviations/evaluate (R-003 should trigger; R-001 and R-002 should NOT trigger in this window)
echo "[8/8] GET /deviations/evaluate (R-003 trigges, R-001/R-002 trigges ikke)"

dev_r3="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T13:50:00Z&until=2025-12-15T14:20:00Z" || true)"
echo "$dev_r3" | jq -e '
  type=="array"
  and length==1
  and .[0].rule_id=="R-003"
' >/dev/null || fail "Expected only R-003 in window 13:50–14:20"

echo "OK"
echo

echo "SUCCESS: Smoke test passed."
