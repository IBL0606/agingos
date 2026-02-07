#!/usr/bin/env bash
set -euo pipefail

echo "== scheduler anomalies_job next_run_time =="
curl -fsS http://127.0.0.1:8000/anomalies/scheduler_jobs | python3 -c "import sys,json; jobs=json.load(sys.stdin); j=[x for x in jobs if x.get('id')=='anomalies_job']; print(j[0] if j else 'MISSING')"
echo

echo "== runner freshness (age seconds) + last_scored_bucket_start =="
curl -fsS http://127.0.0.1:8000/anomalies/runner_status | python3 -c "import sys,json; from datetime import datetime,timezone; rs=json.load(sys.stdin); ts=rs.get('last_ok_at'); dt=datetime.fromisoformat(ts.replace('Z','+00:00')); age=(datetime.now(timezone.utc)-dt).total_seconds(); print(f\"age_s={age:.1f} last_scored_bucket_start={rs.get('last_scored_bucket_start','')} counts={rs.get('last_counts')}\")"
echo

echo "== DB: dupes room+start_ts (expect 0) =="
docker compose exec -T db psql -U agingos -d agingos -Atc "
SELECT COUNT(*) FROM (
  SELECT 1
  FROM anomaly_episodes
  GROUP BY room, start_ts
  HAVING COUNT(*) > 1
) s;
"
echo

echo "== DB: rooms with >1 active episode (expect 0) =="
docker compose exec -T db psql -U agingos -d agingos -Atc "
SELECT COUNT(*) FROM (
  SELECT 1
  FROM anomaly_episodes
  WHERE active IS TRUE
  GROUP BY room
  HAVING COUNT(*) > 1
) s;
"
