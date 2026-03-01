#!/usr/bin/env bash
# examples/scripts/smoke_test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

API_KEY_HEADER=()

# If AGINGOS_API_KEY isn't set in the environment, try to load it from .env (repo root)
if [[ -z "${AGINGOS_API_KEY:-}" && -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

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
  # (Safety) NEVER clear real events unless explicitly requested AND running in isolated smoke stack
  # Guardrails:
  # - Only allow TRUNCATE when COMPOSE_PROJECT_NAME=smoke
  # - Only allow TRUNCATE when BASE_URL is on dedicated smoke port (default 18000)
  # - Require explicit acknowledgement
  SMOKE_OK_TO_TRUNCATE=0
  if [[ "${COMPOSE_PROJECT_NAME:-}" == "smoke" && "${BASE_URL:-}" =~ ^http://localhost:18000($|/) ]]; then
    SMOKE_OK_TO_TRUNCATE=1
  fi

  if [[ "${SMOKE_TRUNCATE:-0}" == "1" ]]; then
    if [[ "$SMOKE_OK_TO_TRUNCATE" == "1" && "${SMOKE_I_KNOW_WHAT_IM_DOING:-}" == "YES" ]]; then
      echo "WARN: SMOKE_TRUNCATE=1 -> TRUNCATE events (isolated smoke stack)"
      docker compose exec -T db psql -U agingos -d agingos -c "TRUNCATE TABLE events;" >/dev/null || true
    else
      echo "WARN: SMOKE_TRUNCATE=1 ignored (refusing to truncate outside isolated smoke stack)." >&2
      echo "      Require: COMPOSE_PROJECT_NAME=smoke BASE_URL=http://localhost:18000 SMOKE_I_KNOW_WHAT_IM_DOING=YES" >&2
    fi
  else
    echo "INFO: skipping TRUNCATE (set SMOKE_TRUNCATE=1 to enable in isolated smoke stack)"
  fi

# 1) Health
echo "[1/8] GET /health"
health_json=""
for ((i=1; i<=10; i++)); do
  health_json="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/health" || true)"
  echo "$health_json" | grep -q '"status"' && break
  sleep 0.5
done
echo "$health_json" | grep -q '"status"' || fail "/health did not return expected JSON"
echo "OK"
echo

# 2) POST /event (safe-by-default)
  EVENT_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ "${SMOKE_DETERMINISTIC:-0}" == "1" ]]; then
  EVENT_ID="00000000-0000-0000-0000-000000000001"
    MOTION_R1_ID="00000000-0000-0000-0000-000000000011"
  DOOR_R2_ID="00000000-0000-0000-0000-000000000110"
  MOTION_R2_ID="00000000-0000-0000-0000-000000000111"
  DOOR_R3_ID="00000000-0000-0000-0000-000000000210"
  MOTION_R3_ID="00000000-0000-0000-0000-000000000211"
else
  EVENT_ID="$(cat /proc/sys/kernel/random/uuid)"
    MOTION_R1_ID="$(cat /proc/sys/kernel/random/uuid)"
  DOOR_R2_ID="$(cat /proc/sys/kernel/random/uuid)"
  MOTION_R2_ID="$(cat /proc/sys/kernel/random/uuid)"
  DOOR_R3_ID="$(cat /proc/sys/kernel/random/uuid)"
  MOTION_R3_ID="$(cat /proc/sys/kernel/random/uuid)"
fi

echo "[2/8] POST /event (motion)"
  post_json="$(curl -sS -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
    -H "Content-Type: application/json" \
    --data-binary @- <<EOF || true
{
  "id": "$EVENT_ID",
  "timestamp": "$EVENT_TS",
  "category": "motion",
  "payload": {"state":"on","smoke":true}
}
EOF
)"
echo "$post_json" | grep -q '"received"' || fail "POST /event did not return expected JSON"
echo "OK"
echo

# Extra events for R-002 test (door open at night), and motion in the same window so R-001 does NOT trigger there
  # R-001 window anchor event (ensure "0 deviations" is true for the morning window)
  curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
    -H "Content-Type: application/json" \
    -d '{
      "id":"'"$MOTION_R1_ID"'",
      "timestamp":"2025-12-15T10:00:00Z",
      "category":"motion",
      "payload":{"state":"on","smoke":true}
    }' >/dev/null

curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"'"$DOOR_R2_ID"'",
    "timestamp":"2025-12-15T02:00:00Z",
    "category":"door",
    "payload":{"state":"open","door":"front","smoke":true}
  }' >/dev/null

curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"'"$MOTION_R2_ID"'",
    "timestamp":"2025-12-15T01:30:00Z",
    "category":"motion",
    "payload":{"state":"on","smoke":true}
  }' >/dev/null

# Extra events for R-003 test (daytime door open; NO motion in next 10 minutes; motion later to avoid R-001)
curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"'"$DOOR_R3_ID"'",
    "timestamp":"2025-12-15T14:00:00Z",
    "category":"door",
    "payload":{"state":"open","door":"front","smoke":true}
  }' >/dev/null

curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"'"$MOTION_R3_ID"'",
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
SINCE_UTC="$(date -u -d "${EVENT_TS} - 10 minutes" +%Y-%m-%dT%H:%M:%SZ)"
UNTIL_UTC="$(date -u -d "${EVENT_TS} + 10 minutes" +%Y-%m-%dT%H:%M:%SZ)"
tw_json="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/events?since=$SINCE_UTC&until=$UNTIL_UTC&limit=10" || true)"
echo "$tw_json" | grep -q "$EVENT_ID" || fail "Posted event id not found in /events time-window query"
echo "OK"
echo



# 6) GET /deviations/evaluate (R-001 boundary test, until is exclusive)
echo "[6/8] GET /deviations/evaluate (R-001, until eksklusiv)"

# Window ends exactly at the event timestamp -> event NOT included -> expect 1 deviation (R-001)
dev_a="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T08:00:00Z&until=2025-12-15T10:00:00Z" || true)"
echo "$dev_a" | jq -e 'type=="array" and (map(.rule_id) | index("R-001") != null)' >/dev/null \
  || fail "/deviations/evaluate expected R-001 present for window [08:00,10:00)"

# Window ends 1 second after event timestamp -> event included -> expect 0 deviations
dev_b="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T08:00:00Z&until=2025-12-15T10:00:01Z" || true)"
echo "$dev_b" | jq -e 'type=="array" and (map(.rule_id) | index("R-001") == null)' >/dev/null \
  || fail "/deviations/evaluate expected NO R-001 for window [08:00,10:00:01)"

echo "OK"
echo

# 7) GET /deviations/evaluate (R-002 or R-003 should trigger; R-001 should NOT trigger in this window)
echo "[7/8] GET /deviations/evaluate (R-002/R-003 trigges, R-001 trigges ikke)"

dev_r2="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T01:00:00Z&until=2025-12-15T03:00:00Z" || true)"
echo "$dev_r2" | jq -e '
  type=="array"
  and (map(.rule_id) | (index("R-002") != null or index("R-003") != null))
  and (map(.rule_id) | index("R-001") == null)
' >/dev/null || fail "Expected R-002 or R-003 and not R-001 in window 01:00–03:00"

echo "OK"
echo

# 8) GET /deviations/evaluate (R-003 should trigger; R-001 and R-002 should NOT trigger in this window)
# --- R-003 prep (smoke) ---
# Goal:
# - Prevent R-001 by having motion somewhere in the window
# - Trigger R-003 by having a front door open, then NO motion/presence in followup window
curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"00000000-0000-0000-0000-000000000300",
    "timestamp":"2025-12-15T13:55:00Z",
    "category":"motion",
    "payload":{"state":"on","smoke":true,"note":"r003_pre_motion"}
  }' >/dev/null || true

curl -sf -X POST "${API_KEY_HEADER[@]}" "$BASE_URL/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id":"00000000-0000-0000-0000-000000000301",
    "timestamp":"2025-12-15T14:00:00Z",
    "category":"door",
    "payload":{"state":"open","door":"front","smoke":true,"note":"r003_front_open"}
  }' >/dev/null || true

echo "[8/8] GET /deviations/evaluate (R-003 trigges, R-001/R-002 trigges ikke)"

dev_r3="$(curl -sS "${API_KEY_HEADER[@]}" "$BASE_URL/deviations/evaluate?since=2025-12-15T13:50:00Z&until=2025-12-15T14:20:00Z" || true)"
  # Assertion policy:
  # - In isolated deterministic smoke mode (clean DB): expect ONLY R-003
  # - Otherwise (shared/dev DB): require R-003 present (avoid flakiness)
  if [[ "${SMOKE_DETERMINISTIC:-0}" == "1" && "$SMOKE_OK_TO_TRUNCATE" == "1" && "${SMOKE_TRUNCATE:-0}" == "1" ]]; then
    echo "$dev_r3" | jq -e 'type=="array" and (map(.rule_id)|length==1) and (map(.rule_id)[0]=="R-003")' >/dev/null \
      || fail "Expected only R-003 in window 13:50–14:20 (deterministic isolated smoke)"
  else
    echo "$dev_r3" | jq -e 'type=="array" and (map(.rule_id)|index("R-003")!=null)' >/dev/null \
      || fail "Expected R-003 present in window 13:50–14:20"
  fi

echo "OK"
echo

echo "SUCCESS: Smoke test passed."
