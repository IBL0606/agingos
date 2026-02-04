#!/usr/bin/env bash
set -euo pipefail

API_KEY="${AGINGOS_API_KEY:-}"
if [ -z "${API_KEY}" ]; then
  echo "ERROR: Set AGINGOS_API_KEY in your environment (no default in repo)."
  exit 1
fi

# Deterministic dev test window (matches our verified GUI/proxy checks)
UNTIL="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
COMMON_QS="until=${UNTIL}&window_days=14&z_threshold=0&min_abs_increase=0&meaningful_recent_floor=0&quiet_min_room_baseline_nights=1&quiet_min_room_baseline_mean=0"

echo "== Bot direct anomalies =="
curl -s "http://127.0.0.1:8010/v1/anomalies?${COMMON_QS}" \
| jq -e '.findings[] | select(.id|test("^anomaly-night-(quiet-room-|activity-)")) | .title' >/dev/null
echo "OK: bot direct quiet living"

echo "== Via backend proxy anomalies =="
curl -s -H "X-API-Key: ${API_KEY}" "http://127.0.0.1:8000/ai/anomalies?${COMMON_QS}" \
| jq -e '.findings[] | select(.id|test("^anomaly-night-(quiet-room-|activity-)")) | .title' >/dev/null
echo "OK: backend proxy quiet living"

echo "OK"
