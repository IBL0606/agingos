# AgingOS — dokumentasjon, struktur og kode

[![CI](https://github.com/IBL0606/agingos/actions/workflows/ci.yml/badge.svg?event=push)](https://github.com/IBL0606/agingos/actions/workflows/ci.yml)


## Quick verification (Smoke test)
1. `make up` (evt `docker compose up -d --build`)
2. `make smoke` (evt `./examples/scripts/smoke_test.sh`)
3. `make down` (evt `docker compose down`)

---

## Testing / Scenario

Scenario-formatet er en **kontrakt for testing** og brukes av scenario runneren til å poste events og verifisere beregnede avvik via `GET /deviations/evaluate`.

- Format (schema + eksempler): `docs/testing/scenario-format.md`

Kjør scenario smoke-test:
```bash
make scenario
``` 
Kjør et spesifikt scenario (YAML/JSON):

./examples/scripts/scenario_runner.py docs/testing/scenarios/<filnavn>.yaml

Longrun-simulering (runbook): `docs/ops/longrun-sim.md`


## AgingOS – Sim-baseline: Regler R-001–R-003 + Avvik v1

Dette steget implementerer en tynn vertikal slice:
- Leser events fra DB
- Evaluerer regler (R-001, R-002, R-003)
- Returnerer Avvik v1 via endepunkt for evaluering

## Regler implementert

### R-001: Ingen bevegelse i våkentidsvindu
**Tolkning i denne slicen:**
- Vi bruker `since` og `until` i kall til API som “våkentidsvindu”.
- Vi sjekker om det finnes minst én event med `category=motion` i vinduet.
- Hvis det ikke finnes noen, returnerer vi ett avvik.

### R-002: Ytterdør åpnet på natt
**Tolkning i denne slicen:**
- Vi sjekker events med `category=door` i vinduet `[since, until)`.
- Hvis payload indikerer `state=open` (evt `value=open`) og tidspunktet er i nattetid (23:00–06:00), returnerer vi ett avvik.

### R-003: Dør åpnet, ingen bevegelse i etterkant
**Tolkning i denne slicen:**
- Vi finner dør-event som matcher “front door open” i vinduet `[since, until)`.
- Vi sjekker om det finnes motion-events med `state=on` (evt `value=on`) i de neste 10 minuttene etter dør-eventet.
- Hvis ingen bevegelse registreres i oppfølgingstiden, returnerer vi ett avvik.

---

## Avvik v1 (API-kontrakt)

Kontraktkrav for event-timestamps (UTC, ISO 8601) er dokumentert i: `docs/contracts/event-v1.md`.

### Avvik-livssyklus (OPEN/ACK/CLOSED + expire)
- Scheduler kan persistere avvik som `OPEN` når en regel trigger (for regler med `enabled_in_scheduler: true`).
- Et `OPEN` avvik kan settes til `ACK` via API for å markere at det er sett, men avviket regnes fortsatt som aktivt.
- Når regelen fortsatt trigger, oppdateres samme aktive avvik (OPEN/ACK) med ny `last_seen_at` og oppdatert kontekst/evidens.
- Et aktivt avvik (`OPEN` eller `ACK`) lukkes automatisk som `CLOSED` når det ikke har blitt sett igjen innen `expire_after_minutes`.
- Hvis regelen trigger igjen etter at avviket er `CLOSED`, opprettes en ny `OPEN` (ny episode).

Eksempel (liste OPEN avvik):
```bash
curl -sS "http://localhost:8000/deviations?status=OPEN&subject_key=default&limit=50" | jq .
```
Eksempel (sortert severity først):
```bash
curl -sS "http://localhost:8000/deviations" | jq -r '.[] | "\(.severity) \(.last_seen_at) \(.status) \(.rule_id) \(.subject_key)"' | head
```

Felt:
- `deviation_id` (UUID)
- `rule_id` (f.eks. "R-001")
- `timestamp` (tidspunktet avviket ble generert)
- `severity` ("LOW" / "MEDIUM" / "HIGH")
- `title`
- `explanation` (1–2 setninger, for mennesker)
- `evidence` (liste av event-id; kan være tom ved fravær av events)
- `window` (alltid satt):
  - `since`
  - `until`

---

## API

### GET /deviations/evaluate
Evaluerer regler over events i et tidsvindu og returnerer beregnede avvik (ikke lagret i DB).

**Query params:**
- `since` (ISO 8601)
- `until` (ISO 8601)

### Vinduskontrakt (VIKTIG)
- `since` er inkludert
- `until` er IKKE inkludert

Med andre ord: vinduet er “fra og med since, fram til men ikke med until”.
En event som skjer eksakt på `until` teller ikke med i dette vinduet.

### Helse
```bash
curl -s http://localhost:8000/health
```

## Konfigurasjon: regler (rule-config)

Rule-parametre (lookback, expire, terskler/tidsvinduer) er samlet i:
- `backend/config/rules.yaml`

Kontrakt/schema er dokumentert i:
- `docs/contracts/rule-config.md`

**Status:** Implementert: scheduler og R-002/R-003 leser parametre fra `backend/config/rules.yaml`.


### Feltoversikt

| Felt | Type | Eksempel | Effekt |
|---|---|---|---|
| `scheduler.interval_minutes` | int | `1` | Hvor ofte scheduler kjører |
| `scheduler.default_subject_key` | string | `"default"` | Default subject_key i persist-flow |
| `defaults.lookback_minutes` | int | `60` | Standard lookback hvis ikke overstyrt |
| `defaults.expire_after_minutes` | int | `60` | Standard expire hvis ikke overstyrt |
| `rules.<id>.enabled_in_scheduler` | bool | `true/false` | Om regelen er med i scheduler/persist-flow |
| `rules.<id>.lookback_minutes` | int | `60` | Evalueringsvindu bakover i tid |
| `rules.<id>.expire_after_minutes` | int | `60` | Stale-threshold for closing (OPEN/ACK) |
| `rules.<id>.params.*` | object | `{...}` | Regelspesifikke terskler/tidsvinduer |

---

## Troubleshooting: Hvis tider virker feil

Sjekkliste:
- Bekreft at du sender **UTC-aware** timestamps (ISO 8601 med `Z` eller `+00:00`). Naive timestamps uten timezone blir avvist.
- Verifiser vinduskontrakten: `[since, until)` der `until` er eksklusiv.
- Sjekk DB-timezone: `docker compose exec db psql -U agingos -d agingos -c "SHOW timezone;"`
- Hvis du filtrerer events/deviations med `since/until`, bruk alltid `...Z` (UTC).

Eksempel (gyldig):
```bash
curl -sS "http://localhost:8000/deviations/evaluate?since=2025-12-22T10:00:00Z&until=2025-12-22T11:00:00Z"
```

Ekstra dokumentasjonssetning: Policy ligger i `docs/policies/time-and-timezone.md`, kontraktkrav i `docs/contracts/event-v1.md`, og praktisk feilsøking i `README.md`.

## CI (GitHub Actions)

Repoet kjører CI på hver push og pull request:

- Lint/format (fail fast): `ruff format --check` og `ruff check`
- Docker-baserte tester: `make up` → `make smoke` → `make scenario` → `make down`

Daglig “hvordan lese CI” ligger i README.md, mens feilsøking og detaljer ligger i docs/ops/ci.md.
