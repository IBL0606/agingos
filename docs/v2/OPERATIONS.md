# OPERATIONS (DRAFT)

Status: **DRAFT**

## Scope: Devbox
This document applies to **Devbox only** (`~/dev/agingos`, Docker Desktop).
Pilot/Prod (MiniPC) is out of scope unless explicitly stated.

## Start/stop (Devbox)

### Localhost-only (DEFAULT / recommended)
This mode binds ports to **127.0.0.1** only (not exposed on LAN):

- Start / reconcile:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
- Verify ports:
  - `docker ps --format "table {{.Names}}\t{{.Ports}}" | rg "agingos-(backend|console|db|ai-bot)-1"`
- Stop:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml down`

### LAN-exposed (OPT-IN, explicit)
This mode exposes ports on **0.0.0.0** (LAN). Use only when explicitly needed:

- Start:
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml up -d`
- Verify ports:
  - `docker ps --format "table {{.Names}}\t{{.Ports}}" | rg "agingos-(backend|console|db|ai-bot)-1"`
- Stop:
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml down`

## Health checks (read-only)
- `GET /health`
- `GET /health/detail` (requires `X-API-Key`)
  - includes ingest diagnostics: `components.ingest.by_category` and `components.ingest.room_id_completeness_24h`
- `GET /debug/scope` (requires `X-API-Key`)

## Evidence capture (read-only)
Canonical Devbox evidence capture:
- `make audit-capture`

Writes a dated evidence pack under:
- `docs/audit/as-is-YYYY-MM-DD-devbox/`

Rule: anything not proven by evidence must be marked **NO_EVIDENCE** or **HYPOTHESIS**.
