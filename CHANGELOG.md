# Changelog

## sim-baseline-v1 — 2025-12-18
**Tag:** sim-baseline-v1  
**Commit:** b0d764609cb4f2cf0268c0953f50fab4ef7cc0fa

### Hva som inngår (features)
- Docker Compose stack: FastAPI backend + Postgres
- Makefile targets: `make up`, `make down`, `make logs`, `make smoke`
- Event v1 pipeline:
  - `POST /event`
  - `GET /events` med filtre (category/since/until/limit)
- Regel-evaluering (ikke-persist):
  - `GET /deviations/evaluate` med vinduskontrakt: `[since, until)` (until er eksklusiv)
  - Regler i scope: R-001, R-002, R-003 (verifisert via smoke test)
- Persistente avvik (Avvik v1):
  - `POST /deviations/persist?since=...&until=...&subject_key=default`
  - `GET /deviations?status=OPEN&subject_key=default&limit=...`
  - `deviations_v1` tabell
- Scheduler-policy:
  - Persist/oppdater kun R-002 og R-003 (R-001 kjøres ikke i scheduler for å unngå støy)
- Menneskelig oversikt:
  - `GET /deviations/summary` (human overview)

### Kjente begrensninger
- R-001 er bevisst ikke med i scheduler/persist-flow (kun evaluering), for å unngå støy.
- `subject_key` er per nå hardkodet/brukes som `default` (ikke multi-home/device strategi).
- DB-håndtering av tid kan være “naiv timestamp” internt selv om API bruker ISO8601 `Z` (standardisering til UTC gjennom hele kjeden er en åpen beslutning).
- Severity-sortering/“top N viktigste” er ikke implementert som enhetlig prioriteringslogikk i DB/listing.

### Hvordan reprodusere (deterministisk)
1. Start stack:
   - `make up` (evt. `docker compose up -d --build`)
2. Kjør smoke test:
   - `make smoke` (evt. `./examples/scripts/smoke_test.sh`)
   - Smoke gjør deterministisk kjøring ved å truncate `events` og `deviations_v1`, poster faste event-id’er, og verifiserer:
     - `/health`
     - event-listing og filtre
     - `GET /deviations/evaluate` for R-001 boundary (until eksklusiv), R-002 og R-003
     - `POST /deviations/persist` og `GET /deviations` for persisted R-002/R-003
3. Stopp stack:
   - `make down`

---

## baseline-thinslice-v1 — 2025-12-15
**Tag:** baseline-thinslice-v1  
**Commit:** 03060ba

### Hva som inngår (features)
- Event v1 + deterministic smoke test
- Regel R-001–R-003 tilgjengelig via `GET /deviations/evaluate`
- Thin-slice kontrakter og verifikasjon (pre “persist deviations v1”)

### Kjente begrensninger
- Persistente avvik (deviations_v1) ikke inkludert i denne baselinen.

### Hvordan reprodusere
- Samme Quick verification-prinsipp (start stack, kjør smoke, stopp stack), men uten persisteringssteg.
