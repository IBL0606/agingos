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


## Weekly report (Fixpack-5 / MUST-3)
- Host page: `services/console/report.html` (`/report.html`).
- Purpose: non-technical weekly summary with four fixed sections:
  - `Data inn`
  - `Romdekning`
  - `Alarmer`
  - `Endringer`
- Truth-source reuse (no parallel reporting stack):
  - `Data inn` + `Romdekning`: derived from `GET /events` (same source already used by report/driftpakke).
  - `Alarmer`: `GET /anomalies?last=7d`.
  - `Endringer`: `GET /proposals` and nested `actions[].created_at/action`.
- Weekly truth labels are mandatory per section:
  - `REAL`: at least 7 days observed event span exists.
  - `TEMPLATE/FALLBACK`: source exists, but observed data is <7 days or zero rows.
  - `NO_EVIDENCE`: source missing/unavailable, or no truthful source exists.
- Rule: never present one-week real coverage unless ≥7 days observed span is verified from event timestamps.

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
