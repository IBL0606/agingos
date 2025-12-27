# Sensor → Event mapping (v1)

Dette dokumentet beskriver hvordan fysiske sensorer mappes til **Event v1** i AgingOS.
Målet er at alle upstream-integrasjoner (Home Assistant, Zigbee gateway, custom script, osv.) produserer samme, stabile event-format.

## Event v1 (input til /event)

Event-felter (se også `docs/contracts/event-v1.md`):
- `id` (UUID)
- `timestamp` (UTC, ISO 8601)
- `category` (string)
- `payload` (object)

Konvensjon:
- `category` bestemmer hvilke nøkler vi forventer i `payload`.
- Bruk alltid små bokstaver i `category` og payload-verdier.

---

## Mapping: sensorer (første HW / v1)

### 1) PIR bevegelsessensor (motion)

**Category**
- `motion`

**Payload (minimum)**
- `state`: `"on"` | `"off"`
  - Alternativt aksepterer regelmotoren `value`, men standardiser på `state`.

**Eksempel (motion on)**
```json
{
  "id": "00000000-0000-0000-0000-000000000010",
  "timestamp": "2025-12-27T12:00:00Z",
  "category": "motion",
  "payload": { "state": "on" }
}
```

**Bruk i regler**
- R-001: sjekker at det finnes minst én `motion` event i vinduet.
- R-003: ser etter `motion` med `state/value == "on"` i oppfølgingsvindu.

---

### 2) Dørkontakt ytterdør (front door contact)

**Category**
- `door`

**Payload (minimum)**
- `door`: `"front"` (må være eksakt `"front"` i v1)
- `state`: `"open"` | `"closed"`
  - Alternativt aksepterer R-002 også `value`, men standardiser på `state`.

**Eksempel (front door open)**
```json
{
  "id": "00000000-0000-0000-0000-000000000020",
  "timestamp": "2025-12-27T23:30:00Z",
  "category": "door",
  "payload": { "door": "front", "state": "open" }
}
```

**Bruk i regler**
- R-002: trigger hvis `door`-event har `state/value == "open"` og timestamp er i nattvindu.
- R-003: trigger kun hvis `door == "front"` og `state/value == "open"`, og det ikke finnes `motion on` i oppfølgingsvindu.

---

## Test / verifikasjon (lokalt)

Post et event:
```bash
ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

curl -sS \
  -H "Content-Type: application/json" \
  -d "{\"id\":\"$ID\",\"timestamp\":\"$TS\",\"category\":\"motion\",\"payload\":{\"state\":\"on\"}}" \
  http://localhost:8000/event
```

Merk: I feltprofil med API-key må du sende `X-API-Key`-header på alle kall.

---
