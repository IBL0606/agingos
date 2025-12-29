# docs/hw/architecture.md
# Pilot-arkitektur v1 (RPi/HA sensorhub → AgingOS/DB på mini-PC)

## Formål
Denne arkitekturen beskriver Pilot #1 for AgingOS der Home Assistant (HA) på eksisterende Raspberry Pi fungerer som sensorhub, og en dedikert mini-PC kjører AgingOS + Postgres (Docker Compose). Pilotens mål er å verifisere stabil datainnhenting (Event v1), regel/avvik-flyt og operasjonell drift før hardware bestilles/utvides.

## Oversikt
**Komponenter**
- **Sensorer:** Aqara FP2 (stue/kjøkken), Aqara FP300 ×4 (gang/bad/soverom 1/2), Aqara Door/Window ×3 (inngang/bad/balkong), Aqara Mini Switch (assist-knapp).
- **Sensorhub:** Raspberry Pi (eksisterende) med Home Assistant.
- **Compute/DB:** Mini-PC (x86) med AgingOS + PostgreSQL (Docker Compose).
- **Kommunikasjon:** HA → HTTP POST til AgingOS `/event` på LAN.

**Datakjede**
Sensors → (Zigbee/Matter/HomeKit lokalt i HA) → Home Assistant automasjoner/rest_command → AgingOS `/event` → Postgres → rule_engine/scheduler → deviations.

## Nettverk og sikkerhetsmodell (pilot)
- Mini-PC og RPi står på samme LAN.
- Mini-PC har fast IP (DHCP reservation).
- AgingOS eksponerer port **TCP 8000** på LAN.
- **Port 8000 skal ikke eksponeres mot internett.**
- Anbefaling: brannmurregel på mini-PC som kun tillater TCP 8000 fra RPi sin IP.

## Roller og ansvar
- **RPi/HA**
  - Ansvar: integrere sensorer, normalisere signaler, sende Event v1 til AgingOS.
  - Beholder kun minimal historikk for feilsøking (kort retention).
- **Mini-PC**
  - Ansvar: system-of-record (Postgres), regel-/avvik-evaluering, scheduler, drift/logg/backup.

## Event-kontrakt (pilot)
HA skal sende Event v1 til `POST /event`. Pilot definerer følgende minimum:
- `timestamp`: UTC, ISO 8601
- `category`: en av: `presence`, `door`, `environment`, `assist_button`
- `payload`:
  - `source`: `"homeassistant"`
  - `room`: kontrollert romlabel (f.eks. `"stue_kjokken"`, `"gang"`, `"bad"`, `"soverom_1"`, `"soverom_2"`)
  - `entity_id`: HA entity_id
  - `state`: normalisert state
  - sensor-spesifikke felt:
    - `environment`: `temperature_c`, `humidity_pct`, `illuminance_lux` (der tilgjengelig)
    - `door`: `open|closed`
    - `presence`: `on|off`
    - `assist_button`: `single|double|hold`

**Rate limiting (pilot)**
- `presence`: kun transitions (`off→on`, `on→off`) + optional heartbeat (f.eks. hvert 10. minutt) hvis ønsket.
- `environment`: sampling (f.eks. hvert 5.–15. minutt), ikke hvert state-change.

## Bølgeplan (aktivering)
Bølger brukes for å redusere feilsøkingsflate. Innkjøp kan være “aggressivt”, men aktivering gjøres trinnvis.

### Bølge 0 – Infrastruktur/pipeline
- Mini-PC oppe med AgingOS+DB
- Nettverkstest RPi → mini-PC
- Brannmur: kun RPi → TCP 8000

Akseptkriterier:
- `/event` kan nås fra RPi
- Logging viser mottatt request
- Ingen errors i compose logs

### Bølge 1 – Kjerne (lav støy, høy verdi)
- FP2: stue/kjøkken (presence)
- Door/Window: inngang + bad + balkong
- Assist-knapp
- FP300: bad (presence + environment)

Akseptkriterier:
- Minst 24 timer uten “event drop” (event kommer inn ved reelle triggere)
- Ingen vedvarende “flapping” uten at det håndteres via rate-limit/debounce
- Avvik kan evalueres manuelt og persisteres (minst én test-deviation)

### Bølge 2 – Dekning
- FP300: gang
- FP300: soverom 1

Akseptkriterier:
- Minst 48 timer stabil drift
- Noisy entities ekskluderes fra HA recorder hvis nødvendig
- Ingen regressjoner i avvikslivssyklus (stale/close)

### Bølge 3 – Full dekning (valgfritt)
- FP300: soverom 2

Akseptkriterier:
- Minst 72 timer stabil drift
- Dokumentert “known issues” og mitigeringer

## Drift (pilot)
- Backup/restore: definert og testet (se go/no-go).
- Retention: beslutning dokumentert (AgingOS er system-of-record; HA holder minimal historikk).
- Observability: strukturerte logs for scheduler/ingest, og enkel “pilot-verification” sjekkliste.
