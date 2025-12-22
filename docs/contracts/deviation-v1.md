# Deviation contract (AgingOS) — v1

## Formål
Definerer minimumskontrakten for persisterte avvik (deviations) og hvordan systemet identifiserer “samme” aktive avvik over tid.

**Status:** Avvik v1 er gjeldende; modellen ligger i `backend/models/deviation.py` og brukes av både API (`/deviations`) og scheduler.

## Deviation key-policy (aktivt avvik)
Et **aktivt avvik** identifiseres av:
- `rule_id` (FK til `rules.id`)
- `subject_key` (string)

Det skal aldri finnes mer enn **én** aktiv rad for samme `(rule_id, subject_key)` samtidig.

**Aktive statuser:**
- `OPEN`
- `ACK`

**Konsekvens (upsert):**
- Når scheduler finner at en regel fortsatt trigger, skal eksisterende aktiv rad (OPEN/ACK) oppdateres (f.eks. `last_seen_at`, `context`, `evidence`, `severity`), og det skal ikke opprettes en ny rad.

## Reopen-policy (etter CLOSED)
Når et avvik er `CLOSED` og regelen trigger på nytt, opprettes en **ny** `OPEN` rad (ny episode), fordi det ikke finnes en aktiv rad å upserte.

## subject_key-policy (minimalt)
I nåværende thin-slice/persist-flow brukes én “default subject”:
- Scheduler bruker `scheduler.default_subject_key` fra `backend/config/rules.yaml`.
- Standardverdi er `"default"`.

## Fremtidig utvidelse
Kontrakten utvides senere med eksplisitt identifikator for bolig/enhet, f.eks.:
- `home_id`
- `device_id`

Ved innføring av slike felter skal key-policy revurderes og versjoneres.

## API: sortering for GET /deviations
`GET /deviations` returnerer avvik sortert slik:

1) **Primær:** `severity` synkende (HIGH > MEDIUM > LOW)
2) **Sekundær:** `last_seen_at` synkende (nyeste først innen samme severity)

### Eksempel (illustrativt)
```json
[
  { "severity": 3, "last_seen_at": "2025-12-22T10:05:00Z", "status": "OPEN", "rule_id": 2, "subject_key": "default" },
  { "severity": 2, "last_seen_at": "2025-12-22T10:04:00Z", "status": "ACK",  "rule_id": 1, "subject_key": "default" },
  { "severity": 1, "last_seen_at": "2025-12-22T09:59:00Z", "status": "OPEN", "rule_id": 3, "subject_key": "default" }
]
```

**Ekstra dokumentasjonssetning:** Kontrakt dokumenteres i `docs/contracts/deviation-v1.md`, mens begrunnelse/valg dokumenteres i `docs/adr/` og lenkes fra Master arbeidslogg.
**Ekstra dokumentasjonssetning:** API-garantier (inkl. sortering) ligger i `docs/contracts/deviation-v1.md`, mens praktisk bruk (curl) ligger i `README.md`.

