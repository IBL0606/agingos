# Gap Analysis — SoT Claims v1 vs AS-IS Evidence Pack (pilotbox)

Date: 2026-03-02  
Scope: `docs/audit/sot-claims-v1.md` vs evidence captured under `docs/audit/as-is-2026-03-02-pilotbox/` only.  
Method: Claims are marked from available evidence only; no inferred or uncaptured proof is used.

## Status legend
- **PASS**: claim is directly supported by captured evidence.
- **PARTIAL**: some aspects are supported, but full claim is not proven.
- **FAIL**: captured evidence contradicts the claim or shows a material policy breach.
- **NO_EVIDENCE**: evidence pack does not contain sufficient proof.

## Summary counts
- **PASS:** 2
- **PARTIAL:** 8
- **FAIL:** 1
- **NO_EVIDENCE:** 29

## Claim-by-claim mapping

| Claim ID | Status | Evidence | Notes | Fix suggestion | Priority |
|---|---|---|---|---|---|
| SOT-001 | PARTIAL | `docker-compose-ps.txt` | Stack is up, but no evidence of `.env.example` copy nor `up -d --build` flow. | Capture bootstrap transcript from clean shell including env-file check and compose config/build run. | PILOT_SHOULD |
| SOT-002 | NO_EVIDENCE | no evidence captured | No Alembic/migration proof in current artifacts. | Next capture (read-only): `docker compose logs --tail=400 backend | grep -E 'alembic|upgrade head'` and `docker compose exec -T backend alembic -c alembic.ini current`. | PILOT_BLOCKER |
| SOT-003 | NO_EVIDENCE | no evidence captured | No artifact shows field override compose config validation. | Next capture: `docker compose -f docker-compose.yml -f docker-compose.field.yml config >/dev/null && echo OK_FIELD_CONFIG`. | PILOT_SHOULD |
| SOT-004 | NO_EVIDENCE | no evidence captured | No `.env` dump proving `AGINGOS_AUTH_MODE=api_key` and key env setup. | Next capture: `grep -E '^AGINGOS_AUTH_MODE=|^AGINGOS_API_KEYS=|^AGINGOS_API_KEY=' .env`. | PILOT_BLOCKER |
| SOT-005 | PASS | `docker-compose-logs-backend.tail200.txt`, `docker-compose-logs-console.tail200.txt`, `docker-compose-logs-db.tail200.txt` | Runtime logs are present from multiple services via compose logs artifacts. | Keep log capture in each audit pack and include timestamps + tail size metadata. | MVP_LATER |
| SOT-006 | NO_EVIDENCE | no evidence captured | Retention policy (30d events) is a docs/config claim; no matching policy artifact in pack. | Next capture: `sed -n '/Retention/,/Logs/p' README.md` and `sed -n '/### Events/,/### Deviations/p' docs/policies/retention.md`. | PILOT_SHOULD |
| SOT-007 | NO_EVIDENCE | no evidence captured | No proof of 180d deviations policy or OPEN/ACK retention handling. | Next capture: `sed -n '/deviations/,/Status/p' README.md` and `sed -n '/### Deviations/,/### Backups/p' docs/policies/retention.md`. | PILOT_SHOULD |
| SOT-008 | NO_EVIDENCE | no evidence captured | No grep artifact confirms absence of automatic retention job. | Next capture: `rg -n 'retention job|retention' README.md docs/policies/retention.md backend/services`. | PILOT_SHOULD |
| SOT-009 | PASS | `curl-health.backend.txt` | Direct HTTP 200 response for `/health` with JSON status payload. | Keep this endpoint in baseline health evidence bundle. | PILOT_SHOULD |
| SOT-010 | PARTIAL | `docker-compose-logs-backend.tail200.txt`, `curl-health.backend.txt` | `/events`, `/rules`, and `/health` are evidenced; `/deviations`, `/deviations/evaluate`, `/event`, and full CRUD subset are not proven. | Add OpenAPI path dump and curls for each endpoint family in evidence capture script. | PILOT_BLOCKER |
| SOT-011 | NO_EVIDENCE | no evidence captured | No captured POST `/event` acceptance test with UTC-aware timestamp payload. | Next capture: execute documented `curl -X POST /event` with `timestamp=...Z` and store status+body. | PILOT_BLOCKER |
| SOT-012 | NO_EVIDENCE | no evidence captured | No captured negative test for naive timestamp rejection. | Next capture: execute documented naive timestamp POST and save status+body to artifact. | PILOT_BLOCKER |
| SOT-013 | NO_EVIDENCE | no evidence captured | Window contract `[since, until)` is not evidenced in runtime or docs snapshot artifacts. | Next capture: `sed -n '/Vinduskontrakt/,/Helse/p' README.md` and `sed -n '/## Vinduskontrakt/,/## Felter/p' docs/contracts/rule-config.md`. | PILOT_SHOULD |
| SOT-014 | NO_EVIDENCE | no evidence captured | No DB status enumeration for OPEN/ACK/CLOSED in deviations. | Next capture: `docker compose exec -T db psql -U agingos -d agingos -c "SELECT DISTINCT status FROM deviations ORDER BY status;"`. | PILOT_BLOCKER |
| SOT-015 | NO_EVIDENCE | no evidence captured | No uniqueness check output for active deviation rows per `(rule_id, subject_key)`. | Next capture: documented SQL HAVING query for active duplicates and store raw table output. | PILOT_BLOCKER |
| SOT-016 | NO_EVIDENCE | no evidence captured | Reopen policy behavior requires scenario evidence; not captured. | Next capture: run `make statusflow` and preserve full output/logs for lifecycle transitions. | PILOT_SHOULD |
| SOT-017 | NO_EVIDENCE | no evidence captured | No `/deviations` response captured to validate sort order by severity/last_seen_at. | Next capture: `curl -sS -H "X-API-Key: ${AGINGOS_API_KEY}" "http://localhost:8000/deviations" | jq -r '.[] | [.severity,.last_seen_at] | @tsv'`. | PILOT_SHOULD |
| SOT-018 | PARTIAL | `curl-health-detail.backend.txt`, `curl-health-detail.console-proxy.txt` | Scheduler appears to run at 5-minute interval, but no `rules.yaml` evidence proves source-of-truth key. | Capture `yq '.scheduler.interval_minutes' backend/config/rules.yaml` in future pack. | PILOT_SHOULD |
| SOT-019 | NO_EVIDENCE | no evidence captured | No artifact shows `enabled_in_scheduler` per rule in config. | Next capture: `yq '.rules | to_entries[] | {rule: .key, enabled_in_scheduler: .value.enabled_in_scheduler}' backend/config/rules.yaml`. | PILOT_SHOULD |
| SOT-020 | NO_EVIDENCE | no evidence captured | No direct config proof for R-001 disabled / R-002,R-003 enabled baseline. | Next capture: `yq '.rules."R-001".enabled_in_scheduler, .rules."R-002".enabled_in_scheduler, .rules."R-003".enabled_in_scheduler' backend/config/rules.yaml`. | PILOT_SHOULD |
| SOT-021 | PARTIAL | `curl-health-detail.backend.txt`, `curl-health-detail.console-proxy.txt` | Health detail scope includes `subject_id:"default"`, but this does not directly prove scheduler/persist default_subject_key config. | Add explicit config capture: `yq '.scheduler.default_subject_key' backend/config/rules.yaml`. | PILOT_SHOULD |
| SOT-022 | NO_EVIDENCE | no evidence captured | No code-path grep artifact proving shared rule-engine authority across API + scheduler flows. | Next capture: `rg -n 'evaluate_rules|rule_engine' backend/routes backend/services/scheduler.py backend/services/rule_engine.py`. | PILOT_BLOCKER |
| SOT-023 | NO_EVIDENCE | no evidence captured | No evaluation artifact demonstrating R-001 semantics. | Next capture: documented `/deviations/evaluate` call for R-001 window case and save JSON output. | PILOT_SHOULD |
| SOT-024 | NO_EVIDENCE | no evidence captured | No config artifact proving R-002 night window parameterization. | Next capture: `yq '.rules."R-002".params.night_window' backend/config/rules.yaml`. | PILOT_SHOULD |
| SOT-025 | NO_EVIDENCE | no evidence captured | No config artifact proving R-003 follow-up minutes default. | Next capture: `yq '.rules."R-003".params.followup_minutes' backend/config/rules.yaml`. | PILOT_SHOULD |
| SOT-026 | PARTIAL | `db-events-by-category-24h.txt`, `db-events-by-category-2h.txt` | Runtime data shows `door` events, but `motion` is not observed and code-register proof is absent. | Capture code grep evidence for category register and a short events sample including motion channel tests. | PILOT_SHOULD |
| SOT-027 | NO_EVIDENCE | no evidence captured | Mapping policy (“presence mapped to motion”) is not evidenced in pack. | Next capture: `sed -n '/Kategori-register/,/Payload/p' docs/mapping/sensor-event-mapping.md`. | PILOT_SHOULD |
| SOT-028 | NO_EVIDENCE | no evidence captured | No payload sample/doc extract proving `door:"front"` + `state:"open|closed"` convention. | Next capture: `sed -n '/Dørkontakt ytterdør/,/Bruk i regler/p' docs/mapping/sensor-event-mapping.md` and one sanitized event sample. | PILOT_SHOULD |
| SOT-029 | NO_EVIDENCE | no evidence captured | No scenario runner contract evidence for table resets pre-run. | Next capture: `rg -n 'scenario-reset|deviations_v1|deviations' docs/testing/scenario-format.md Makefile examples/scripts/scenario_runner.py`. | PILOT_SHOULD |
| SOT-030 | NO_EVIDENCE | no evidence captured | No docs excerpt confirming pass_condition options only `contains|exact`. | Next capture: `sed -n '/pass_condition/,/ExpectedDeviation/p' docs/testing/scenario-format.md`. | MVP_LATER |
| SOT-031 | NO_EVIDENCE | no evidence captured | No grep evidence for `utcnow()` as single deterministic now source. | Next capture: `rg -n 'def utcnow|utcnow\(' backend/util/time.py backend/services backend/routes backend/tests`. | MVP_LATER |
| SOT-032 | PARTIAL | `docker-compose-logs-backend.tail200.txt` | JSONL entries with UTC `ts` and scheduler events are present; “stable mandatory field set” not fully validated. | Add log schema check command that validates required scheduler fields across N log lines. | PILOT_SHOULD |
| SOT-033 | PARTIAL | `docker-compose-logs-backend.tail200.txt` | No obvious `Authorization`/`X-API-Key`/`DATABASE_URL` leakage in captured tail; sample size is limited. | Increase scan window (e.g., tail 1000+) and include explicit deny-list grep artifact output. | PILOT_BLOCKER |
| SOT-034 | NO_EVIDENCE | no evidence captured | No backup directory listing in evidence pack. | Next capture: `ls -1 backups | grep -E '^agingos_[0-9]{8}T[0-9]{6}Z\.sql$'`. | PILOT_SHOULD |
| SOT-035 | NO_EVIDENCE | no evidence captured | No restore transcript proving destructive schema reset-before-import path. | Next capture: `make restore-db 2>&1 | sed -n '1,80p'` (read-only transcript capture). | PILOT_SHOULD |
| SOT-036 | NO_EVIDENCE | no evidence captured | Stack status is known, but no artifact proves runbook path `/opt/agingos`. | Next capture: `test -d /opt/agingos && echo OK_REPO_PATH` and `cd /opt/agingos && docker compose ps`. | PILOT_SHOULD |
| SOT-037 | PARTIAL | `docker-compose-ps.txt`, `curl-health.console-proxy.txt`, `curl-health-detail.console-proxy.txt` | Nginx front-door on `:8080` and `/api/health`/`/api/health/detail` are evidenced, but `/api/ai/status` and events/proposals checks are missing. | Extend sanity curl capture to all runbook-listed endpoints behind console proxy. | PILOT_BLOCKER |
| SOT-038 | NO_EVIDENCE | no evidence captured | `ai-bot` container is running, but `.env` proof of `AI_BOT_ENABLED=true` is absent. | Next capture: `grep -E '^AI_BOT_ENABLED=' .env`. | PILOT_SHOULD |
| SOT-039 | NO_EVIDENCE | no evidence captured | No architecture-doc excerpt or network trace proving HA→LAN→mini-PC `/event` flow. | Next capture: `sed -n '/Datakjede/,/Nettverk/p' docs/hw/architecture.md` plus one ingress request sample from HA source IP. | MVP_LATER |
| SOT-040 | FAIL | `docker-compose-ps.txt` | Backend port is published on `0.0.0.0:8000`; no evidence of segment restrictions, conflicting with perimeter hardening intent. | Enforce network ACL/firewall policy and capture allowed/disallowed segment curl results in next evidence cycle. | PILOT_BLOCKER |

## Fix Plan

1. Build a single `make audit-capture` read-only target that runs all SoT verify commands and writes timestamped artifacts.
2. Add explicit auth-mode evidence capture (`AGINGOS_AUTH_MODE`, key vars) with secret-safe masking.
3. Capture OpenAPI path inventory and endpoint smoke tests for `/event`, `/events`, `/deviations`, `/deviations/evaluate`, `/rules`, `/health`.
4. Add timestamp contract tests (UTC-aware accepted, naive rejected) as reusable curl fixtures in audit pack.
5. Capture deviations DB invariants (status domain and active uniqueness query) on every pilot audit.
6. Capture scheduler config evidence from `backend/config/rules.yaml` (interval, enabled flags, default subject key).
7. Add rule semantics evidence mini-suite for R-001/R-002/R-003 using deterministic windows and saved outputs.
8. Add logging deny-list scan artifact over larger window (`tail 1000+`) and fail audit if secrets/headers appear.
9. Add log schema check for scheduler JSONL mandatory fields.
10. Capture backup/restore operational evidence (`backups` naming + restore transcript) in controlled maintenance window.
11. Expand runbook proxy checks to include `/api/ai/status` and events/proposals endpoints.
12. Add perimeter evidence capture from both allowed and disallowed network segments for `:8000`.
13. Include `/opt/agingos` location checks in operational evidence for MiniPC alignment.
14. Add category-register evidence (code grep + runtime sample) to reconcile `motion`/`door`/`presence` expectations.
15. Add architecture flow evidence snippet (doc excerpt + representative ingress log line from HA-originated traffic).
