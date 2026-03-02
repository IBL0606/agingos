# AS-IS Evidence Pack (pilotbox)

Dato (UTC): 2026-03-02
Mål: Dokumentere faktisk status på pilot-maskinen uten funksjonelle endringer.

## Status Summary

### ✅ OK
- Docker Compose stack kjører (se `docker-compose-ps.txt`).
- Backend `/health` svarer 200 (se `curl-health.backend.txt`).
- Console proxy `/api/health` svarer 200 (se `curl-health.console-proxy.txt`).
- Console proxy `/api/health/detail` svarer 200 (se `curl-health-detail.console-proxy.txt`).

### ⚠️ DEGRADED
- `/health/detail` viser `overall_status=DEGRADED` pga ingest-lag:
  - `ingest.lag_seconds` over `degraded_seconds` (se `curl-health-detail.backend.txt`).

### 🔎 Observations (data/coverage)
- DB viser at `ha_snapshot` fortsatt kommer inn, men `presence` og `door` stopper tidligere:
  - `db-events-by-category-2h.txt`
  - `db-events-by-category-24h.txt`
- `room_id` er tom (EMPTY) for 100% av `presence` og `door` events siste 24h:
  - `db-presence-roomid-empty-vs-set-24h.txt`
  - `db-door-roomid-empty-vs-set-24h.txt`
- `presence` per rom i 24h viser kun tom `room_id`:
  - `db-presence-by-room-24h.txt`

## Captured Artifacts
- Compose: `docker-compose-ps.txt`, `compose-profiles.txt`
- Logs (tail 200): `docker-compose-logs-backend.tail200.txt`, `docker-compose-logs-console.tail200.txt`, `docker-compose-logs-db.tail200.txt`
- Health: `curl-health.backend.txt`, `curl-health-detail.backend.txt`, `curl-health.console-proxy.txt`, `curl-health-detail.console-proxy.txt`
- DB snapshots: `db-events-by-category-24h.txt`, `db-events-by-category-2h.txt`, `db-presence-by-room-24h.txt`, `db-presence-roomid-empty-vs-set-24h.txt`, `db-door-roomid-empty-vs-set-24h.txt`
