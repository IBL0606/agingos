# OPERATIONS (DRAFT)

Status: **DRAFT**

## Scope: Devbox
This document applies to **Devbox only** (`~/dev/agingos`, Docker Desktop).
Pilot/Prod (MiniPC) is out of scope unless explicitly stated.


## MiniPC / Pilotbox (Pilot/Prod) — upgrade/run guidance (explicit)

This section is **guidance only**. It does **not** imply any MiniPC changes were made.
Any MiniPC state must be captured as **read-only evidence** under `docs/audit/as-is-YYYY-MM-DD-pilotbox/`.

### Why this exists
- `docker-compose.yml` is **safe-by-default** (no published ports).
- LAN reachability is **opt-in** via `docker-compose.expose.yml`.
- If MiniPC runs only `docker-compose.yml` after upgrading to `main`, it will likely **lose host/LAN reachability** (expected).

### Run on MiniPC (LAN, recommended for pilot)
From `/opt/agingos`:
- Start / reconcile:
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml up -d --build`
- Stop:
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml down`

### (Optional) Run on MiniPC (localhost-only)
From `/opt/agingos`:
- Start / reconcile:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`
- Stop:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml down`

### systemd unit guidance (MiniPC)
This is a **template**. It is **NO_EVIDENCE** until a MiniPC `systemctl cat agingos.service` capture confirms it.

Example (LAN):
[Unit]
Description=AgingOS (docker compose)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/agingos
ExecStart=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.expose.yml up -d --build
ExecStop=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.expose.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target

## Start/stop (Devbox)

### Localhost-only (DEFAULT / recommended)
This mode binds ports to **127.0.0.1** only (not exposed on LAN):

- Start / reconcile:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
- Verify ports:
  - `docker ps --format "table {{.Names}}\t{{.Ports}}" | rg "agingos-(backend|console|db|ai-bot)-1"`
- Stop:
  - `docker compose -f docker-compose.yml -f docker-compose.dev.yml down`

### LAN-exposed (OPT-IN, explicit)
This mode exposes ports on **0.0.0.0** (LAN). Use only when explicitly needed:

- Start:
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml up -d`
- Verify ports:
  - `docker ps --format "table {{.Names}}\t{{.Ports}}" | rg "agingos-(backend|console|db|ai-bot)-1"`
- Stop:
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml down`

## Health checks (read-only)
- `GET /health`
- `GET /health/detail` (requires `X-API-Key`)
  - includes ingest diagnostics: `components.ingest.by_category` and `components.ingest.room_id_completeness_24h`
- `GET /debug/scope` (requires `X-API-Key`)


## Console health card (Fixpack-4B / MUST-2)
- Host page: `services/console/index.html` (Status).
- Truth source: `GET /health/detail` (requires `X-API-Key`).
- Card must show:
  - overall color state from `overall_status` (`OK`→grønn, `DEGRADED`→gul, `ERROR`→rød, ellers ukjent)
  - kort forklaring i vanlig språk
  - 1–3 konkrete neste steg
  - komponentvis status for ingest + baseline + worker-ekvivalent (`worker`/`anomalies_runner`/`scheduler`)
- If component fields are missing in `/health/detail`, Console must explicitly render `Ukjent / mangler data` (never silently green).


## Weekly report truth/export (Fixpack-D / MUST-D1)
- Host page: `services/console/report.html` (`/report.html`).
- Canonical weekly truth source is backend aggregation (not client-side sampled events):
  - `GET /v1/reports/weekly?stream_id=prod`
  - legacy alias: `GET /reports/weekly?stream_id=prod`
- Truthful export endpoint:
  - `GET /v1/reports/weekly/export.json?stream_id=prod`
  - legacy alias: `GET /reports/weekly/export.json?stream_id=prod`
  - format marker in payload: `export_format=agingos_weekly_truth_json_v1`
- Contract highlights:
  - `summary`: `events_7d`, `deviations_open`, `deviations_seen_7d`, `anomalies_7d`, `proposals_updated_7d`
  - `analysis_running`: explicitly tied to runner evidence (`last_ok_at` / `last_run_at` / `last_error_at`)
  - `history_basis_ready`: explicitly tied to baseline evidence (`baseline_ready`, `days_with_data`, `min_days_required`, `room_bucket_supported/room_bucket_rows`)
  - `basis.status/message/deficits`: concrete deficits with `have` vs `need` and optional `missing_rooms`
- Rule: Console weekly report must consume this endpoint as primary truth, and must render weak basis concretely (what is missing and how much is missing).

## Evidence capture (read-only)
Canonical Devbox evidence capture:
- `make audit-capture`

Writes a dated evidence pack under:
- `docs/audit/as-is-YYYY-MM-DD-devbox/`

Rule: anything not proven by evidence must be marked **NO_EVIDENCE** or **HYPOTHESIS**.

<!-- FIXPACK-3: ROOM MAPPING START -->
## Romoppsett (Fixpack-3)
- Se: docs/v2/ROOM_MAPPING.md
- Console: /rooms.html (Romoppsett)
- Pilotbox template (NO_EVIDENCE): docs/audit/_templates/pilotbox_capture/fixpack-3_room_mapping.md
<!-- FIXPACK-3: ROOM MAPPING END -->

## Setup truth pointer (Devbox)
For install/upgrade verification commands and expected truth, use:
- `docs/v2/SETUP_TRUTH.md`

Do not assume `/health/detail overall_status=OK` on fresh empty installs; verify actual output.

## Pilot alarms (Fixpack-6 / MUST-4)
- Explicit pilot rule pack endpoint:
  - `GET /v1/rules/pilot-pack`
- Alarm lifecycle endpoints used by Console Alarmer:
  - `GET /v1/deviations`
  - `PATCH /v1/deviations/{id}` with status `OPEN|ACK|CLOSED`
- Notification policy endpoints reused for quiet/override behavior:
  - `GET /v1/notification/policy`
  - `POST /v1/notification/policy/partner_override`
  - `GET /v1/notification/policy/audit`

Truth guardrails:
- No cooldown semantics beyond what is explicit in config are allowed.
- Outbox anti-spam truth is idempotency-key based delivery dedupe, not alarm-generation dedupe.
- If deviation status history/audit is required, it is currently NO_EVIDENCE unless a concrete table/endpoint is introduced and verified.


## Fixpack-10 runtime truth (boot + room inventory)

- Pilot/LAN restart/autostart truth in repo remains compose with expose overlay:
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml up -d --build`
  - `docker compose -f docker-compose.yml -f docker-compose.expose.yml down`
- Base compose only (`docker compose up -d`) is not sufficient truth for LAN-reachable Console in pilot mode.
- Room inventory self-heal API (scope + stream-aware):
  - `POST /v1/room_mappings/self_heal?stream_id=<id>&dry_run=true|false`
  - Reads live observed `payload.room` / `payload.area` and `payload.entity_id` from current scope+stream.
  - Reports deterministic counters: `rooms_inserted`, `rooms_unchanged`, `mappings_inserted`, `mappings_unchanged`, `mappings_conflicted`, `skipped_existing`, `conflicts[]`.
  - Conflict policy: if one `entity_id` is observed in multiple rooms, mapping is **not** auto-written; conflict is reported explicitly.
  - Existing mappings to another room are not overwritten blindly (`skipped_existing`).



## Fixpack-B — Rule explainability + truthful drilldown (2026-03-15)

Console:
- `services/console/rules.html` / `rules.html` er operatorflaten for regler.
- Siden skal vise minst:
  - `rule_id`
  - menneskelig navn
  - menneskelig forklaring
  - runtime-status / truth-status når tilgjengelig
- Regelsiden skal kunne sende operatør videre til relevante funn via:
  - `./alarms.html?rule_id=<RULE_ID>`

API truth:
- `GET /v1/rules` er utvidet additivt med operatorfelter:
  - `rule_id`
  - `display_name`
  - `human_explanation`
  - `runtime_status`
- Eksisterende felt/atferd skal bevares; dette er ikke parameterredigering.

Drilldown truth:
- Varsler/funn skal lenke til `events.html` med reelle filtre når slikt grunnlag finnes:
  - `room`
  - `category`
  - `since`
  - `until`
  - `stream_id`
  - `auto=1`
- `events.html` skal lese og faktisk bruke disse filtrene i visningen.
- Hvis eksakt trigger-event ikke kan bevises/rekonstrueres, skal Console si dette eksplisitt og vise relevant datagrunnlag for samme scope/tidsvindu/rom/kategori i stedet.

Bevisstatus:
- Verifisert i dev på PR #48.
- Evidence pack:
  - `docs/audit/verification-2026-03-15-fixpack-b-rule-explainability/`
- Control Tower:
  - `docs/audit/AgingOS_CONTROL_TOWER.md`

## Fixpack-C — Truthful gating for regler (2026-03-15)

Pilot-reglene er nå klassifisert eksplisitt som:

- `baseline_dependent`
- `profile_dependent`
- `independent`

Formål:
Regler skal ikke presenteres som fullverdige alarmer når historikkgrunnlaget eller boligprofilen er for svak.

### Evaluation truth
Følgende truth-stater brukes i runtime / Console:

- `FULLY_EVALUATED` — regelen er vurdert med tilstrekkelig grunnlag
- `WEAK_BASIS` — regelen er vurdert med svakt grunnlag og skal ikke leses som full-confidence
- `NOT_EVALUATED` — regelen ble ikke fullverdig vurdert fordi grunnlaget mangler
- `DEFAULT_PROFILE` — regelen bruker standardprofil / standardvindu og er ikke personlig tilpasset boligen

### Operatørkontrakt
Console skal bruke menneskespråk som tydelig sier hvorfor vurdering er svak eller uteblir, for eksempel:

- «Ikke vurdert: mangler nok historikk»
- «Svak vurdering: baseline ikke READY»
- «Bruker standard nattvindu, ikke personlig boligprofil»

Baseline-/profil-svake regler skal ikke presenteres som vanlige full-confidence alarmer.

### Bevisstatus
Fixpack-C ble verifisert gjennom:
- CI grønn for PR #46
- unit tests for truth-gating
- unit tests for scope fallback i `/rules/evaluation-truth`
- smoke-test oppdatert til truth-aware R-001-kontrakt
- Control Tower entry i `docs/audit/AgingOS_CONTROL_TOWER.md`

Det ble ikke laget en egen samlet `docs/audit/verification-...`-pakke i denne runden; verifikasjonen ligger i test/CI-artefakter og Control Tower.
