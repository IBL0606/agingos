#!/usr/bin/env bash
set -euo pipefail

# Devbox-only. Read-only evidence capture.
# Writes a dated evidence pack to docs/audit/as-is-YYYY-MM-DD-devbox/
# No secrets should be written.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATE_UTC="$(date -u +%Y-%m-%d)"
TS_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OUT="docs/audit/as-is-${DATE_UTC}-devbox"

mkdir -p "$OUT"

run_to_file() {
  local outfile="$1"
  shift
  {
    echo "## TS_UTC=${TS_UTC}"
    echo "## CMD: $*"
    echo
    "$@"
    echo
  } > "${OUT}/${outfile}"
}

cat > "${OUT}/MANIFEST.md" <<MD
# Devbox AS-IS evidence pack (${DATE_UTC})

- TS_UTC: ${TS_UTC}
- Scope: Devbox only (~/dev/agingos, Docker Desktop)
- Rule: read-only verification only (GET/SELECT/logs/ps/grep)

## Contents
- git-rev-parse-head.txt
- git-status-sb.txt
- git-log-1.txt
- env-keys.txt (names only; no values)
- docker-compose-ps.txt
- docker-compose-logs-backend.tail200.txt
- docker-compose-logs-console.tail200.txt
- docker-compose-logs-db.tail200.txt
- curl-health.txt
- curl-health-detail.txt
- curl-debug-scope.txt
- db-events-by-category-24h.txt
- db-roomid-empty-vs-set-24h.txt
MD

# Git meta
run_to_file git-rev-parse-head.txt git rev-parse HEAD
run_to_file git-status-sb.txt git status -sb
run_to_file git-log-1.txt git --no-pager log -n 1 --decorate=short

# Env key names only (no values)
if [[ -f .env ]]; then
  {
    echo "## TS_UTC=${TS_UTC}"
    echo "## Source: .env (keys only)"
    echo
    sed -n 's/^\s*\([A-Za-z_][A-Za-z0-9_]*\)\s*=.*$/\1/p' .env | sort -u
    echo
  } > "${OUT}/env-keys.txt"
else
  {
    echo "## TS_UTC=${TS_UTC}"
    echo "## Source: .env not found"
    echo
  } > "${OUT}/env-keys.txt"
fi

# Docker compose runtime evidence
run_to_file docker-compose-ps.txt docker compose ps
run_to_file docker-compose-logs-backend.tail200.txt docker compose logs --no-color --tail=200 backend || true
run_to_file docker-compose-logs-console.tail200.txt docker compose logs --no-color --tail=200 console || true
run_to_file docker-compose-logs-db.tail200.txt docker compose logs --no-color --tail=200 db || true

# HTTP health (read-only) if BASE_URL and API_KEY are set
BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"

if [[ -n "${BASE_URL}" ]]; then
  run_to_file curl-health.txt curl -sS "${BASE_URL}/health"
  if [[ -n "${API_KEY}" ]]; then
    run_to_file curl-health-detail.txt curl -sS "${BASE_URL}/health/detail" -H "X-API-Key: ${API_KEY}"
    run_to_file curl-debug-scope.txt curl -sS "${BASE_URL}/debug/scope" -H "X-API-Key: ${API_KEY}"
  else
    {
      echo "## TS_UTC=${TS_UTC}"
      echo "## NOTE: API_KEY not set; skipping /health/detail and /debug/scope"
      echo
    } > "${OUT}/curl-health-detail.txt"
    cp -a "${OUT}/curl-health-detail.txt" "${OUT}/curl-debug-scope.txt"
  fi
else
  {
    echo "## TS_UTC=${TS_UTC}"
    echo "## NOTE: BASE_URL not set; skipping curl outputs"
    echo
  } > "${OUT}/curl-health.txt"
  cp -a "${OUT}/curl-health.txt" "${OUT}/curl-health-detail.txt"
  cp -a "${OUT}/curl-health.txt" "${OUT}/curl-debug-scope.txt"
fi

# DB read-only checks (best-effort)
DB_CONT="$(docker compose ps -q db 2>/dev/null || true)"
if [[ -n "${DB_CONT}" ]]; then
  run_to_file db-events-by-category-24h.txt docker exec -i "${DB_CONT}" psql -U agingos -d agingos -P pager=off -c "
SELECT category,
       COUNT(*) AS n_24h,
       MAX(\"timestamp\") AS max_ts_24h
FROM events
WHERE \"timestamp\" >= now() - interval '24 hours'
GROUP BY 1
ORDER BY max_ts_24h DESC NULLS LAST;
" || true

  run_to_file db-roomid-empty-vs-set-24h.txt docker exec -i "${DB_CONT}" psql -U agingos -d agingos -P pager=off -c "
SELECT category,
       SUM(CASE WHEN COALESCE(room_id,'')='' THEN 1 ELSE 0 END) AS room_id_empty,
       SUM(CASE WHEN COALESCE(room_id,'')<>'' THEN 1 ELSE 0 END) AS room_id_set
FROM events
WHERE category IN ('presence','door')
  AND \"timestamp\" >= now() - interval '24 hours'
GROUP BY 1
ORDER BY 1;
" || true
else
  {
    echo "## TS_UTC=${TS_UTC}"
    echo "## NOTE: could not resolve db container (docker compose ps -q db returned empty)"
    echo
  } > "${OUT}/db-events-by-category-24h.txt"
  cp -a "${OUT}/db-events-by-category-24h.txt" "${OUT}/db-roomid-empty-vs-set-24h.txt"
fi

echo "OK: wrote evidence pack to ${OUT}"
