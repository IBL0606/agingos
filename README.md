# agingos
AgingOS — dokumentasjon, struktur og kode

# Quick verification (Smoke test)
1. make up (evt <docker compose up -d --build>)
2. make smoke (evt <./examples/scripts/smoke_test.sh>)
3. make down (evt <docker compose down>)

____________________________________________________________________________
# AgingOS – Thin slice: Regel R-001 + Avvik v1

Dette steget implementerer en tynn vertikal slice:
- Leser events fra DB
- Evaluerer én regel (R-001)
- Returnerer Avvik v1 via et enkelt endepunkt

## Regel implementert

### R-001: Ingen bevegelse i våkentidsvindu
**Tolkning i denne slicen:**
- Vi bruker `since` og `until` i kall til API som “våkentidsvindu”.
- Vi sjekker om det finnes minst én event med `category=motion` i vinduet.
- Hvis det ikke finnes noen, returnerer vi ett avvik.

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

## Quick verification

Helse:

curl -s http://localhost:8000/health
____________________________________________________________________________