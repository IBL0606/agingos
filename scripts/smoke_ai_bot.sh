#!/usr/bin/env bash
set -euo pipefail

API_KEY="${AGINGOS_API_KEY:-}"
if [ -z "${API_KEY}" ]; then
  echo "ERROR: Set AGINGOS_API_KEY in your environment (no default in repo)."
  exit 1
fi

echo "== Bot direct =="
curl -s http://127.0.0.1:8010/healthz | cat
echo
curl -s http://127.0.0.1:8010/v1/capabilities | cat
echo

echo "== Via backend =="
curl -s -H "X-API-Key: ${API_KEY}" http://127.0.0.1:8000/ai/status | cat
echo
curl -s -H "X-API-Key: ${API_KEY}" \
  "http://127.0.0.1:8000/ai/insights?since=2026-01-01T00:00:00Z&until=2026-01-02T00:00:00Z" | cat
echo

echo "OK"
