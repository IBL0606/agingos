# PILOT RUNBOOK (DRAFT)

Status: **DRAFT**

## Intent
Operational checklist for a pilot environment.

NOTE: In this fixpack we do **Devbox-only** work. This runbook is a skeleton only.

## Daily (read-only)

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

