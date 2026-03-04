# Pilotbox (MiniPC) — Read-only evidence capture (TEMPLATE)

Status: TEMPLATE (NO_EVIDENCE until executed on MiniPC)

## Rules (must follow)
- Read-only only: GET/SELECT/logs/ps/grep and docker compose ls/config.
- No data deletion.
- Capture outputs into docs/audit/as-is-YYYY-MM-DD-pilotbox/ with a copy of this MANIFEST.

## Required captures

### 1) Compose + runtime
Run on MiniPC:
- cd /opt/agingos
- docker compose ls
- docker compose config > /tmp/compose.resolved.yml
- head -n 120 /tmp/compose.resolved.yml
- docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"
- docker compose logs backend/console/db/ai-bot/notification-worker --tail 200
- systemctl cat agingos.service

Save outputs as files:
- docker-compose-ls.txt
- docker-compose-config.head120.txt
- docker-ps.ports.txt
- docker-compose-logs.tail200.txt
- systemd-agingos.service.txt

### 2) Health + scope (read-only)
- curl -sS http://127.0.0.1:8000/health
- curl -sS http://127.0.0.1:8000/health/detail -H "X-API-Key: $API_KEY"
- curl -sS http://127.0.0.1:8000/debug/scope -H "X-API-Key: $API_KEY"

Save as:
- curl-health.txt
- curl-health-detail.txt
- curl-debug-scope.txt

### 3) DB (read-only SELECT)

By category (last 24h, scoped + stream_id=prod):
SQL:
SELECT category,
       COUNT(*) AS n_24h,
       MAX("timestamp") AS max_ts_24h
FROM events
WHERE org_id='default' AND home_id='default' AND subject_id='default'
  AND stream_id='prod'
  AND "timestamp" >= now() - interval '24 hours'
GROUP BY 1
ORDER BY max_ts_24h DESC NULLS LAST;

room_id completeness (presence/door/ha_snapshot, last 24h):
SQL:
SELECT category,
       COUNT(*) AS total_24h,
       COUNT(*) FILTER (WHERE COALESCE(room_id,'')='') AS room_id_empty_24h,
       COUNT(*) FILTER (WHERE COALESCE(room_id,'')<>'') AS room_id_set_24h,
       MAX("timestamp") AS max_ts_24h
FROM events
WHERE org_id='default' AND home_id='default' AND subject_id='default'
  AND stream_id='prod'
  AND "timestamp" >= now() - interval '24 hours'
  AND category IN ('presence','door','ha_snapshot')
GROUP BY 1
ORDER BY max_ts_24h DESC NULLS LAST;

Save as:
- db-events-by-category-24h.txt
- db-roomid-completeness-24h.txt

## Notes
- If MiniPC has not been upgraded yet, do not claim “post-upgrade”. Use correct date + context.
- Anything not proven by files in the evidence pack must be labeled NO_EVIDENCE or HYPOTHESIS.
