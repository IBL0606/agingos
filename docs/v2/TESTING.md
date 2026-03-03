# TESTING (DRAFT)

Status: **DRAFT**

## Ground rules
- Verification must be **read-only** (GET/SELECT/logs/ps/grep).
- No data deletion.
- No mixing Pilot/Prod (MiniPC) into Devbox work.

## Canonical: audit-capture (Devbox)
Run:
- `make audit-capture`

This generates a dated evidence pack under `docs/audit/as-is-YYYY-MM-DD-devbox/` including:
- git metadata
- docker compose ps
- logs tail
- curl GET outputs for /health and /health/detail (including ingest diagnostics fields) and /debug/scope
- DB SELECT summaries (freshness + room_id completeness)
- manifest of exact commands executed

NO_EVIDENCE: the target is introduced in this fixpack and will become the standard way to reduce NO_EVIDENCE claims.
