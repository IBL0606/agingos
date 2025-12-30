# Sensor → Event mapping (v1)

Status: **NORMATIVE**  
Formål: Alle upstream-integrasjoner (Home Assistant, Zigbee, scripts, osv.) skal produsere samme, stabile Event-format.

Dette dokumentet er “hjemmet” for:
- kategori-register (hvilke `category` som finnes)
- payload-konvensjoner (felles felter)
- konkrete sensor-mappinger og eksempler

Se også: `docs/contracts/event-v1.md`.

---

## Event v1 (input til /event)

Event-felter:
- `id` (UUID)
- `timestamp` (UTC, ISO 8601)
- `category` (string)
- `payload` (object)

---

## Kategori-register (v1)

### Implementert i kode per i dag
Disse brukes av regelmotoren og scenarioene:
- `motion`
- `door`

### Planlagt for pilot/HW (ikke implementert i kode ennå)
Disse er ønsket for HA-pilot, men må innføres i kode før de er normative:
- `presence`
- `environment`
- `assist_button`

**Viktig regel for å unngå konflikt:**  
Hvis kode og docs er uenige, vinner kode. Inntil `presence` er implementert i kode, mappes “presence-sensorer” til `motion` i Event v1.

---

## Payload – felles konvensjoner (v1)

### Minimum (bør alltid være med)
- `state`: normalisert tilstand (se per kategori under)

### Anbefalt for Home Assistant (gir sporbarhet i pilot)
- `source`: f.eks. `"homeassistant"`
- `room`: kontrollert romlabel (f.eks. `"stue_kjokken"`, `"gang"`)
- `entity_id`: HA `entity_id` (f.eks. `"binary_sensor.front_door_contact"`)
- `state`: normalisert state

### Legacy-kompatibilitet
I eldre dokumenter kan du se `payload.location`. Vi standardiserer på `payload.room`.
- **Standard nå:** `payload.room`
- **Legacy:** `payload.location` skal ikke brukes i nye integrasjoner. Hvis det dukker opp, må det mappes til `room` før eventet sendes inn.

---

## Mapping: sensorer (første HW / v1)

### 1) PIR / presence-signal (brukes som `motion` i kode v1)

**Category**
- `motion`

**Payload (minimum)**
- `state`: `"on"` | `"off"`

**Eksempel (motion on)**
```json
{
  "id": "00000000-0000-0000-0000-000000000010",
  "timestamp": "2025-12-27T12:00:00Z",
  "category": "motion",
  "payload": { "state": "on", "room": "stue_kjokken", "source": "homeassistant", "entity_id": "binary_sensor.fp2_presence" }
}
```

**Bruk i regler**
- R-001: sjekker at det finnes minst én `motion` event i vinduet.
- R-003: ser etter `motion` med `state == "on"` i oppfølgingsvindu.

---

### 2) Dørkontakt ytterdør (front door contact)

**Category**
- `door`

**Payload (minimum)**
- `door`: `"front"` (må være eksakt `"front"` i v1)
- `state`: `"open"` | `"closed"`

**Eksempel (front door open)**
```json
{
  "id": "00000000-0000-0000-0000-000000000020",
  "timestamp": "2025-12-27T23:30:00Z",
  "category": "door",
  "payload": { "door": "front", "state": "open", "room": "gang", "source": "homeassistant", "entity_id": "binary_sensor.front_door_contact" }
}
```

**Bruk i regler**
- R-002: trigger hvis `door`-event har `state == "open"` og timestamp er i nattvindu.
- R-003: trigger kun hvis `door == "front"` og `state == "open"`, og det ikke finnes `motion on` i oppfølgingsvindu.

---

## Rate limiting / støy (pilot-anbefaling)

Dette er operative retningslinjer som normalt settes i HA (ikke i AgingOS):
- `motion`/presence: send kun transitions (`off→on`, `on→off`) + evt. heartbeat (f.eks. hver 10. min) hvis du trenger “system lever”-signal.
- `environment` (når innført): sampling hvert 5–15 min (ikke hvert state-change).

---

## Test / verifikasjon (lokalt)

Post et event:
```bash
ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
API_KEY=dev-key-1

curl -sS \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d "{\"id\":\"$ID\",\"timestamp\":\"$TS\",\"category\":\"motion\",\"payload\":{\"state\":\"on\"}}" \
  http://localhost:8000/event
```

Merk: I feltprofil med API-key må du sende `X-API-Key`-header på alle kall.


### Optional: `payload.raw` (debug)
- Kan brukes av upstream (HA/script) for å lagre originalt rå-payload (best effort).
- **Skal ikke brukes i regler** eller som del av kontrakt/semantikk (kun feilsøking).
