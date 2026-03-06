# Pilotbox capture template — Fixpack-3 Room Mapping (NO_EVIDENCE)

Status: NO_EVIDENCE (template only)
Scope: Pilotbox/MiniPC — read-only verifikasjon (GET/SELECT/logs/ps)
IKKE: slett data eller endre config
IKKE: gjør DB writes (ingen INSERT/UPDATE/DELETE)

0) Forutsetning
- API key med operator-scope
- Scope: default/default/default
- Stream: prod

Sett:
- API_KEY="<din-key>"

1) Runtime (read-only)
docker compose ps
docker compose logs --tail 200 backend
docker compose logs --tail 200 console
docker compose logs --tail 200 db

2) API (read-only)
BASE="http://127.0.0.1:8000"

curl -sS -i "$BASE/v1/rooms" -H "X-API-Key: $API_KEY" | sed -n '1,160p'
curl -sS -i "$BASE/v1/room_mappings" -H "X-API-Key: $API_KEY" | sed -n '1,200p'
curl -sS -i "$BASE/v1/room_mappings/unknown_sensors?stream_id=prod" -H "X-API-Key: $API_KEY" | sed -n '1,200p'

3) DB: room_id coverage presence/door last 24h (read-only)
DB_CONT="$(docker compose ps -q db)"
docker exec -i "$DB_CONT" psql -U agingos -d agingos -P pager=off -c "
SELECT category,
       COUNT(*) AS total_24h,
       SUM(CASE WHEN room_id IS NULL OR room_id='' THEN 1 ELSE 0 END) AS room_id_empty_24h,
       SUM(CASE WHEN room_id IS NOT NULL AND room_id<>'' THEN 1 ELSE 0 END) AS room_id_set_24h
FROM events
WHERE org_id='default' AND home_id='default' AND subject_id='default'
  AND stream_id='prod'
  AND \"timestamp\" >= now() - interval '24 hours'
  AND category IN ('presence','door')
GROUP BY 1
ORDER BY 1;
"

4) DB: entity_id inventory (read-only)
DB_CONT="$(docker compose ps -q db)"
docker exec -i "$DB_CONT" psql -U agingos -d agingos -P pager=off -c "
SELECT
  category,
  payload->>'entity_id' AS entity_id,
  COUNT(*) AS n,
  MAX(\"timestamp\") AS last_ts
FROM events
WHERE org_id='default' AND home_id='default' AND subject_id='default'
  AND stream_id='prod'
  AND \"timestamp\" >= now() - interval '7 days'
  AND payload->>'entity_id' IS NOT NULL AND payload->>'entity_id' <> ''
  AND category IN ('presence','door')
GROUP BY 1,2
ORDER BY last_ts DESC
LIMIT 100;
"

5) Console (NOTE)
- Åpne: http://<host>:8080/rooms.html
- Romoppsett er en operatørhandling. Evidence-capture her er read-only; mapping-writes må være eksplisitt godkjent.
