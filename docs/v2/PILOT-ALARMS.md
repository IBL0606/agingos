# PILOT ALARMS (DRAFT)

Status: **DRAFT**

## Scope
- MUST-4 only (pilot alarm system truth).
- Devbox/repo truth only in this fixpack.
- No MiniPC/customer change in this document.

## 1) Explicit pilot rule pack
Truth source:
- API endpoint: `GET /v1/rules/pilot-pack`
- Backed by:
  - `backend/config/rules.yaml` (`enabled_in_scheduler`, lookback/expire)
  - `backend/services/rules/registry.py` (`R-001..R-010` names/descriptions)
  - `rules` table severity if present, otherwise default `2/MEDIUM`

Returned fields per rule:
- `rule_id`
- `name`
- `description`
- `severity` (`score`, `label`, `source`)
- `scheduler_enabled`
- `cooldown_grouping`

Truth constraints:
- `cooldown` is reported as `NONE` because no cooldown field exists in `backend/config/rules.yaml`.
- `grouping` is reported as active OPEN/ACK dedupe by rule+subject scope because this is what scheduler/deviation model proves.
- No hidden cooldown/aggregation semantics are claimed.

## 2) Quiet-hours / override / anti-spam behavior
Truth source:
- `tools/notification_worker.py`
- `backend/routes/notification_policy.py`

Proven behavior:
- Policy mode gate:
  - Only `QUIET` / `NIGHT` can defer delivery.
- Quiet window defer:
  - In quiet window, worker sets outbox row to `RETRY` and computes `next_attempt_at` at quiet-end local time converted to UTC.
  - Policy defer reason string is `policy_defer:<MODE>`.
- Override:
  - If `override_until > utcnow()`, delivery is allowed (no quiet defer).
  - Partner API to set override: `POST /v1/notification/policy/partner_override`.
- Anti-spam / idempotency:
  - Delivery receipt insert uses unique key `(org_id, home_id, subject_id, route_type, route_key, idempotency_key)` with `ON CONFLICT DO NOTHING`.
  - This proves delivery idempotency at outbox receipt layer.
- Attempt counter truth:
  - On policy defer, worker does **not** increment `attempt_n`.

NO_EVIDENCE in this fixpack:
- No new claim that policy creates/open-dedupes alarms themselves; this path is for outbox delivery behavior.

## 3) ACK/CLOSE lifecycle
Truth source:
- UI path: `services/console/alarms.html`
- API path: `GET /v1/deviations`, `PATCH /v1/deviations/{id}`
- Model: `backend/models/deviation.py`

Proven behavior:
- Allowed statuses are `OPEN`, `ACK`, `CLOSED`.
- Console action buttons call `PATCH /v1/deviations/{id}` with status payload.
- Active dedupe exists for OPEN/ACK rows per `(rule_id, subject_key)` (partial unique index).
- Scheduler stale-close logic closes old OPEN/ACK rows based on `expire_after_minutes`.

NO_EVIDENCE / not claimed:
- Automatic reopen semantics as a standalone API transition are not claimed here.
- Dedicated ACK/CLOSE audit trail table for deviations is NO_EVIDENCE in current repo.


## 4) Schema dependency for notification policy runtime
Runtime dependency (dev/repo truth):
- `GET /v1/notification/policy` and partner override require base table `public.notification_policy`.
- Base table SQL (additive): `backend/sql/p1_6_notification_policy_base.sql`.
- Audit/override helpers remain in: `backend/sql/p1_6_notification_policy_audit.sql`.

Apply order on dev:
1. base table SQL
2. audit/helper SQL

NO_EVIDENCE:
- Runtime PASS must be proven in a live dev stack after applying both SQL files.

## 5) CHECK-RULES-02 blocker and helper-fix truth
- Blocker found on dev runtime: `/v1/notification/policy` could fail when `public.notification_policy` did not exist.
- Blocker-fix added: `backend/sql/p1_6_notification_policy_base.sql`.
- Additional bug found on dev runtime in helper function upsert conflict target.
- Helper-fix: `set_notification_policy_override(...)` now uses `ON CONFLICT ON CONSTRAINT notification_policy_pkey DO UPDATE`.

Truth statement:
- Policy/override/audit runtime is expected to be verifiable on dev after applying base SQL first, then audit/helper SQL.
- Quiet-hours and anti-spam claims remain limited to observed worker/outbox behavior (`policy_defer`, `override_until` bypass, delivery idempotency key dedupe).

## 6) Final schema-alignment blocker for CHECK-RULES-02
Additional blocker found on dev runtime during defer path:
- `notification_outbox.last_error` (and dead-letter path `dead_letter_reason`) were used by worker but missing from table schema created by migration `c7e0e6518d5c`.

Repo fix:
- `backend/alembic/versions/c7e0e6518d5c_create_notification_outbox.py` now adds:
  - `last_error text NULL`
  - `dead_letter_reason text NULL`
- Added via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` to keep alignment additive for existing dev DBs.

Dev apply/verify order for CHECK-RULES-02 completion:
1. apply notification policy base SQL
2. apply notification policy audit/helper SQL
3. apply outbox schema alignment (alembic upgrade or explicit ALTER)
4. run quiet defer + override/idempotency verification commands


## 7) Final table blocker for override/idempotency proof
Fourth blocker found on dev runtime after defer-path fix:
- `public.notification_deliveries` table was missing, blocking override-bypass receipt insert and idempotency proof.

Repo fix:
- Added additive Alembic migration:
  - `backend/alembic/versions/1f2b3c4d5e6f_create_notification_deliveries_table.py`
- Table/constraint aligned to worker contract in `tools/notification_worker.py`:
  - columns: `outbox_id`, `org_id`, `home_id`, `subject_id`, `route_type`, `route_key`, `idempotency_key`, `provider_msg_id`, `response`, `created_at`
  - dedupe uniqueness: `(org_id, home_id, subject_id, route_type, route_key, idempotency_key)`

Final apply/verify order for CHECK-RULES-02 completion:
1. apply notification_policy base SQL
2. apply notification_policy audit/helper SQL
3. apply notification_outbox column alignment
4. apply notification_deliveries migration
5. run quiet defer + override receipt + idempotency rerun verification

## 8) Explainable alarm/anomaly UI (Fixpack-7 / MUST-5)
Scope truth:
- Primary UI surface is anomaly episode evidence panel in `services/console/anomalies.html`.
- This fixpack adds explicit explainability sections:
  - `Hva skjedde`
  - `Hvorfor uvanlig`
  - `Datagrunnlag`

Proven behavior (repo + dev runtime evidence):
- Explainability text uses anomaly score payload fields only:
  - summary from episode/score fields
  - why-text from reason codes (`reasons`)
  - data basis from `details.observed`
- If reason/baseline explanation is missing in response, UI states this explicitly instead of inferring cause.
- If room context is unavailable for episode row/action, UI explicitly shows `rominfo mangler`.
- Event support link reuses existing events deep-link pattern (`events.html?auto=1&since=...&until=...&room=...`) when room + bucket exist.
- Dev runtime verification proved:
  - `POST /v1/anomalies/run_latest` returns 200
  - `GET /v1/anomalies/score` returns 200 with explainability payload
  - `GET /v1/anomalies` returns persisted anomaly episode rows
- Fixpack-7 also includes minimal backend compatibility fixes required for truthful MUST-5 runtime on current dev schema:
  - `backend/services/anomaly_scoring.py`
  - `backend/services/scheduler.py`

CHECK-WHY mapping:
- CHECK-WHY-01: PASS (repo + dev runtime).
- CHECK-WHY-02: PASS (repo + dev runtime; explicit missing-room episode row tested with empty `room` persisted value).

NO_EVIDENCE:
- Browser screenshot/UI capture is still NO_EVIDENCE unless captured explicitly from running Console.


## 9) Fixpack-A (MUST-A1) alarm truth + lifecycle in Console
Status: **ACTIVE (dev-repo truth)**

Truth implemented in repo:
- Console `alarms.html` now has explicit view split:
  - **Aktiv arbeidsliste** = `OPEN` + `ACK` (default)
  - **Historikk** = `CLOSED`
- `CLOSED` rows are not shown in default active worklist view.
- Operator can switch to explicit history view to see closed alarms.
- Sorting in Console supports at least:
  - status
  - last_seen
  - title
- Existing backend lifecycle contract is unchanged:
  - active statuses are `OPEN` and `ACK`
  - scheduler stale-close moves stale `OPEN/ACK -> CLOSED`
  - later trigger after `CLOSED` creates new `OPEN` row

R-002 local night-window truth:
- Rule now evaluates `night_window.start_local_time` / `end_local_time` in local timezone.
- Default timezone is `Europe/Oslo`, configurable via `rules.R-002.params.timezone`.
- Regression covered for March timestamp around `05:55 UTC` (`06:55` local), which must **not** trigger default `23:00-06:00` local night window.
