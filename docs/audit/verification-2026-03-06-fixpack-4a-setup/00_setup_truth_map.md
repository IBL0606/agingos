# Fixpack-4A setup truth map (pre-change)

Status: NO_EVIDENCE for runtime checks in this container.

Verified by repo inspection:
- `make up` runs `docker compose up -d --build`, waits for db readiness, then runs `docker compose exec -T backend alembic -c alembic.ini upgrade head`.
- `docker-compose.yml` has no host port publishing by default (safe-by-default).
- host-reachable ports require overlays (`docker-compose.dev.yml` localhost-only or `docker-compose.expose.yml` LAN).
- `.env.example` exists and defaults `AGINGOS_AUTH_MODE=off`.
- `/health/detail` degrades to ERROR when scoped event count is zero (`n == 0` branch).

Runtime verification blockers in this environment:
- `docker` CLI is not installed (`command not found`), so fresh-install and upgrade runtime checks cannot be executed here.
