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

### CHECK-RULES-02 runtime unblock (notification_policy base table)
Apply on dev DB before policy runtime checks:
- `docker compose exec -T db psql -U agingos -d agingos -f /workspace/backend/sql/p1_6_notification_policy_base.sql | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/23_apply_notification_policy_base_sql.txt`
- `docker compose exec -T db psql -U agingos -d agingos -f /workspace/backend/sql/p1_6_notification_policy_audit.sql | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/24_apply_notification_policy_audit_sql.txt`

Then verify API/runtime:
- `curl -sS http://127.0.0.1:8000/v1/notification/policy -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/25_policy_get_after_base.json`
- `curl -sS -X POST http://127.0.0.1:8000/v1/notification/policy/partner_override -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"override_until_utc":"2030-01-01T00:00:00Z"}' | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/26_partner_override_post.json`
- `curl -sS http://127.0.0.1:8000/v1/notification/policy/audit -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/27_policy_audit_after_override.json`

Anti-spam evidence (existing worker/outbox scope):
- `docker compose exec -T db psql -U agingos -d agingos -c "\d public.notification_deliveries" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/28_notification_deliveries_schema.txt`
- `docker compose exec -T db psql -U agingos -d agingos -c "SELECT id, status, attempt_n, next_attempt_at, last_error, idempotency_key FROM public.notification_outbox ORDER BY id DESC LIMIT 20;" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/29_outbox_recent.txt`

If docker compose service names/paths differ on dev, capture equivalent command output and mark adaptation explicitly.

### CHECK-RULES-02 completion pass (base schema + helper conflict fix)
Problem/fix truth:
- Runtime was previously blocked by missing `public.notification_policy`.
- Helper function conflict target ambiguity was fixed by using `ON CONFLICT ON CONSTRAINT notification_policy_pkey` in `set_notification_policy_override(...)`.

Exact dev commands (full verification):

1) Apply schema + helper/audit SQL in order
- `docker compose exec -T db psql -U agingos -d agingos -f /workspace/backend/sql/p1_6_notification_policy_base.sql | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/42_apply_base.sql.txt`
- `docker compose exec -T db psql -U agingos -d agingos -f /workspace/backend/sql/p1_6_notification_policy_audit.sql | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/43_apply_audit_helper.sql.txt`

2) Verify policy endpoints
- `curl -sS http://127.0.0.1:8000/v1/notification/policy -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/44_policy_get.json`
- `curl -sS -X POST http://127.0.0.1:8000/v1/notification/policy/partner_override -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"override_until_utc":"2030-01-01T00:00:00Z"}' | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/45_partner_override.json`
- `curl -sS http://127.0.0.1:8000/v1/notification/policy/audit -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/46_policy_audit.json`

3) Prove QUIET/NIGHT defer does not bump attempt_n
- `docker compose exec -T db psql -U agingos -d agingos -c "INSERT INTO public.notification_policy(org_id,home_id,subject_id,mode,quiet_start_local,quiet_end_local,tz,updated_by) VALUES ('default','default','default','QUIET','00:00','23:59','Europe/Oslo','dev:test') ON CONFLICT ON CONSTRAINT notification_policy_pkey DO UPDATE SET mode=EXCLUDED.mode, quiet_start_local=EXCLUDED.quiet_start_local, quiet_end_local=EXCLUDED.quiet_end_local, tz=EXCLUDED.tz, override_until=NULL, updated_by=EXCLUDED.updated_by, updated_at=now();" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/47_policy_set_quiet_full_day.txt`
- `docker compose exec -T db psql -U agingos -d agingos -c "INSERT INTO public.notification_outbox(org_id,home_id,subject_id,route_type,route_key,destination,message_type,severity,idempotency_key,payload,bypass_policy,status,next_attempt_at,attempt_n,max_attempts) VALUES ('default','default','default','db','dev-route','dev-dest','MUST4_TEST','INFO','must4-defer-001','{}'::jsonb,false,'PENDING',now(),0,5) RETURNING id,attempt_n,status,next_attempt_at;" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/48_outbox_insert_defer_case.txt`
- `docker compose exec -T backend python /workspace/tools/notification_worker.py 1 | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/49_worker_run_defer_case.txt`
- `docker compose exec -T db psql -U agingos -d agingos -c "SELECT id,status,attempt_n,last_error,next_attempt_at FROM public.notification_outbox WHERE idempotency_key='must4-defer-001';" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/50_outbox_after_defer_case.txt`

4) Prove override_until bypasses quiet defer
- `docker compose exec -T db psql -U agingos -d agingos -c "UPDATE public.notification_policy SET override_until = now() + interval '2 hours', updated_at=now(), updated_by='dev:test-override' WHERE org_id='default' AND home_id='default' AND subject_id='default';" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/51_policy_set_override_future.txt`
- `docker compose exec -T db psql -U agingos -d agingos -c "INSERT INTO public.notification_outbox(org_id,home_id,subject_id,route_type,route_key,destination,message_type,severity,idempotency_key,payload,bypass_policy,status,next_attempt_at,attempt_n,max_attempts) VALUES ('default','default','default','db','dev-route','dev-dest','MUST4_TEST','INFO','must4-override-001','{}'::jsonb,false,'PENDING',now(),0,5) RETURNING id,attempt_n,status;" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/52_outbox_insert_override_case.txt`
- `docker compose exec -T backend python /workspace/tools/notification_worker.py 1 | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/53_worker_run_override_case.txt`
- `docker compose exec -T db psql -U agingos -d agingos -c "SELECT id,status,attempt_n,delivered_at,acked_at,last_error FROM public.notification_outbox WHERE idempotency_key='must4-override-001';" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/54_outbox_after_override_case.txt`

5) Anti-spam/idempotency evidence (existing implementation only)
- `docker compose exec -T db psql -U agingos -d agingos -c "SELECT outbox_id,org_id,home_id,subject_id,route_type,route_key,idempotency_key,COUNT(*) AS n FROM public.notification_deliveries WHERE idempotency_key='must4-override-001' GROUP BY 1,2,3,4,5,6,7;" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/55_delivery_rows_override_case.txt`
- `docker compose exec -T backend python /workspace/tools/notification_worker.py 1 | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/56_worker_rerun_idempotency_case.txt`
- `docker compose exec -T db psql -U agingos -d agingos -c "SELECT outbox_id,org_id,home_id,subject_id,route_type,route_key,idempotency_key,COUNT(*) AS n FROM public.notification_deliveries WHERE idempotency_key='must4-override-001' GROUP BY 1,2,3,4,5,6,7;" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/57_delivery_rows_after_rerun.txt`

Expected evidence outputs:
- defer case: `status='RETRY'`, `attempt_n=0`, `last_error` starts with `policy_defer:`.
- override case: `status='DELIVERED'` with non-null `delivered_at`/`acked_at`.
- idempotency case: grouped delivery row count remains `1` for the same idempotency key.

### CHECK-RULES-02 final schema-alignment step (notification_outbox)
Third blocker history in order:
- (a) missing `notification_policy` base table
- (b) helper upsert conflict ambiguity
- (c) missing `notification_outbox.last_error` / `dead_letter_reason` columns required by worker defer/retry/dead-letter paths

Apply outbox alignment on dev (pick one):
- Preferred (migration path):
  - `docker compose exec -T backend alembic upgrade head | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/59_alembic_upgrade_head.txt`
- Explicit SQL patch path (if DB already at head but missing cols):
  - `docker compose exec -T db psql -U agingos -d agingos -c "ALTER TABLE public.notification_outbox ADD COLUMN IF NOT EXISTS last_error text NULL, ADD COLUMN IF NOT EXISTS dead_letter_reason text NULL;" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/60_outbox_align_alter.txt`

Verify aligned columns exist:
- `docker compose exec -T db psql -U agingos -d agingos -c "SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='notification_outbox' AND column_name IN ('last_error','dead_letter_reason') ORDER BY column_name;" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/61_outbox_columns_check.txt`

Re-run runtime proof sequence after alignment:
- QUIET defer case commands: files `47`..`50` above.
- Override bypass commands: files `51`..`54` above.
- Idempotency re-run/grouped count commands: files `55`..`57` above.

Expected outputs remain:
- defer case => `status='RETRY'`, `attempt_n=0`, `last_error` starts with `policy_defer:`
- override case => `status='DELIVERED'` with non-null `delivered_at` and `acked_at`
- idempotency case => grouped delivery count stays `1` for same `idempotency_key`
