#!/usr/bin/env bash
set -euo pipefail

: "${BASE_URL:?set BASE_URL}"
: "${API_KEY:?set API_KEY}"

curl -sS "$@" -H "X-API-Key: ${API_KEY}"
