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


## MUST-2 health card verification (Fixpack-4B)
Evidence pack proposal:
- `docs/audit/verification-2026-03-06-fixpack-4b-health-card/`

Required captures:
1) CHECK-HEALTH-01 (`/health/detail` truth)
- `curl -sS http://127.0.0.1:8000/health/detail -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-4b-health-card/10_health_detail_raw.json`
- `jq '{overall_status, reasons, ingest:.components.ingest, baseline:.components.baseline, worker:(.components.worker // .components.anomalies_runner // .components.scheduler)}' docs/audit/verification-2026-03-06-fixpack-4b-health-card/10_health_detail_raw.json | tee docs/audit/verification-2026-03-06-fixpack-4b-health-card/11_health_detail_focus.json`

2) CHECK-HEALTH-02 (Console rendering truth vs API)
- `curl -sS http://127.0.0.1:8080/index.html | tee docs/audit/verification-2026-03-06-fixpack-4b-health-card/20_console_index_html.txt`
- Capture screenshot from Console Status page after loading API key + refresh. Save as `docs/audit/verification-2026-03-06-fixpack-4b-health-card/21_console_health_card.png`.
- Add short comparison note in `docs/audit/verification-2026-03-06-fixpack-4b-health-card/30_check_health_02.md` with:
  - overall color + text shown
  - explanation text shown
  - next-step bullets shown
  - component statuses shown
  - explicit statement for every missing field rendered as `Ukjent / mangler data`

Truth rule:
- If `/health/detail` is missing a component or thresholds, evidence must show that Console rendered unknown/missing state explicitly.
