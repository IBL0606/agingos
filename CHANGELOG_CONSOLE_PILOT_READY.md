# AgingOS Console/UI — Pilot-Ready Changelog (Steg 1–10)

Dato (UTC): 2026-02-09  
Scope: Console/UI (statisk HTML/JS) + nginx proxy i container `agingos-console-1` (host :8080 → container :80).  
Repo: /opt/agingos  
Console path: /opt/agingos/services/console  

## 1) Formål
Gjøre Console/UI pilot-klar: stabilt UI som viser status, events, anomalier og ukentlig rapport, med tydelig auth/API-key-håndtering og en enkel operatør-flyt.

## 2) Operasjonell arkitektur (kort)
- Nginx i `agingos-console-1` serverer statiske sider og proxyer `/api/*` til backend:8000.
- Auth: `X-API-Key` (backend: `AGINGOS_AUTH_MODE=api_key`).
- UI lagrer API base/key lokalt i nettleseren (localStorage).

## 3) Filer i Console (pilot-relevante)
- `/opt/agingos/services/console/index.html`
- `/opt/agingos/services/console/events.html`
- `/opt/agingos/services/console/anomalies.html`
- `/opt/agingos/services/console/report.html`
- `/opt/agingos/services/console/proposals.html`
- `/opt/agingos/services/console/nginx.conf`

## 4) Endelig backup (Steg 10)
Backup dir:
- /opt/agingos/backups/console_final_20260209T195718Z

Tarball:
- /opt/agingos/backups/console_final_20260209T195718Z.tgz

Inkludert:
- Alle HTML-filer + nginx.conf
- Step8-backups for events.html:
  - events.html.bak_step8_prevtsfix_20260209T163214Z
  - events.html.bak_step8_fix743_20260209T164054Z
  - events.html.bak_step8_apimini_20260209T163545Z
  - events.html.bak_step8_apimini_20260209T163632Z
  - events.html.bak_step8_apimini2_20260209T163727Z
  - events.html.bak_step8_events_layout2_20260209T164426Z
  - events.html.bak_step8_events_layout2b_20260209T164518Z
  - events.html.bak_step8_events_overflowfix_20260209T164727Z

## 5) Pilot-verifikasjon (Steg 9) — PASS med bevis
### 5.1 Servering av sider (PASS)
Verifisert 200 på:
- http://192.168.4.68:8080/index.html
- http://192.168.4.68:8080/events.html
- http://192.168.4.68:8080/anomalies.html
- http://192.168.4.68:8080/proposals.html
- http://192.168.4.68:8080/report.html

### 5.2 Proxy + auth (PASS)
- Uten key: GET /api/health → 401
- Med key (`dev-key-2`): GET /api/health → 200 {"status":"ok"}
Backend env-bevis:
- AGINGOS_AUTH_MODE=api_key
- AGINGOS_API_KEY=dev-key-2

### 5.3 UI-endepunkter (PASS)
Verifisert HTTP 200 via proxy (med X-API-Key):
- /api/health
- /api/ai/status
- /api/anomalies/runner_status
- /api/baseline
- /api/baseline/status
- /api/events?limit=5 (200)
- /api/events?limit=50 (200)

Verifisert POST (med key):
- POST /api/anomalies/run_latest → 200 (counts returned)

### 5.4 Runtime UI-funksjoner (PASS)
Index (Status):
- "Oppdater status" oppdaterer banner + chips.
- System viser DEGRADED når expected rooms ikke er satt og/eller baseline coverage er lav.

Events:
- "Hent" laster events (eksempel: 1000 events i valgt periode).
- "Hent flere" fungerer (paginering; eksempel: 2000 events).
- "Tøm" fungerer.
- Romfilter fungerer.
- Dupe-vindu + "vis kun duplikater" finnes.

Anomalies:
- "Oppdater" fungerer (runner status OK).
- "Kjør anomalier (siste bucket)" fungerer (run_id + counts vises).

Report:
- "Oppdater rapport" fyller warnings/coverage/baseline.
- "Last ned driftpakke (JSON)" genererer JSON blob (application/json, size>0).

## 6) Pilot-ready: hva operatør må gjøre
### 6.1 Sett API-key i UI
- I UI: sett API base `/api` (default) og API-key.
- Verifisering: /api/health skal bli 200 når key er satt.

### 6.2 Sett "expected rooms"
- Expected rooms lagres lokalt i nettleseren (localStorage: `agingos_expected_rooms`).
- Hvis expected rooms ikke er satt: UI viser DEGRADED og warnings `expected_rooms_not_set`.

### 6.3 Forstå "DEGRADED" årsaker
Eksempler observert i pilot:
- Lav baseline coverage (room_bucket=0.1298 < 0.2) → baseline degraderes
- Unknown room events present → warnings
Disse er ikke nødvendigvis feil, men må tolkes i drift.

## 7) Kjente non-critical observasjoner (ikke P0)
- Report-siden gjør en auth-probe uten key (detectAuthMode):
  - GET /api/health uten key → 401 vises i DevTools som rød linje
  - Med key fungerer alt (health_with_key=200), og rapport/eksport fungerer
- Browser warning ved blob over HTTP:
  - "blob was loaded over an insecure connection" → forventet i HTTP-miljø (ikke blocker)

## 8) Rollback / restore (Console)
### 8.1 Rask rollback til final-backup
```bash
cd /opt/agingos
ts=20260209T195718Z
tar -C / -xzf /opt/agingos/backups/console_final_${ts}.tgz
docker compose up -d --force-recreate console
```

### 8.2 Restore enkeltfiler
```bash
cp -a /opt/agingos/backups/console_final_20260209T195718Z/index.html /opt/agingos/services/console/index.html
cp -a /opt/agingos/backups/console_final_20260209T195718Z/events.html /opt/agingos/services/console/events.html
cp -a /opt/agingos/backups/console_final_20260209T195718Z/anomalies.html /opt/agingos/services/console/anomalies.html
cp -a /opt/agingos/backups/console_final_20260209T195718Z/report.html /opt/agingos/services/console/report.html
cp -a /opt/agingos/backups/console_final_20260209T195718Z/proposals.html /opt/agingos/services/console/proposals.html
cp -a /opt/agingos/backups/console_final_20260209T195718Z/nginx.conf /opt/agingos/services/console/nginx.conf
docker compose up -d --force-recreate console
```

## 9) Hva som fortsatt er utsatt / TODO
- Steg 8 TODO: Index “ekte 3-kolonne dashboard” (utsatt).
- Eventuell polish: dempe 401-auth-probe logging i report.html (ikke P0).
