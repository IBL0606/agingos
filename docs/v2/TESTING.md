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

## MUST-1 setup verification (fresh install vs upgrade)
Use the exact commands in `docs/v2/SETUP_TRUTH.md`.

Truth rule: `/health/detail` is data-aware; empty fresh install can return `overall_status=ERROR` with `no events found for this scope`.
