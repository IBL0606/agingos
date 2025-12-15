#!/usr/bin/env bash
#examples/scripts/smoke_test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "== AgingOS smoke test =="
echo "BASE_URL: $BASE_URL"
echo

# Helper: pretty fail message
fail() {
  echo "FAIL: $1" >&2
  exit 1
}

# 1) Health
echo "[1/5] GET /health"
health_json="$(curl -sS "$BASE_URL/health" || true)"
echo "$health_json" | grep -q '"status"' || fail "/health did not return expected JSON"
echo "OK"
echo

# 2) POST /event
# Use a fixed UUID so it's deterministic; timestamp is now-ish (UTC).
EVENT_ID="00000000-0000-0000-0000-000000000001"
NOW_UTC="2025-12-15T10:00:00Z"


echo "[2/5] POST /event"
post_json="$(curl -sS -X POST "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"$EVENT_ID\",
    \"timestamp\": \"$NOW_UTC\",
    \"category\": \"motion\",
    \"payload\": {\"state\": \"on\", \"smoke\": true}
  }" || true)"

echo "$post_json" | grep -q '"received"' || fail "POST /event did not return expected JSON"
echo "OK"
echo

# 3) GET /events?limit=10
echo "[3/5] GET /events?limit=10"
events_json="$(curl -sS "$BASE_URL/events?limit=10" || true)"
echo "$events_json" | grep -q "$EVENT_ID" || fail "Posted event id not found in /events?limit=10"
echo "OK"
echo

# 4) GET /events?category=motion&limit=10
echo "[4/5] GET /events?category=motion&limit=10"
motion_json="$(curl -sS "$BASE_URL/events?category=motion&limit=10" || true)"
echo "$motion_json" | grep -q "$EVENT_ID" || fail "Posted event id not found in /events filtered by category"
echo "OK"
echo

# 5) GET /events with time window (since/until)
# Use a small window around NOW_UTC. (Since = now-1h, Until = now+1h)
SINCE_UTC="$(date -u -d "1 hour ago" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || true)"
UNTIL_UTC="$(date -u -d "1 hour" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || true)"

# Fallback for systems without GNU date -d (rare in Linux, but just in case)
if [[ -z "${SINCE_UTC}" || -z "${UNTIL_UTC}" ]]; then
  # Use a wider static window if date arithmetic not available
  SINCE_UTC="2000-01-01T00:00:00Z"
  UNTIL_UTC="2100-01-01T00:00:00Z"
fi

echo "[5/5] GET /events?since=...&until=...&limit=10"
tw_json="$(curl -sS "$BASE_URL/events?since=${SINCE_UTC}&until=${UNTIL_UTC}&limit=10" || true)"
echo "$tw_json" | grep -q "$EVENT_ID" || fail "Posted event id not found in /events time-window query"
echo "OK"
echo

# 6) GET /deviations/evaluate (R-001 boundary test, until is exclusive)
echo "[6/6] GET /deviations/evaluate (R-001, until eksklusiv)"

# Window ends exactly at the event timestamp -> event should NOT be included -> expect 1 deviation
dev_a="$(curl -sS "$BASE_URL/deviations/evaluate?since=2025-12-15T08:00:00Z&until=2025-12-15T10:00:00Z" || true)"
echo "$dev_a" | jq -e 'type=="array" and length==1 and .[0].rule_id=="R-001" and ((.[0].evidence|length)==0)' >/dev/null \
  || fail "/deviations/evaluate expected 1 deviation for window [08:00,10:00)"

# Window ends 1 second after event timestamp -> event is included -> expect 0 deviations
dev_b="$(curl -sS "$BASE_URL/deviations/evaluate?since=2025-12-15T08:00:00Z&until=2025-12-15T10:00:01Z" || true)"
echo "$dev_b" | jq -e 'type=="array" and length==0' >/dev/null \
  || fail "/deviations/evaluate expected 0 deviations for window [08:00,10:00:01)"

echo "OK"
echo


echo "SUCCESS: Smoke test passed."
