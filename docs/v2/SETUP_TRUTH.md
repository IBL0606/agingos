# SETUP TRUTH (ACTIVE)

Status: **ACTIVE**

Scope: **Dev repo only** (`/workspace/agingos`).

Rule: install/upgrade is **per-home scope** (`org_id`, `home_id`, `subject_id`) and must be verified with command evidence. If not verified, mark **NO_EVIDENCE**.

## MUST-1: fresh install vs upgrade (do not mix)

### Fresh install (new DB volume)

#### Runtime bring-up truth
- `make up` uses **base compose only** (`docker compose up -d --build`), then waits for DB and runs `alembic upgrade head`.
- Base compose does not publish host ports by default.
- If host path `127.0.0.1:8000` is needed, start with dev overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

#### Verification sequence (fresh install, full PASS target)

```bash
docker compose down -v --remove-orphans
make up
docker compose exec -T backend alembic -c alembic.ini current

# activate scope mapping for dev-key-2 (sha256 precomputed)
docker compose exec -T db psql -U agingos -d agingos -c "
INSERT INTO api_key_scopes (org_id, home_id, subject_id, role, api_key_hash, user_id, active)
VALUES ('default','default','default','operator','966c44be82076d2c2ad29390d50c34034a35056007f29606f6457b02af023402','ba7cd3c0-a65b-4fe4-a564-b27607a791c8',true)
ON CONFLICT (api_key_hash) DO UPDATE SET active=true, org_id=EXCLUDED.org_id, home_id=EXCLUDED.home_id, subject_id=EXCLUDED.subject_id, role=EXCLUDED.role, user_id=EXCLUDED.user_id;
"

# seed scoped ingest data: one fresh event (ingest lag OK) + one yesterday event (baseline window)
docker compose exec -T db psql -U agingos -d agingos -c "
INSERT INTO events (event_id, timestamp, category, payload, org_id, home_id, subject_id, stream_id, room_id)
VALUES
  ('fix4a-now-1', NOW() AT TIME ZONE 'utc', 'presence', '{\"state\":\"on\"}', 'default', 'default', 'default', 'prod', 'stue'),
  ('fix4a-yday-1', ((NOW() AT TIME ZONE 'Europe/Oslo')::date - 1 + time '12:00') AT TIME ZONE 'Europe/Oslo', 'presence', '{\"state\":\"on\"}', 'default', 'default', 'default', 'prod', 'stue')
ON CONFLICT DO NOTHING;
"

# build baseline in-repo (migration-provisioned functions)
docker compose exec -T db psql -U agingos -d agingos -c "
SELECT *
FROM public.run_baseline_nightly('ba7cd3c0-a65b-4fe4-a564-b27607a791c8'::uuid, 0.1, 0.25, 1);
"

docker compose exec -T backend curl -sS http://127.0.0.1:8000/health

docker compose exec -T backend curl -sS \
  -H "X-API-Key: dev-key-2" \
  http://127.0.0.1:8000/health/detail

docker compose logs --tail=200 backend
```

Expected truth after baseline bootstrap support:
- `/health` returns `{"status":"ok"}`.
- `/health/detail` requires an active `api_key_scopes` mapping for the presented API key.
- With seeded scoped ingest + successful `run_baseline_nightly(...)`, `/health/detail` can reach `overall_status="OK"`.
- Scheduler/anomalies runner must not repeatedly fail with transaction-aborted loop from invalid `baseline_model_status.user_id` query.
- If baseline build is skipped, `/health/detail` remains data-aware and can stay `ERROR/DEGRADED` (valid behavior).

### Upgrade (existing home data)

```bash
docker compose pull || true
docker compose up -d --build
docker compose exec -T backend alembic -c alembic.ini upgrade head
docker compose exec -T backend alembic -c alembic.ini current
docker compose exec -T backend curl -sS \
  -H "X-API-Key: dev-key-2" \
  http://127.0.0.1:8000/health/detail
```

Expected truth:
- `alembic upgrade head` is idempotent.
- `/health/detail` output depends on current scoped data freshness/content and must be read as observed output, not assumed `OK`.

## Verification evidence paths

- Fixpack-4A base: `docs/audit/verification-2026-03-06-fixpack-4a-setup/`
- Fixpack-4A follow-up (scheduler root-cause fix): `docs/audit/verification-2026-03-06-fixpack-4a-scheduler-followup/`
- Fixpack-4A final follow-up (baseline bootstrap path): `docs/audit/verification-2026-03-06-fixpack-4a-final-setup-pass/`
