# AgingOS — dokumentasjon, struktur og kode

## Quick verification (Smoke test)
1. `make up` (evt `docker compose up -d --build`)
2. `make smoke` (evt `./examples/scripts/smoke_test.sh`)
3. `make down` (evt `docker compose down`)

---

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


