# Scenario format (AgingOS testing contract)

Dette dokumentet definerer scenario-formatet som brukes av scenario runneren for å poste events og verifisere beregnede avvik via `GET /deviations/evaluate`.

Scenario-formatet er en **kontrakt for testing**. Endringer her skal gjøres bevisst og sammen med oppdatering av runner og scenarioer.

## Forutsetninger

- Alle timestamps skal være **UTC timezone-aware** (ISO 8601 med `Z` eller eksplisitt offset).
- Scenario-kjøring skal starte fra ren database for determinisme:
  - `make scenario-reset` truncater `events`, `deviations_v1`, `deviations`.

## API-kontrakter (grunnlag)

### Post event
- Endpoint: `POST /event`
- Request body:
  - `id` (UUID, required)
  - `timestamp` (datetime, required, UTC-aware)
  - `category` (string, required)
  - `payload` (object, optional, default `{}`)

### Evaluer avvik
- Endpoint: `GET /deviations/evaluate?since=...&until=...`
- Parametre:
  - `since` (datetime, required, UTC-aware)
  - `until` (datetime, required, UTC-aware)
- Vindu: `[since, until)` der `until` er eksklusiv
- Response: `List[DeviationV1]`

### DeviationV1 schema (response)
Hvert avvik i responsen følger:
- `deviation_id` (UUID, generert)
- `rule_id` (string)
- `timestamp` (datetime)
- `severity` (string)
- `title` (string)
- `explanation` (string)
- `evidence` (list[UUID]) – event-id-er som støtter avviket
- `window` (object):
  - `since` (datetime)
  - `until` (datetime)

## Scenario-fil (YAML/JSON)

Scenario kan skrives i YAML eller JSON. Felt og semantikk er identiske.

### Top-level felter

| Felt | Type | Required | Beskrivelse |
|------|------|----------|-------------|
| `id` | string | ja | Unik scenario-id (brukes i output/logging). |
| `description` | string | nei | Kort forklaring av hensikten. |
| `events` | list[Event] | ja | Events som postes til `POST /event`. |
| `evaluate` | object | ja | Evalueringsvindu som sendes til `GET /deviations/evaluate`. |
| `expect` | object | ja | Forventet resultat og PASS/FAIL-regel. |

### Event objekt

| Felt | Type | Required | Beskrivelse |
|------|------|----------|-------------|
| `id` | UUID (string) | ja | Event-id. Skal være stabil og eksplisitt i scenariofilen. |
| `timestamp` | datetime (string) | ja | ISO 8601 UTC-aware, f.eks. `2025-12-23T10:00:00Z`. |
| `category` | string | ja | Event kategori (f.eks. `motion`, `door`). |
| `payload` | object | nei | Ekstra data (default `{}`). |

### Evaluate objekt

| Felt | Type | Required | Beskrivelse |
|------|------|----------|-------------|
| `since` | datetime (string) | ja | Start av evalueringsvindu. |
| `until` | datetime (string) | ja | Slutt av evalueringsvindu (eksklusiv). |

### Expect objekt

| Felt | Type | Required | Beskrivelse |
|------|------|----------|-------------|
| `pass_condition` | enum | ja | `exact` eller `contains`. |
| `deviations` | list[ExpectedDeviation] | ja | Liste over forventede avvik. |

`pass_condition`:
- `contains`: Faktiske avvik må inneholde minst de forventede (ekstra avvik tillates).
- `exact`: Faktiske avvik må matche forventningene uten ekstra avvik (streng).

### ExpectedDeviation objekt

Følgende matcher brukes. Kun `rule_id` er obligatorisk.

| Felt | Type | Required | Match-regel |
|------|------|----------|------------|
| `rule_id` | string | ja | Eksakt match. |
| `severity` | string | nei | Eksakt match hvis oppgitt. |
| `title` | string | nei | Eksakt match hvis oppgitt. |
| `explanation_contains` | string | nei | Substring må finnes i `explanation`. |
| `evidence_contains` | list[UUID] | nei | Alle oppgitte UUID-er må finnes i `evidence` (subset). |
| `window` | object | nei | Hvis oppgitt: `since` og `until` må matche eksakt. |

Merknader:
- `deviation_id` skal **ikke** brukes som matcher (genereres ved kjøring).
- `timestamp` på avvik settes til serverens “nå” (`utcnow()` på server). Derfor anbefales det å ikke kreve eksakt `timestamp`-match i scenarioene.

## PASS/FAIL definisjon

1. Runner resetter DB (`make scenario-reset`).
2. Runner poster alle events i scenariofilen til `POST /event`.
3. Runner kaller `GET /deviations/evaluate?since=...&until=...`.
4. Runner matcher response mot `expect.deviations` iht. match-reglene over.
5. PASS/FAIL avgjøres av `pass_condition` (`contains` eller `exact`).

## Eksempel (YAML)

```yaml
id: sc_r001_no_motion_basic
description: "Ingen motion i vinduet skal gi R-001"
events:
  - id: "11111111-1111-1111-1111-111111111111"
    timestamp: "2025-12-23T10:00:00Z"
    category: "motion"
    payload: { state: "on" }
evaluate:
  since: "2025-12-23T10:00:00Z"
  until: "2025-12-23T11:00:00Z"
expect:
  pass_condition: contains
  deviations:
    - rule_id: "R-001"
      explanation_contains: "Ingen"
```

Eksempel (JSON)
```json
{
  "id": "sc_r001_no_motion_basic",
  "description": "Ingen motion i vinduet skal gi R-001",
  "events": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "timestamp": "2025-12-23T10:00:00Z",
      "category": "motion",
      "payload": { "state": "on" }
    }
  ],
  "evaluate": {
    "since": "2025-12-23T10:00:00Z",
    "until": "2025-12-23T11:00:00Z"
  },
  "expect": {
    "pass_condition": "contains",
    "deviations": [
      {
        "rule_id": "R-001",
        "explanation_contains": "Ingen"
      }
    ]
  }
}
```
