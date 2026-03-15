# AgingOS Control Tower (SoT companion)

Purpose: Keep continuity across chats/agents by recording only verified facts, current priorities, and pointers to evidence/PRs.

Status policy:
- **ACTIVE** = statements backed by evidence and/or merged code in repo
- **AUDIT** = statements backed by evidence packs under `docs/audit/`
- **HYPOTHESIS** = plausible, not yet verified
- **NO_EVIDENCE** = explicitly not proven yet

---

## 0) Current goals

1. **Pilot-ready scope (ACTIVE)**  
   Run pilot on the smallest proven surface possible, with truthful docs, evidence, and UI behavior.

2. **v2 documentation truthfulness (ACTIVE)**  
   `docs/v2/` must reflect only verified behavior. Anything not proven must be marked `NO_EVIDENCE` or `HYPOTHESIS`.

3. **SoT compliance loop (ACTIVE)**  
   Keep claims, evidence packs, fixpacks, and Control Tower aligned so new chats/agents inherit the same truth.

4. **Post-pilot backlog control (ACTIVE)**  
   Do not expand pilot scope unless explicitly decided and evidenced.

---

## 1) Current master status (ACTIVE)

### Pilot-ready scope decision
- Pilot-ready is evaluated based on **Fixpack-1 through Fixpack-8**.
- **MUST-7 (lock support / lock_state / lock UI/rules) is deferred and is NOT included in current pilot scope.**
- This is a deliberate risk-reduction decision to avoid introducing new issues late in the cycle.
- No claim is made that lock support is implemented or verified for pilot use.

### MUST / fixpack status
- **Fixpack-1**: VERIFIED / MERGED / CLOSED
- **Fixpack-2**: VERIFIED / MERGED / CLOSED
- **Fixpack-3**: VERIFIED / MERGED / CLOSED
- **Fixpack-4A (MUST-1 setup truth)**: VERIFIED / MERGED / CLOSED
- **Fixpack-4B (MUST-2 health card in Console)**: VERIFIED / MERGED / CLOSED
- **Fixpack-5 (MUST-3 weekly report in Console)**: VERIFIED / MERGED / CLOSED
- **Fixpack-6 (MUST-4 pilot alarm system)**: VERIFIED / MERGED / CLOSED
- **Fixpack-7 (MUST-5 explainable alarm UI)**: VERIFIED / MERGED / CLOSED
- **Fixpack-8 (MUST-6 room model hardening)**: VERIFIED / MERGED / CLOSED
- **Fixpack-9 / MUST-7 (lock support)**: DEFERRED / OUT OF PILOT SCOPE

### Current truth boundary for pilot
- Pilot scope includes:
  - truthful setup/install/upgrade flow
  - Console health card
  - non-technical weekly report
  - explicit pilot alarm pack + policy/anti-spam/ACK/CLOSE
  - explainable anomaly/alarm UI
  - room-model truth hardening
- Pilot scope does **not** include:
  - lock support / lock_state / lock UI/rules
- `CHECK-ROOM-02` remains **NO_EVIDENCE** for real-home variants such as `bod`, `loft`, `kjellerstue`.

---

## 2) Latest verified baseline evidence (AUDIT)

### Evidence Pack A (Codex runner)
- **PR:** #24
- **Outcome:** Evidence captured in an environment without Docker (`docker: command not found`) and curl attempted `localhost:80`.
- **Use:** Documents Codex-runner limits; not representative of pilotbox runtime.

### Evidence Pack B (pilotbox / MiniPC)
- **PR:** #25
- **Date captured:** 2026-03-02 (UTC)

Key facts from `docs/audit/as-is-2026-03-02-pilotbox/*`:
- Stack up (compose): backend / console / db / ai-bot / notification-worker running ~32h
- `GET /health` → `200 OK`
- `GET /health/detail` → `200 OK`, `overall_status=DEGRADED`
- Reason: ingest lag >= 900s
- Observed: `lag_seconds ≈ 1774s`
- `ingest.max_event_ts ≈ 2026-03-02T18:30:00Z` while `now_utc ≈ 18:59:34Z`
- Baseline: `OK` (`baseline_ready=true`, `age_hours≈15.5`, model window `2026-02-23..2026-03-01`)
- Scheduler: `OK` (rule_engine/anomalies every 5 min; proposals miner daily)
- Anomalies runner: `OK` (`NOOP=5`, `last_scored_bucket_start 18:30`)

Critical DB snapshot facts:
- Last 2h by category:
  - `ha_snapshot` continues to `19:00Z`
  - `presence` last at `18:26:46Z`
  - `door` last at `18:13:05Z`
- `room_id` was EMPTY for 100% of `presence` and `door` events in last 24h at that capture time

### SoT Claims Checklist v1
- **PR:** #26
- **Outcome:** Added `docs/audit/sot-claims-v1.md` with machine-checkable SoT claims and verification commands.

### Gap Analysis (SoT v1 vs pilotbox evidence)
- **PR:** #28
- **Outcome:** Added `docs/audit/gap-analysis-2026-03-02.md`
- **Use:** Historical Phase 3 deliverable and starting point for Phase 4 fixpack planning.

---

## 3) Current pilot-impacting truth / backlog (ACTIVE)

### Resolved / reduced from earlier baseline
These earlier issues are no longer open in the same form for dev-pilot readiness because fixpacks have been delivered and verified:

- **MUST-1 setup ambiguity** → addressed by Fixpack-4A
- **MUST-2 missing health-card UX** → addressed by Fixpack-4B
- **MUST-3 weak/non-truthful report behavior** → addressed by Fixpack-5
- **MUST-4 alarm policy / ACK-CLOSE / anti-spam truth gaps** → addressed by Fixpack-6
- **MUST-5 explainability gap** → addressed by Fixpack-7
- **room_id deterministic mapping gap** → addressed by Fixpack-3
- **room-model truth boundary for variants** → documented by Fixpack-8

### Still open / explicitly bounded
- **Real-home room variant evidence** remains `NO_EVIDENCE` for specific variant names such as `bod`, `loft`, `kjellerstue`.
- **Browser screenshot/UI capture** for Fixpack-7 was `NO_EVIDENCE` during that verification round, but this was not a blocker for `CHECK-WHY-01/02`.
- **Lock support (MUST-7)** is intentionally deferred and out of pilot scope.

### Important semantics to keep explicit
- Presence event rate can drop to ~0 if occupants remain in the same room; the system may still need occupancy-state/heartbeat logic in future work. This remains a product/logic consideration and should not be silently treated as solved unless separately evidenced.

---

## 4) Current project position (ACTIVE)

The original Phase 1–4 structure has been executed far enough that the project should now be treated as:

- **Phase 1 (Freeze + Evidence Pack): DONE**
- **Phase 2 (SoT claims checklist): DONE**
- **Phase 3 (Gap analysis + prioritized plan): DONE**
- **Phase 4 (Fixpacks for pilot readiness): SUBSTANTIALLY COMPLETE for current pilot scope**
  - Fixpack-1 through Fixpack-8 completed
  - MUST-7 intentionally deferred out of scope

Current practical position:
- AgingOS is considered **pilot-ready for the defined pilot scope**, based on Fixpack-1 through Fixpack-8 and the explicit exclusion of MUST-7.

---

## 5) How to keep continuity across chats (operational rules)

### One canonical state file in repo
Use and maintain this file as the single conversation anchor:

- `docs/audit/AgingOS_CONTROL_TOWER.md`

### Every time you open a new chat
Paste:
- relevant PR link(s)
- the current master status from this file
- the exact task to be done next
- any relevant evidence path(s)

### Naming conventions
- Evidence packs: `docs/audit/as-is-YYYY-MM-DD-pilotbox/`
- Verification packs: `docs/audit/verification-YYYY-MM-DD-.../`
- Gap analyses: `docs/audit/gap-analysis-YYYY-MM-DD.md`
- Fixpack branches / PRs: explicit `fixpack-*` or equivalent task branch names

### No-guessing rule
Anything not backed by:
- an evidence file under `docs/audit/...`, or
- a specific repo path + merged code / verified runtime evidence

must be labeled `HYPOTHESIS` or `NO_EVIDENCE`.

---

## 6) Start prompt template for a new chat (copy/paste)

We are working on AgingOS using a verified fixpack process. Canonical state file: `docs/audit/AgingOS_CONTROL_TOWER.md`. Current pilot-ready scope is based on Fixpack-1 through Fixpack-8; MUST-7 (lock support) is explicitly deferred and out of scope. Constraints: do not guess, do not delete pilot/prod data, verification must be read-only outside dev, docs must be 100% truthful, and anything not proven must be marked NO_EVIDENCE or HYPOTHESIS. Task now: [insert exact scoped task]. Relevant PR(s): [insert]. Relevant evidence path(s): [insert].

---

## 7) Notes / decisions log (append-only)

### 2026-03-02 — Pilotbox evidence collected
- **PR:** #25
- System overall `DEGRADED` due to ingest lag.
- `room_id` missing on `presence` / `door` at that capture time.

### Phase 4 — Fixpack-1 (devbox) — started 2026-03-03T04:56:56Z
- **Branch:** `pilot/fixpack-2026-03-03`
- **Scope:** devbox only (`~/dev/agingos`, Docker Desktop). No MiniPC/pilot/prod changes.
- **Plan:** audit-capture devbox + docs/v2 skeleton + pilot blockers only

Delivered in branch:
- v2 docs skeleton created:
  - `docs/v2/README.md`
  - `docs/v2/OPERATIONS.md`
  - `docs/v2/TESTING.md`
  - `docs/v2/PILOT-RUNBOOK.md`
  - `docs/obsolete/README.md`
- Devbox audit capture implemented:
  - `tools/audit_capture_devbox.sh`
  - `Makefile` target `make audit-capture`
- Evidence pack created/refreshed:
  - `docs/audit/as-is-2026-03-03-devbox/`
- Port exposure hardening on devbox:
  - `docker-compose.yml` no public ports by default
  - `docker-compose.dev.yml` binds ports to `127.0.0.1`
  - `docker-compose.expose.yml` provides opt-in LAN exposure
- Initial room_id derivation added in ingest:
  - `backend/main.py`
  - `backend/util/room_id.py`
  - `backend/config/room_map.yaml`

Historical evidence notes:
- Devbox had no live events at that moment, so runtime room_id completeness remained `NO_EVIDENCE`.
- Python compile checks were unstable in that context; compile evidence was marked `NO_EVIDENCE`.

### Phase 4 — Fixpack-2 (docs/runbook + pilotbox evidence template) — READY TO MERGE — 2026-03-04T05:12:35Z
- **Branch:** `pilot/fixpack-2-2026-03-04`
- **PR:** #31
- **Scope:** docs-only (devbox repo). No MiniPC/pilot/prod changes. No data deletion.

Delivered:
- `docs/v2/OPERATIONS.md`: explicit MiniPC overlay run/upgrade guidance + systemd template (`NO_EVIDENCE` until captured on MiniPC)
- `docs/v2/PILOT-RUNBOOK.md`: read-only Pilotbox/MiniPC post-upgrade checklist
- `docs/audit/_templates/pilotbox_capture/MANIFEST.md`: standardized read-only evidence capture template

### Fixpack-3 — Room Mapping (dev) — 2026-03-06
- **PR:** #32
- **Status:** READY TO MERGE at that entry time; later treated as verified baseline in project truth

Summary:
- Added `rooms` + `sensor_room_map` scoped per org/home
- Ingest resolves `events.room_id` deterministically for presence/door: payload-first → mapping-second → fallback
- Added backend API:
  - `GET/POST /v1/rooms`
  - `GET/POST /v1/room_mappings`
  - `GET /v1/room_mappings/unknown_sensors?stream_id=prod`
- Added Console page: `rooms.html` + nav link

Evidence (dev):
- `docs/audit/verification-2026-03-05-fixpack-3-dev/01_roomid_after_ingest_fix.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/02_db_dt_rooms.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/03_db_dt_sensor_room_map.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/43_api_post_room_mappings_upsert.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/44_api_get_room_mappings_after_upsert.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/45_api_get_rooms.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/46_api_get_room_mappings.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/47_api_get_unknown_sensors_initial.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/52_console_rooms_html_served.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/53_console_nav_rooms_link_present.txt`
- `docs/audit/verification-2026-03-05-fixpack-3-dev/54_rooms_html_api_key_masked.txt`

Pilotbox:
- Template only (`NO_EVIDENCE`): `docs/audit/_templates/pilotbox_capture/fixpack-3_room_mapping.md`

### Phase 4 — Fixpack-4A (MUST-1 setup truth only) — MERGED — 2026-03-06
- **PR:** #33
- **Scope:** dev repo/docs only. No MiniPC/pilotbox runtime change.

Delivered:
- Added canonical `docs/v2/SETUP_TRUTH.md`
- Explicitly separated fresh install vs upgrade
- Documented `/health/detail` truth boundary
- Fixed scheduler fresh-install transaction poison behavior
- Added in-repo DB baseline bootstrap functions through migration `a8f9c2d1e4b7`
- Fresh install PASS path documented and verified to `/health/detail overall_status="OK"`

Evidence:
- `docs/audit/verification-2026-03-06-fixpack-4a-setup/`
- `docs/audit/verification-2026-03-06-fixpack-4a-scheduler-followup/`
- `docs/audit/verification-2026-03-06-fixpack-4a-final-setup-pass/`

Final status:
- `CHECK-SETUP-01`: PASS
- `CHECK-SETUP-02`: PASS

Note:
- PR #34 was source for a final fix and should not be merged separately.

### Phase 4 — Fixpack-4B (MUST-2 Console health card) — MERGED — 2026-03-06
- **PR:** #35
- **Scope:** Console health card / presentation / UX / docs / evidence only.
- `/health/detail` remained the truth backend source.
- No setup-truth or backend contract changes.

Delivered:
- Health card in `services/console/index.html`
- G/Y/R overall status from `/health/detail`
- Plain-language explanation + 1–3 next steps
- Explicit unknown/missing-data handling
- docs/v2 updates
- evidence pack

Evidence:
- `docs/audit/verification-2026-03-06-fixpack-4b-health-card/`

Final status:
- `CHECK-HEALTH-01`: PASS
- `CHECK-HEALTH-02`: PASS

Truth note:
- Worker detail rendered `DEGRADED` in live test because UI interpreted missing `last_ok_at` more strictly than backend `status=OK`.
- Overall card and ingest/baseline parts were truthful against `/health/detail`.
- Not a blocker for MUST-2.

### Phase 4 — Fixpack-5 (MUST-3 weekly report in Console) — MERGED — 2026-03-06
- **PR:** #36
- **Scope:** weekly report UX + truthful data sourcing + minimal runtime/schema reconciliation needed for dev verification.

Delivered:
- Hardened `services/console/report.html` as existing report page
- Non-technical weekly summary with exactly:
  - `Data inn`
  - `Romdekning`
  - `Alarmer`
  - `Endringer`
- Explicit truth mode per section:
  - `REAL`
  - `TEMPLATE/FALLBACK`
  - `NO_EVIDENCE`
- `weekly_report` included in driftpakke JSON export
- Additive migration:
  - `backend/alembic/versions/9c5f1a2b7e44_reconcile_weekly_report_runtime_schema.py`

Evidence:
- `docs/audit/verification-2026-03-06-fixpack-5-must-3-weekly-report/`

Final status:
- `CHECK-REPORT-01`: PASS
- `CHECK-REPORT-02`: PASS
- `CHECK-REPORT-03`: PASS

Truth note:
- Sparse dev data may render `TEMPLATE/FALLBACK` instead of `REAL`; that is expected and truthful.

### Phase 4 — Fixpack-6 (MUST-4 pilot alarm system) — MERGED — 2026-03-07
- **PR:** #37
- **Scope:** explicit pilot rule pack truth + quiet-hours / override / anti-spam truth + ACK/CLOSE lifecycle truth + docs/evidence.

Delivered:
- `GET /v1/rules/pilot-pack`
- Explicit pilot rule pack for `R-001..R-010`
- Notification policy base schema and audit/helper SQL alignment
- Notification outbox alignment for worker-required columns
- `notification_deliveries` table for receipt/idempotency proof
- docs/v2 updates including `docs/v2/PILOT-ALARMS.md`

Evidence:
- `docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/`

Final status:
- `CHECK-RULES-01`: PASS
- `CHECK-RULES-02`: PASS
- `CHECK-RULES-03`: PASS

Truth boundary:
- Cooldown semantics are explicitly `NONE`
- Grouping claim is limited to proven OPEN/ACK dedupe by rule+subject+scope
- No invented anti-spam/alarm semantics added
- Verification is dev-only
- No MiniPC/customer changes

### Phase 4 — Fixpack-7 (MUST-5 explainable alarm UI "why") — MERGED — 2026-03-07
- **PR:** #38
- **Scope:** strictly MUST-5 explainability on existing anomaly/alarm UI surface (dev-only)

Delivered:
- Updated `services/console/anomalies.html` with:
  - `Hva skjedde`
  - `Hvorfor uvanlig`
  - `Datagrunnlag`
- Explainability bounded to existing payload only:
  - `score`
  - `reasons`
  - `details.observed`
- Explicit missing-room handling text: `rominfo mangler`
- Events deep-link only when room + bucket exist
- Minimal backend compatibility fixes:
  - `backend/services/anomaly_scoring.py`
  - `backend/services/scheduler.py`
- docs updates:
  - `docs/v2/PILOT-ALARMS.md`
  - `docs/v2/README.md`
  - `docs/v2/TESTING.md`

Evidence:
- `docs/audit/verification-2026-03-07-fixpack-7-must-5-explainability/00_manifest.md`

Final status:
- `CHECK-WHY-01`: PASS
- `CHECK-WHY-02`: PASS

Dev runtime evidence:
- `POST /v1/anomalies/run_latest` => `200 OK`
- `GET /v1/anomalies/score` => `200 OK` with explainability payload
- persisted `YELLOW` anomaly episode created and returned from `GET /v1/anomalies`
- explicit missing-room runtime case created with empty room anomaly episode row

Truth note:
- Browser screenshot/UI capture was `NO_EVIDENCE` in that verification round.
- This was not a blocker for MUST-5.

### Phase 4 — Fixpack-8 (MUST-6 room model hardening) — MERGED — 2026-03-07
- **PR:** #39
- **Scope:** strictly MUST-6 room-name variant truth hardening (dev/docs only)

Delivered:
- Updated `docs/v2/ROOM_MAPPING.md` to explicitly separate:
  - generic/code-path support
  - real-home tested evidence boundary
- Added dev evidence pack:
  - `docs/audit/verification-2026-03-07-fixpack-8-must-6-room-hardening/00_manifest.md`
  - `docs/audit/verification-2026-03-07-fixpack-8-must-6-room-hardening/10_room_logic_scan.txt`
  - `docs/audit/verification-2026-03-07-fixpack-8-must-6-room-hardening/20_variant_term_scan.txt`
  - `docs/audit/verification-2026-03-07-fixpack-8-must-6-room-hardening/30_check_room_02_status.md`
- Added SoT guard claim in `docs/audit/sot-claims-v1.md` (`SOT-041`)

Final status:
- `CHECK-ROOM-01`: PASS (referenced from Fixpack-3 baseline)
- `CHECK-ROOM-02`: NO_EVIDENCE

Truth boundary:
- Current ingest resolves room names generically via `rooms.display_name` case-insensitive match and `sensor_room_map`.
- No claim is made that `bod` / `loft` / `kjellerstue` are proven in real homes.

### Phase 4 — Pilot scope decision — MUST-7 lock support deferred — 2026-03-07
Decision:
- MUST-7 (lock support / lock_state / lock UI/rules) is deferred and is NOT included in current pilot scope.

Reason:
- Deliberate risk reduction before pilot.
- Current priority is to pilot the smallest proven surface possible and avoid introducing new issues late in the cycle.

Truth boundary:
- No claim is made that lock support is implemented or verified for pilot use.
- Pilot-ready status is evaluated based on Fixpack-1 through Fixpack-8 only.
- MUST-7 remains a post-pilot candidate, not a failed item.

Impact:
- No code/runtime change from this decision.
- This is a project-scope/control decision only.

### MiniPC Pilot Upgrade — CONTROLLED UPGRADE WITH FULL BACKUP FIRST — 2026-03-07

Status: COMPLETED ON PILOTBOX (operational evidence captured under `_handoff` and copied off-host)

Scope:
- Controlled MiniPC/pilotbox upgrade to current `origin/main`
- Full backup before writes
- Read-only preflight
- Runtime upgrade + DB migration
- Post-upgrade verification
- No derived-data rebuild unless evidence required it

What was done:
- Full DB backup + schema-only backup taken before any upgrade writes
- Data-only backups taken for critical tables:
  - `events`
  - `episodes`
  - `episodes_svc`
  - `anomaly_episodes`
  - `deviations`
  - `proposals`
  - `proposal_links`
  - `proposal_feedback`
  - `baseline_model_status`
  - `baseline_room_bucket`
  - `baseline_transition`
  - `notification_outbox`
  - `notification_deliveries`
  - `notification_policy`
  - `api_key_scopes`
- Off-host backup copy verified on laptop
- MiniPC preflight captured runtime, auth/scope, OpenAPI, schema snapshots, counts/freshness
- MiniPC moved from old audit branch to current `origin/main` (`1dcf9ec`)
- Runtime restarted/rebuilt
- Alembic migration completed to head `1f2b3c4d5e6f`

Migration repairs required (evidence-backed, minimal):
- Removed redundant ancestor row `5d205e6bbb78` from `alembic_version` after extra backup
- Stamped `16675adff372` because its schema effects were already materially present on MiniPC
- Backed up and dropped 3 conflicting baseline functions with incompatible return type before re-running Alembic:
  - `build_daily_room_bucket_rollup(date, uuid)`
  - `build_daily_transition_rollup(date, uuid)`
  - `build_baseline_7d(date, uuid, double precision, double precision, integer)`

Post-upgrade outcome:
- Base compose alone lost host/LAN reachability as documented
- LAN pilot reachability restored with `docker-compose.expose.yml`
- Host `/health` and `/health/detail` returned `200` after overlay recovery
- Ingest temporarily degraded during restart window, then recovered
- Final `/health/detail` returned `overall_status = OK`
- Key APIs verified post-upgrade:
  - `/v1/events`
  - `/v1/anomalies`
  - `/v1/deviations`
  - `/v1/proposals`
  - `/v1/rules/pilot-pack`
  - `/v1/notification/policy`

Rebuild decision:
- baseline rebuild: NO
- anomalies rerun: NO
- episodes_svc build: not required by evidence
- proposals re-mine: NO

Important residual note:
- `room_id` materialization is improved on new events, but historical completeness is not retroactively fixed by this upgrade
- This was not treated as a reason to rebuild derived data

Evidence:
- `/opt/agingos/_handoff/minipc_upgrade/20260307T170203Z/`
- off-host copy: `~/agingos-minipc-backups/20260307T170203Z`

### Fixpack-10 — Boot + Room Inventory Robustness — 2026-03-14
- **Branch:** `work`
- **Scope:** dev repo only (`/workspace/agingos`). No MiniPC/pilotbox runtime changes.
- **Delivered (code/docs):**
  - Added room inventory self-heal endpoint:
    - `POST /v1/room_mappings/self_heal?stream_id=<id>&dry_run=true|false`
  - Self-heal behavior:
    - Rebuild/upsert missing rooms from live observed `payload.room` / `payload.area`
    - Rebuild/upsert sensor mappings only for unique observed `entity_id -> room`
    - Explicit conflict reporting for multi-room observations per entity
    - No blind overwrite of existing different mappings (`skipped_existing`)
  - Rooms UI now uses selected stream from Console config (localStorage) for:
    - `/v1/room_mappings/unknown_sensors`
    - `/v1/events`
  - Rooms UI now renders explicit operator state for empty room catalog.
  - MiniPC runbook start/stop/log commands updated to expose overlay truth:
    - `docker compose -f docker-compose.yml -f docker-compose.expose.yml ...`
- **Evidence pack target:**
  - `docs/audit/verification-2026-03-14-fixpack-10-boot-room-robustness/`
- **Important limitation:**
  - Runtime API verification in this environment is `NO_EVIDENCE` when Docker is unavailable.

### Fixpack-10 — Boot + Room Inventory Robustness — VERIFIED ON DEV — 2026-03-14
Branch: `fixpack-10-verify`
PR: https://github.com/IBL0606/agingos/pull/43

Scope:
- truthful pilot/LAN boot/runtime path
- room inventory self-heal/bootstrap
- Rooms UI stream + empty-state hardening

Evidence pack:
- `docs/audit/verification-2026-03-14-fixpack-10-boot-room-robustness/`

Verified status:
- CHECK-FP10-01: PASS
- CHECK-FP10-02: PASS
- CHECK-FP10-03: NO_EVIDENCE
- CHECK-FP10-04: PASS
- CHECK-FP10-05: NO_EVIDENCE
- CHECK-FP10-06: PASS
- CHECK-FP10-07: PASS
- CHECK-FP10-08: NO_EVIDENCE

Verified facts:
- `/v1/room_mappings/self_heal` is registered in runtime.
- Room self-heal from live observed `payload.room` / `payload.area` is runtime-verified on dev.
- Re-running self-heal is idempotent for room creation in current dev dataset.
- Rooms UI now uses selected stream from shared Console config, not hardcoded `prod`.
- MiniPC runbook now reflects expose-overlay boot truth for pilot/LAN mode.

Remaining evidence gaps:
- Current dev events do not contain `payload.entity_id`.
- Therefore entity→room auto-mapping, conflict handling for same entity in multiple rooms, and unknown-sensors reduction after self-heal remain NO_EVIDENCE in this verification run.

Merge position:
- Safe to merge with truthful NO_EVIDENCE status retained.
- Not a full 100% DoD close until entity-bearing dev/pilot evidence exists.

### Fixpack-A — MUST-A1 Alarm truth + lifecycle in Console — 2026-03-15
- **Scope:** dev repo only (`/workspace/agingos`). No pilot/prod data change.
- **Goal:** keep alarm view truthful and operator-safe with explicit active vs history split, and align R-002 night logic with local time semantics.

Delivered:
- Console alarms view now defaults to active worklist (`OPEN` + `ACK`) and separates `CLOSED` into explicit history view.
- Console added sorting options for status, last_seen, title.
- R-002 now evaluates night window in local timezone (`Europe/Oslo` by default; configurable via params.timezone).
- R-002 unit tests updated to prove local-night trigger, local-day no-trigger, and March regression (`05:55 UTC` => non-night local).

Evidence path:
- `docs/audit/verification-2026-03-15-fixpack-a-must-a1/`

Status note:
- CHECK-A-01..CHECK-A-05 intended to be proven from this verification pack.

### Fixpack-B — MUST-B1 Rule explainability + drilldown — 2026-03-15
PR: https://github.com/IBL0606/agingos/pull/48
Branch: pr-48-fixpack-b
Status: IMPLEMENTED / VERIFIED IN DEV

Scope:
- operatorvennlig regelvisning i Console
- regel → funn-filtering
- sann drilldown fra funn/anomali til hendelser
- ingen falsk presisjon når eksakt trigger-event ikke kan bevises

Changed files:
- backend/routes/rules.py
- services/console/rules.html
- services/console/console_shared.js
- services/console/alarms.html
- services/console/anomalies.html
- services/console/events.html

Verification summary:
- CHECK-B-01 PASS: egen regelside i Console (`rules.html`)
- CHECK-B-02 PASS: `/v1/rules` returnerer `rule_id`, `display_name`, `human_explanation`, `runtime_status`
- CHECK-B-03 PASS: `rules.html -> alarms.html?rule_id=...`, og `alarms/anomalies -> events.html?...`
- CHECK-B-04 PASS: drilldown bygger og konsumerer reelle filterfelt (`room`, `category`, `since`, `until`, `stream_id`, `auto=1`)
- CHECK-B-05 PASS: ACK/CLOSE-flyt beholdt; anomalies-flyt beholdt; proposals ikke rørt

Runtime/UI evidence:
- statisk regelside inneholder kolonnene `Rule ID`, `Forklaring`, `Funn`
- backend er tilgjengelig fra console-nettverket og returnerer operatorfelter for R-001..R-010
- nginx proxyer `/api/*` til backend og videresender `X-API-Key`

Known gap / risk:
- `backend/routes/rules.py` har robusthetsstøy i scope-fallback mot `subjects` i dette dev-miljøet; respons ender fortsatt i 200 med fallback-data, men dette bør hardenes separat

### Fixpack-B — MUST-B1 Rule explainability + drilldown — 2026-03-15
PR: https://github.com/IBL0606/agingos/pull/48
Status: IMPLEMENTED / VERIFIED IN DEV

Scope:
- operatorvennlig regelvisning i Console
- regel → funn-filtering
- sann drilldown fra funn/anomali til hendelser
- ingen falsk presisjon når eksakt trigger-event ikke kan bevises

Changed files:
- backend/routes/rules.py
- services/console/rules.html
- services/console/console_shared.js
- services/console/alarms.html
- services/console/anomalies.html
- services/console/events.html

Verification summary:
- CHECK-B-01 PASS: egen regelside i Console (`rules.html`)
- CHECK-B-02 PASS: `/v1/rules` returnerer `rule_id`, `display_name`, `human_explanation`, `runtime_status`
- CHECK-B-03 PASS: `rules.html -> alarms.html?rule_id=...`, og `alarms/anomalies -> events.html?...`
- CHECK-B-04 PASS: drilldown bygger og konsumerer reelle filterfelt (`room`, `category`, `since`, `until`, `stream_id`, `auto=1`)
- CHECK-B-05 PASS: ACK/CLOSE-flyt beholdt; anomalies-flyt beholdt; proposals ikke rørt

Runtime/UI evidence:
- statisk regelside inneholder kolonnene `Rule ID`, `Forklaring`, `Funn`
- backend er tilgjengelig fra console-nettverket og returnerer operatorfelter for R-001..R-010
- nginx proxyer `/api/*` til backend og videresender `X-API-Key`

Known gap / risk:
- `backend/routes/rules.py` har robusthetsstøy i scope-fallback mot `subjects` i dette dev-miljøet; respons ender fortsatt i 200 med fallback-data, men dette bør hardenes separat
