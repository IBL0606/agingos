#!/usr/bin/env bash
set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:8000}"
API_KEY="${AGINGOS_API_KEY:-}"

if [ -z "${API_KEY}" ]; then
  echo "ERROR: Set AGINGOS_API_KEY in your environment (no default in repo)."
  exit 1
fi

echo "== /ai/status =="
status_json="$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE}/ai/status")"
echo "${status_json}" | cat
echo

echo "== /ai/insights =="
insights_json="$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE}/ai/insights")"
echo "${insights_json}" | cat
echo

echo "OK"
