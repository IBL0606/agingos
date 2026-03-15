# PILOT RUNBOOK (DRAFT)

Status: **DRAFT**

## Intent
Operational checklist for a pilot environment.

NOTE: In this fixpack we do **Devbox-only** work. This runbook is a skeleton only.

## Daily (read-only)


## Daily (read-only) — Pilotbox / MiniPC checklist (post-upgrade)

This checklist is **read-only** and is intended for **post-upgrade evidence capture** on MiniPC.
If it has not been executed yet, mark outputs as **NO_EVIDENCE** and rely on the template under:
- `docs/audit/_templates/pilotbox_capture/`

### 0) Compose + runtime (read-only)
- `cd /opt/agingos`
- `docker compose ls`
- `docker compose config > /tmp/compose.resolved.yml; head -n 120 /tmp/compose.resolved.yml`
- `docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}"`
- `docker compose logs backend/console/db/ai-bot/notification-worker --tail 200`
- `systemctl cat agingos.service`

### 1) Health + scope (read-only)
- `curl -sS http://127.0.0.1:8000/health`
- `curl -sS http://127.0.0.1:8000/health/detail -H "X-API-Key: $API_KEY"`
- `curl -sS http://127.0.0.1:8000/debug/scope -H "X-API-Key: $API_KEY"`

Interpret `/health/detail` ingest diagnostics:
- `components.ingest.by_category` (last 24h): confirms if `door` stopped earlier than e.g. `ha_snapshot`
- `components.ingest.room_id_completeness_24h`: confirms if `room_id_empty == total` for `presence`/`door`

### 2) DB (read-only SELECT)
By category (last 24h, scoped + stream_id=prod):
SQL:
SELECT category,
       COUNT(*) AS n_24h,
       MAX("timestamp") AS max_ts_24h
FROM events
WHERE org_id='default' AND home_id='default' AND subject_id='default'
  AND stream_id='prod'
  AND "timestamp" >= now() - interval '24 hours'
GROUP BY 1
ORDER BY max_ts_24h DESC NULLS LAST;

room_id completeness (presence/door, last 24h):
SQL:
SELECT category,
       COUNT(*) AS total_24h,
       COUNT(*) FILTER (WHERE COALESCE(room_id,'')='') AS room_id_empty_24h,
       COUNT(*) FILTER (WHERE COALESCE(room_id,'')<>'') AS room_id_set_24h,
       MAX("timestamp") AS max_ts_24h
FROM events
WHERE org_id='default' AND home_id='default' AND subject_id='default'
  AND stream_id='prod'
  AND "timestamp" >= now() - interval '24 hours'
  AND category IN ('presence','door')
GROUP BY 1
ORDER BY category;

NO_EVIDENCE until executed on MiniPC and captured under `docs/audit/as-is-YYYY-MM-DD-pilotbox/`.

## Daily (read-only) — Devbox checklist (current)

All commands below are **read-only** (GET/SELECT) and apply to Devbox (`127.0.0.1`).

### 1) Health: overall status + ingest diagnostics
Run:
- `curl -sS http://127.0.0.1:8000/health`
- `curl -sS http://127.0.0.1:8000/health/detail -H "X-API-Key: $API_KEY"`

Interpret `/health/detail`:
- `overall_status`: OK / DEGRADED / ERROR
- `components.ingest`:
  - `events_n`, `max_event_ts`, `lag_seconds`
  - `thresholds.degraded_seconds`, `thresholds.error_seconds`
  - `by_category` (last 24h, scoped + stream_id):
    - list of `{category, n_24h, max_ts_24h}`
    - Useful to see if e.g. `presence`/`door` stopped earlier than `ha_snapshot`.
  - `room_id_completeness_24h` (last 24h, scoped + stream_id):
    - `presence` and `door`: `{room_id_empty, room_id_set, total}`
    - If `room_id_empty == total` for `presence`/`door`, room attribution is missing for that category.

NO_EVIDENCE: Devbox may have `events_n=0`, so `by_category` and completeness values can be all empty/0 in dev. The fields exist and are verifiable, but real-world data patterns require pilotbox/pilot evidence.

### 2) Scope sanity
Run:
- `curl -sS http://127.0.0.1:8000/debug/scope -H "X-API-Key: $API_KEY"`

### 3) Baseline + runner status (read-only)
In `/health/detail`:
- `components.baseline` indicates readiness/staleness.
- `components.anomalies_runner.runner_status` can be null immediately after restart (process-local).


## Fixpack-C — Hvordan lese regler og alarmer sannferdig

Etter Fixpack-C kan enkelte regler bevisst la være å gi vanlig alarm dersom grunnlaget er for svakt.

Dette gjelder særlig:
- regler som trenger historikk / baseline
- regler som avhenger av boligspesifikk døgnprofil

### Hva operatør skal se etter
Når Console viser at en regel er:

- `WEAK_BASIS`
- `NOT_EVALUATED`
- `DEFAULT_PROFILE`

skal dette leses som:
- systemet skjuler ikke sannheten om svakt grunnlag
- fravær av vanlig alarm betyr ikke automatisk «alt er normalt»
- vurderingen må leses sammen med forklaringen i Console

### Praktisk konsekvens i pilot
- Baseline-avhengige regler kan utebli som normal alarm hvis baseline ikke er READY
- Profil-avhengige regler kan bruke standardprofil og skal da merkes tydelig som ikke personlig tilpasset
- Uavhengige regler skal fortsatt fungere normalt

### Evidence
Ingen egen samlet Fixpack-C evidence-pack ble laget under `docs/audit/verification-...`.
Verifikasjon er i stedet bevist gjennom:
- CI / smoke for PR #46
- tester i `backend/tests/rules/test_rule_truth_gating_unit.py`
- tester i `backend/tests/test_rules_scope_resolution_unit.py`
- appendet Control Tower-tekst i `docs/audit/AgingOS_CONTROL_TOWER.md`
