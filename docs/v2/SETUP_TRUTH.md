# SETUP TRUTH (ACTIVE)

Status: **ACTIVE**

Scope: **Dev repo only** (`/workspace/agingos`).

Rule: install/upgrade is **per-home scope** (`org_id`, `home_id`, `subject_id`) and must be verified with command evidence. If not verified, mark **NO_EVIDENCE**.

## MUST-1: fresh install vs upgrade (do not mix)

### Fresh install (new DB volume)
Command sequence:

```bash
docker compose down -v --remove-orphans
make up
docker compose ps
docker compose exec -T backend alembic -c alembic.ini current
docker compose exec -T backend curl -sS http://127.0.0.1:8000/health
docker compose exec -T backend curl -sS http://127.0.0.1:8000/health/detail
```

Expected truth:
- `make up` runs `alembic upgrade head` automatically.
- `/health` should return `{"status":"ok"}` when backend is up.
- `/health/detail` is runtime/data-aware and may be `overall_status=ERROR` when no scoped events exist (this is valid on empty installs).

Code evidence for the empty-install health/detail behavior:
- `if n == 0: ... status = "ERROR" ... reason "no events found for this scope"`.

### Upgrade (existing home data)
Command sequence:

```bash
docker compose pull || true
docker compose up -d --build
docker compose exec -T backend alembic -c alembic.ini upgrade head
docker compose exec -T backend alembic -c alembic.ini current
docker compose exec -T backend curl -sS http://127.0.0.1:8000/health/detail
```

Expected truth:
- `alembic upgrade head` is idempotent.
- `/health/detail` output depends on current scoped data freshness/content and must be read as observed output, not assumed `OK`.

## Verification evidence path for Fixpack-4A

- `docs/audit/verification-2026-03-06-fixpack-4a-setup/`

Current run status in this container:
- Runtime execution is **NO_EVIDENCE** because Docker CLI is unavailable (`command not found`).
- Repo-truth mapping is captured in the same evidence pack.
