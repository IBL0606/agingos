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


## MUST-3 weekly report verification (Fixpack-5)
Evidence pack proposal:
- `docs/audit/verification-2026-03-06-fixpack-5-must-3-weekly-report/`

Required captures:
1) CHECK-REPORT-01 (non-technical weekly page exists)
- `curl -sS http://127.0.0.1:8080/report.html | tee docs/audit/verification-2026-03-06-fixpack-5-must-3-weekly-report/10_report_html.txt`
- Verify `Ukesammendrag (for ikke-tekniske)` is present.

2) CHECK-REPORT-02 (four required sections)
- `rg -n "Data inn|Romdekning|Alarmer|Endringer" docs/audit/verification-2026-03-06-fixpack-5-must-3-weekly-report/10_report_html.txt | tee docs/audit/verification-2026-03-06-fixpack-5-must-3-weekly-report/11_sections_present.txt`

3) CHECK-REPORT-03 (real data vs fallback/no-evidence separation)
- Open `/report.html`, press `Oppdater rapport`, and verify each section shows exactly one truth label: `REAL`, `TEMPLATE/FALLBACK`, or `NO_EVIDENCE`.
- Export `Last ned driftpakke (JSON)` and verify `weekly_report` exists in exported JSON.
- If runtime stack is unavailable, record `NO_EVIDENCE` explicitly.

## MUST-4 pilot alarms verification (Fixpack-6)
Evidence pack proposal:
- `docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/`

### CHECK-RULES-01 (explicit pilot rule pack)
- `curl -sS http://127.0.0.1:8000/v1/rules/pilot-pack -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/10_rules_pilot_pack.json`
- `jq '.rules[] | {rule_id,name,description,severity,scheduler_enabled,cooldown_grouping}' docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/10_rules_pilot_pack.json | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/11_rules_pilot_pack_focus.json`

Truth checks:
- cooldown must be explicit (`NONE` if absent; no inferred cooldown)
- grouping must match existing active dedupe only

### CHECK-RULES-02 (quiet hours / override / anti-spam)
- `curl -sS http://127.0.0.1:8000/v1/notification/policy -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/20_policy_get.json`
- `curl -sS http://127.0.0.1:8000/v1/notification/policy/audit -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/21_policy_audit.json`
- `rg -n "policy_defer|override_until|idempotency_key|ON CONFLICT|do NOT bump attempt_n|mode not in" tools/notification_worker.py | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/22_worker_policy_truth_rg.txt`

If runtime outbox exercise is available on dev, add SQL before/after proving:
- policy defer keeps `attempt_n` unchanged
- duplicate idempotency insert does not create duplicate delivery rows

If unavailable, mark runtime proof as NO_EVIDENCE.

### CHECK-RULES-03 (ACK/CLOSE lifecycle for at least 2 alarms)
- `curl -sS "http://127.0.0.1:8000/v1/deviations?status=OPEN&limit=50" -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/30_deviations_open_before.json`
- Choose two `deviation_id` values: A and B from the open list.
- `curl -sS -X PATCH "http://127.0.0.1:8000/v1/deviations/<A>" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"status":"ACK"}' | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/31_deviation_A_ack.json`
- `curl -sS -X PATCH "http://127.0.0.1:8000/v1/deviations/<B>" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"status":"CLOSED"}' | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/32_deviation_B_closed.json`
- `curl -sS "http://127.0.0.1:8000/v1/deviations?limit=50" -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/33_deviations_after.json`

Truth rule:
- If dedicated deviation status audit/history is absent, explicitly record `NO_EVIDENCE`.
