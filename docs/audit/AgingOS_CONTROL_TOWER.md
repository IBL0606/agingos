# AgingOS Control Tower (SoT companion)

**Purpose:** Keep continuity across chats/agents by recording *only verified facts*, current priorities, and pointers to evidence/PRs.

**Status policy:**
- **ACTIVE** = statements backed by evidence/merged code in repo
- **AUDIT** = statements backed by evidence packs under `docs/audit/`
- **HYPOTHESIS** = plausible, not yet verified

---

## 0) Current goals (4 artifacts)
1. **"Slik fungerer AgingOS" (v2 / ACTIVE)** – complete, up-to-date system explanation.
2. **Updated documentation (v2) + obsolete-policy** – all outdated docs updated or marked obsolete.
3. **Pilot plan (runbook + checklists)** – step-by-step install/verify/daily/weekly/rollback.
4. **SoT compliance loop** – SoT-claims checklist + AS-IS evidence + gap analysis + fix plan.

---

## 1) Latest verified evidence (AUDIT)
### Evidence Pack A (Codex runner)
- PR: https://github.com/IBL0606/agingos/pull/24
- Outcome: Evidence captured in an environment **without Docker** (`docker: command not found`) and `curl` attempted `localhost:80`.
- Use: Documents Codex-runner limits; **not** representative of pilotbox runtime.

### Evidence Pack B (pilotbox / MiniPC)
- PR: https://github.com/IBL0606/agingos/pull/25
- Date captured: **2026-03-02 (UTC)**

**Key facts (from `docs/audit/as-is-2026-03-02-pilotbox/*`):**
- Stack up (compose): backend/console/db/ai-bot/notification-worker running ~32h.
- `GET /health` → **200 OK**.
- `GET /health/detail` → **200 OK**, `overall_status=DEGRADED`.
  - Reason: `ingest lag >= 900s`.
  - Observed: `lag_seconds ≈ 1774s`.
  - `ingest.max_event_ts ≈ 2026-03-02T18:30:00Z` while `now_utc ≈ 18:59:34Z`.
- Baseline: **OK** (`baseline_ready=true`, `age_hours≈15.5`, model window 2026-02-23..2026-03-01).
- Scheduler: **OK** (rule_engine/anomalies every 5 min; proposals miner daily).
- Anomalies runner: **OK** (NOOP=5, last_scored_bucket_start 18:30).

**DB snapshots (critical):**
- Last 2h by category:
  - `ha_snapshot` continues to 19:00Z.
  - `presence` last at 18:26:46Z.
  - `door` last at 18:13:05Z.
- `room_id` is **EMPTY for 100%** of `presence` and `door` events in last 24h.

### SoT Claims Checklist v1 (docs-only)
- PR: https://github.com/IBL0606/agingos/pull/26
- Outcome: Added `docs/audit/sot-claims-v1.md` with 40 claims (SOT-001..SOT-040), each with:
  - one-sentence testable claim
  - provenance (doc path + heading)
  - copy/paste-ready, read-only verification commands (docker compose / curl / psql)
- Use: Phase 2 deliverable; input to Phase 3 gap analysis (claims vs evidence pack).

### Gap Analysis (SoT v1 vs pilotbox evidence)
- PR: https://github.com/IBL0606/agingos/pull/28
- Outcome: Added `docs/audit/gap-analysis-2026-03-02.md` mapping SOT-001..SOT-040 to PASS/PARTIAL/FAIL/NO_EVIDENCE with Evidence/Notes/Fix/Priority + 15-item Fix Plan.
- Key results: PASS 2 / PARTIAL 8 / FAIL 1 / NO_EVIDENCE 29.
- Notable: SOT-040 marked FAIL (backend exposed on 0.0.0.0:8000); many items are NO_EVIDENCE due to missing capture artifacts.
- Use: Phase 3 deliverable; input to Phase 4 fixpack planning (focus on reducing NO_EVIDENCE via audit-capture + addressing true blockers).

---

## 2) Current pilot-impacting issues (AUDIT → backlog)
### PILOT BLOCKER candidates
1. **Ingest status = DEGRADED due to lag threshold**
   - Facts: `/health/detail` degraded because lag_seconds >= 900.
   - Open questions: whether lag definition should be category-specific / heartbeat-based.

2. **`room_id` missing on `presence` and `door`**
   - Facts: DB shows `room_id` EMPTY for 100% of events (24h).
   - Impact: Coverage per room (incl. bathroom) cannot be correct.

### Important semantics (not fixed now; must be captured as tasks)
- Presence event rate can drop to ~0 if occupants remain in same room; system may still need occupancy-state/heartbeat to avoid false “ingest stopped”.

---

## 3) Phase plan and current position
- **Phase 1 (Freeze + Evidence Pack):** DONE (pilotbox evidence in PR #25).
- **Phase 2 (SoT-claims checklist):** IN PROGRESS (Codex Task B).
- **Phase 3 (Gap analysis + prioritized plan):** waiting on Phase 2.
- **Phase 4 (Fix pilot blockers + update v2 docs + pilot runbook):** pending.

---

## 4) How to keep continuity across chats (operational rules)
### One canonical “state file” in repo
Create and maintain one file as the *single conversation anchor*:
- `docs/audit/CONTROL_TOWER.md` (this file’s content)

Every time you open a new chat (with me or Codex), paste:
1) link(s) to latest PR(s)
2) the **top of CONTROL_TOWER.md** (sections 1–3)
3) what you want done next (one of the phases)

### Naming conventions (so nothing gets lost)
- Evidence packs: `docs/audit/as-is-YYYY-MM-DD-pilotbox/`
- Gap analyses: `docs/audit/gap-analysis-YYYY-MM-DD.md`
- Fix packs: `pilot/fixpack-YYYY-MM-DD`

### “No-guessing” rule
Anything not backed by:
- evidence file under `docs/audit/...`, or
- specific repo path+commit,
must be labeled **HYPOTHESIS** until verified.

---

## 5) Start prompt template for a NEW chat (copy/paste)
> We are working on AgingOS using the 4-phase process (evidence → claims → gap analysis → fixes + v2 docs + pilot runbook).
> Latest pilotbox evidence PR: https://github.com/IBL0606/agingos/pull/25
> Current verified facts: `/health/detail` shows overall DEGRADED due to ingest lag >=900s; baseline OK; scheduler OK; anomalies runner OK. DB shows `room_id` EMPTY for 100% of presence+door in 24h; presence/door stop earlier than ha_snapshot.
> Task now: [Phase 2 SoT-claims extraction | Phase 3 gap analysis | Phase 4 fixpack].
> Constraints: do not delete data; verification must be read-only; keep docs truthful.

---

## 6) Notes / decisions log (append-only)
- 2026-03-02: Pilotbox evidence collected (PR #25). System overall DEGRADED due to ingest lag; room_id missing on presence/door.


## Phase 4 — Fixpack-1 (devbox) — started 2026-03-03T04:56:56Z
- Branch: pilot/fixpack-2026-03-03
- Scope: devbox only (~/dev/agingos, Docker Desktop). No MiniPC/pilot/prod changes.
- Plan: audit-capture devbox + docs/v2 skeleton + pilot blockers only
- PR: (TBD)
Scope: Devbox only (~/dev/agingos, Docker Desktop). No MiniPC/pilot/prod changes.
Branch: pilot/fixpack-2026-03-03

### Done (committed in branch)
- v2 docs skeleton created:
  - docs/v2/README.md (status-policy: ACTIVE/OBSOLETE/DRAFT + truthfulness rule)
  - docs/v2/OPERATIONS.md (verified dev start/stop + localhost vs expose overlays)
  - docs/v2/TESTING.md, docs/v2/PILOT-RUNBOOK.md
  - docs/obsolete/README.md (policy)
- Devbox audit capture implemented:
  - tools/audit_capture_devbox.sh + Makefile target `make audit-capture`
  - Evidence pack created/refreshed: docs/audit/as-is-2026-03-03-devbox/
- Pilot blocker SOT-040 (port exposure) addressed on devbox:
  - docker-compose.yml now has no public ports by default
  - docker-compose.dev.yml binds ports to 127.0.0.1 (recommended)
  - docker-compose.expose.yml provides opt-in LAN exposure (0.0.0.0)
  - Runtime evidence captured: docs/audit/verification-2026-03-03-fixpack1/docker-ports.localhost.txt
- room_id derivation added in ingest (code):
  - backend/main.py sets db_event.room_id = derive_room_id(event.payload)
  - backend/util/room_id.py + backend/config/room_map.yaml (default empty)
  - Code evidence captured:
    - docs/audit/verification-2026-03-03-fixpack1/room-id-derivation.diff.txt
    - docs/audit/verification-2026-03-03-fixpack1/room-id-derivation.NO_EVIDENCE.md

### Open / Next (Fixpack-1 remaining)
- Extend /health/detail ingest diagnostics (additive):
  - Add components.ingest.by_category (24h counts + last_seen per category)
  - Add components.ingest.room_id_completeness_24h (presence/door empty vs set)
  - Capture read-only evidence (curl outputs + audit-capture refresh) into docs/audit/verification-2026-03-03-fixpack1/
- Update docs/v2 (PILOT-RUNBOOK / TESTING) to reference the new /health/detail fields (truthful; mark NO_EVIDENCE where needed)
- Open PR for fixpack-1 and link it here (append-only)

### Evidence notes (truthfulness)
- Devbox currently has no live events; DB queries for last 24h returned 0 rows for presence/door/ha_snapshot → runtime data effect for room_id completeness remains NO_EVIDENCE until dev has events.
- Python-based compile checks were unstable (WSL session termination / permission issues) → compile evidence marked NO_EVIDENCE; code evidence is via git diff + file content.

## Phase 4 — Fixpack-2 (docs/runbook + pilotbox evidence template) — IN PROGRESS — 2026-03-04T05:09:25Z

- Branch: `pilot/fixpack-2-2026-03-04`
- Scope: devbox/docs only (`~/dev/agingos`, Docker Desktop). No MiniPC/pilot/prod changes.
- Goals:
  - Document explicit MiniPC run/upgrade using overlays (LAN via `docker-compose.expose.yml`).
  - Document systemd unit guidance that matches overlay-based run command (template; NO_EVIDENCE until captured).
  - Add pilotbox post-upgrade evidence-pack TEMPLATE under `docs/audit/_templates/pilotbox_capture/` (NO_EVIDENCE until executed on MiniPC).
- PR: TBD

## Phase 4 — Fixpack-2 — UPDATE: READY TO MERGE — 2026-03-04T05:12:35Z

- Branch: `pilot/fixpack-2-2026-03-04`
- PR: https://github.com/IBL0606/agingos/pull/31
- Scope: docs-only (devbox repo). No MiniPC/pilot/prod changes. No data deletion.
- Delivered:
  - `docs/v2/OPERATIONS.md`: explicit MiniPC overlay run/upgrade guidance + systemd template (NO_EVIDENCE until captured on MiniPC).
  - `docs/v2/PILOT-RUNBOOK.md`: read-only Pilotbox/MiniPC post-upgrade checklist (compose/runtime, health/scope, DB SELECTs).
  - `docs/audit/_templates/pilotbox_capture/MANIFEST.md`: standardized read-only evidence capture template (NO_EVIDENCE until executed).
- DoD note:
  - This unblocks a controlled MiniPC upgrade where LAN exposure is explicit via overlays, and post-upgrade evidence capture is standardized.



### Fixpack-3 — Room Mapping (dev) — 2026-03-06
Link: https://github.com/IBL0606/agingos/pull/32
Type: fixpack (room mapping)
Status: READY TO MERGE

Summary:
- Added Room Catalog (rooms) + Sensor→room mapping (sensor_room_map) (scoped per org/home).
- Ingest resolves events.room_id deterministically for presence/door:
  payload-first → mapping-second → fallback.
- Added backend API:
  - GET/POST /v1/rooms
  - GET/POST /v1/room_mappings
  - GET /v1/room_mappings/unknown_sensors?stream_id=prod
- Added Console “Romoppsett” page: rooms.html + nav-link.

Evidence (dev):
- docs/audit/verification-2026-03-05-fixpack-3-dev/01_roomid_after_ingest_fix.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/02_db_dt_rooms.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/03_db_dt_sensor_room_map.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/43_api_post_room_mappings_upsert.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/44_api_get_room_mappings_after_upsert.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/45_api_get_rooms.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/46_api_get_room_mappings.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/47_api_get_unknown_sensors_initial.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/52_console_rooms_html_served.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/53_console_nav_rooms_link_present.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/54_rooms_html_api_key_masked.txt

Pilotbox:
- Template only (NO_EVIDENCE): docs/audit/_templates/pilotbox_capture/fixpack-3_room_mapping.md

Remaining:
- Replace PR_TBD with actual PR link and set Status to READY TO MERGE when review is complete.

## Phase 4 — Fixpack-4A (MUST-1 setup truth only) — 2026-03-06

- Branch: current working branch
- Scope: dev repo/docs only. No MiniPC/pilotbox runtime change.
- Goal: make install/upgrade per-home verification deterministic and impossible to misread.

Delivered:
- Added `docs/v2/SETUP_TRUTH.md` as canonical MUST-1 setup truth.
- Explicitly separated fresh install vs upgrade command sequences.
- Explicitly documented `/health/detail` truth: runtime/data-aware; empty scoped install can report `overall_status=ERROR` with reason `no events found for this scope`.
- Created evidence pack: `docs/audit/verification-2026-03-06-fixpack-4a-setup/`.

Evidence status:
- Runtime checks in this container are **NO_EVIDENCE** because Docker CLI is unavailable (`command not found`).
- Repo-level deterministic truth (Makefile/compose/backend health logic/docs diffs) is captured in the evidence pack.
