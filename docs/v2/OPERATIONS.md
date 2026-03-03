# OPERATIONS (DRAFT)

Status: **DRAFT**

## Scope: Devbox
This document applies to **Devbox only** (`~/dev/agingos`, Docker Desktop).

## Start/stop (Devbox)
NO_EVIDENCE: final dev-start command will be confirmed after `docker-compose.dev.yml` is introduced.

Planned:
- `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
- `docker compose ps`
- `docker compose logs --tail=200 backend`

## Health checks (read-only)
- `GET /health`
- `GET /health/detail` (requires `X-API-Key`)

## Evidence capture (read-only)
Use `make audit-capture` to generate a dated evidence pack under:
- `docs/audit/as-is-YYYY-MM-DD-devbox/`

NO_EVIDENCE: the capture script/target is introduced in this fixpack and will provide the canonical commands+outputs.
