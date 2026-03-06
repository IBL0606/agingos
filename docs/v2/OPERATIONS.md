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
