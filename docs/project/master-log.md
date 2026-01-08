# Master logg (beslutninger + status)

Status: **GUIDANCE**  
Formål: Kort, løpende logg over beslutninger og status. Dette erstatter “levende” bruk av docx.  
Regel: Hvis kontrakter/ops/pilot-kriterier endres, legg inn 5–10 linjer her + lenker.

## Format (per entry)
- ### Dato (YYYY-MM-DD) -- Overskrift
- Hva endret seg
- Hvor er sannheten nå (lenker)
- Neste steg

---

## Entries

### 2025-12-29 — Dokumentasjon reset v1 (start)
- Beslutning: Repo (`README.md` + `docs/`) er living source of truth. Docx/xlsx er legacy snapshots.
- Lagt til: `docs/INDEX.md`, dokument-policy, legacy-indeks, endringsjekk.
- Lenker:
  - `docs/INDEX.md`
  - `docs/policies/documentation-policy.md`
  - `docs/_legacy/README.md`
- Neste: Rydde bort duplisering ved å lenke til “hjemmedokumenter” i `docs/contracts/`, `docs/mapping/`, `docs/ops/`, `docs/hw/`.

### 2025-12-30 — Dokumentasjon reset v1 (fullført)
- Beslutning: All videre teknisk sannhet ligger i repo (`README.md` + `docs/`). Legacy `.docx/.xlsx` er frosset som snapshots.
- Legacy er samlet i `docs/_legacy/` og har tydelig banner/INFO slik at de ikke konkurrerer med markdown-dokumentasjonen.
- “Hjemmedokumenter” (én sannhet):
  - Event v1: `docs/contracts/event-v1.md`
  - Sensor→Event mapping: `docs/mapping/sensor-event-mapping.md`
  - Pilot-arkitektur: `docs/hw/architecture.md` (+ BOM: `docs/hw/pilot-bom.md`)
- Neste: Når du ser duplisert tekst i repo, behold én versjon og lenk fra resten (ikke kopier).


### 2025-12-30 — Legacy-docx: nøkkelinnhold portet til repo
- Flyttet nødvendig prosjektinfo ut av docx og inn i repo (`docs/`):
  - Visjon: `docs/project/vision.md`
  - MVP: `docs/project/mvp.md`
  - Status/avgrensninger: `docs/project/status.md`
  - Stopp-kriterier: `docs/project/stop-criteria.md`
  - Regel-katalog: `docs/rules/rule-catalog.md`
  - API-endepunkter: `docs/api/http-api.md`
- Legacy `.docx/.xlsx` beholdes kun som historikk i `docs/_legacy/`.

### 2025-12-31 - Installasjonsklart + runbook for feltpilot
- Hva endret seg:
  - Laget en amatørevennlig runbook (`docs/ops/runbook.md`) som “source of truth” for oppstart/stopp, smoke, logs, backup/restore og feltprofil.
  - Forbedret ops-dok slik at det kan følges uten å “huske” ting: logging (hurtigguide + fullført kontrakt), backup/restore (amatør-proof), security minimum (30-sekunders forklaring + rotasjon)
  - Verifisert i praksis: dev-profil fungerer end-to-end (up → smoke → backup/restore → down). Feltprofil fungerer med API-key (inkl. rotasjon med overlapp).
- Hvor er sannheten nå (lenker):
  - Runbook (amatør steg-for-steg): `docs/ops/runbook.md`
  - Logging (hurtigguide + kontrakt): `docs/ops/logging.md`
  - Backup/restore (detaljer + verifikasjon): `docs/ops/backup-restore.md`
  - API-key (setup + rotasjon): `docs/ops/security-minimum.md`
  - README (inngangspunkt): `README.md`

### 2025-12-31 -- P1: HA→AgingOS mini-plan + bølgeplan (uten HW)
- Hva endret seg
  - Opprettet mini-plan for HA→AgingOS: docs/mapping/ha-mini-plan-p1.md (forventede entity_id-er, payload-felter, transitions-only rate-limit, sjekkliste).
  - Oppdatert bølgeplan i docs/hw/architecture.md slik at Bølge 1 matcher faktisk første installasjon: FP2 (stue/kjøkken) + ytterdør (inngangsdør).
  - Lagt inn eksplisitt lenke under Bølge 1 til mini-planen (sjekkliste/verifisering).
  - Oppdatert docs/INDEX.md slik at mini-planen er synlig i dokumentasjonsindeksen.
- Hvor er sannheten nå (lenker)
  - Mini-plan (P1): docs/mapping/ha-mini-plan-p1.md
  - HW arkitektur + bølgeplan: docs/hw/architecture.md
  - Sensor→Event mapping (normativ): docs/mapping/sensor-event-mapping.md
  - Event v1 (normativ): docs/contracts/event-v1.md
  - Dokumentasjonsindeks (normativ): docs/INDEX.md
- Neste steg
  - Når HW er på bordet: implementer HA automasjoner/rest_command for ytterdør + FP2 i stue/kjøkken, og verifiser end-to-end iht mini-planen. Legg inn debounce/dedupe i HA ved behov.

### 2026-01-05 — P2: Next 2 weeks after install (install → ingest → første regler → observability → læring)
- Hva endret seg
  - Lagt inn en enkel, konkret 2-ukers plan etter installasjon som beskriver hva som skal gjøres i rekkefølge, og hva som er “ferdig” per steg.
- Hvor er sannheten nå (lenker)
  - Go/No-Go (beslutningskriterier): `docs/hw/go-no-go.md`
  - Runbook (oppskrifter, inkl. M1–M8): `docs/ops/runbook.md`
  - HA mini-plan (pilot #1): `docs/mapping/ha-mini-plan-p1.md`
  - Regel-katalog (idébank): `docs/rules/rule-catalog.md`
  - Logging/observability (hva du ser etter): `docs/ops/logging.md`
- Neste steg (2 uker etter install)
  1) **Install (Dag 0–1)**
     - Start feltprofil på mini-PC: `make field-up`.
     - Kjør Go/No-Go minimum: M1–M3 (health, startup, ingest→DB) iht. runbook seksjon E.
     - Output: “Bølge 0 – Infrastruktur” er grønn, og du har en loggført statuslinje i denne master-loggen.

  2) **Ingest (Dag 1–3)**
     - Koble HA→AgingOS for første rom + ytterdør iht. mini-plan (transitions-only).
     - Verifiser at events kommer inn med riktig `category/payload/entity_id` og at støy er håndtert (exclude/noisy entities / rate-limit).
     - Output: Stabil ingest fra FP2 + ytterdør, og en enkel oversikt over “forventede events” vs “faktiske events”.

  3) **Første regler (Dag 3–7)**
     - Implementer 2–3 første regler (minste nyttige sett):
       - Ytterdør åpen “for lenge” (stale open)
       - Manglende bevegelse i stue/kjøkken innen definert tidsvindu (inaktivitet)
       - (Valgfri) Assist-button → “eskaler” event/markør
     - Kjør `make scenario-reset` + `make scenario` for å verifisere determinisme.
     - Output: Regler produserer forventet output på syntetiske scenarioer, og minst én regel er validert på reelle pilot-events.

  4) **Observability (Dag 5–10)**
     - Sikre at du kan svare på disse på ≤5 minutter: “kommer events inn?”, “hvor mange per time?”, “har vi errors?”, “crasher containere?”, “vokser DB ukontrollert?”
     - Innfør rutine: daglig sjekk av logs + event-rate, og ukentlig backup.
     - Output: Et fast “health/ingest/DB”-sjekksett (kommandoer + forventning) som kan kjøres av ikke-utvikler.

  5) **Læring (Dag 10–14)**
     - Kjør 24–72h stabilitetstest (observér restarts, støy, hull i data) og oppdater mapping/rate-limit ved behov.
     - Notér 3 funn: (a) hva som gir mest verdi, (b) hva som er mest noisy, (c) hva som mangler av sensordekning.
     - Output: Beslutning om Bølge 2 (GO/PAUSE/STOP) basert på Go/No-Go + 2-ukers erfaring.

### 2026-01-08 — HA PIR→AgingOS eventflyt (ULID-støtte for `id`)
- Endring:
  - **AgingOS API:** Utvidet validering av `POST /event` slik at feltet `id` aksepterer **UUID eller ULID** (Home Assistant `context.id` er ULID). Dette fjerner 422-feil og gjør at HA kan sende unik id per trigger uten helpers/scripts.
    - Implementert i `backend/models/event.py` ved å endre `Event.id` fra `UUID` → `str` og legge til validator som godkjenner UUID eller ULID.
  - **Home Assistant (lokal konfig):**
    - La inn minimal `rest_command.agingos_event` i `configuration.yaml` som sender `category=motion` og payload (`room/entity_id/state/source`) til `http://192.168.4.62:8000/event` med `X-API-Key`.
    - Opprettet én UI-automation for `binary_sensor.multisensor_6_motion_detection` (bad) som trigges på `on` og `off` og kaller `rest_command.agingos_event` med `event_id = trigger.to_state.context.id` (ULID).
  - **Verifisering:**
    - `curl` mot `/event` med ULID ga `200 OK`.
    - Postgres verifisert med `SELECT … WHERE payload->>'entity_id'='binary_sensor.multisensor_6_motion_detection'` og observerte `category=motion`, `state on/off`, og ULID i `event_id`.
    - Slettet tidligere test-events med hardkodet UUID `…0123` fra DB.
- Lenker:
  - `backend/models/event.py` (Event-schema + id-validator)
  - `backend/main.py` (`POST /event` lagrer `event_id=str(event.id)`)
  - Home Assistant: `configuration.yaml` → `rest_command.agingos_event` (lokalt)
  - Home Assistant: UI Automation → “AgingOS PIR bad test” (lokalt)
  - DB: tabell `events` (`event_id`, `timestamp`, `category`, `payload`)
- Neste:
  - Dokumentere eksplisitt i API-kontrakt at `id` støtter UUID/ULID.
  - Legge til en liten API-test som verifiserer at ULID aksepteres (hindrer regresjon tilbake til UUID-only).
  - (Valgfritt) Beskrive “lokal HA deploy” i docs (rest_command + én automation) som repeterbar prosedyre.


### YYYY-MM-DD — <Tittel>
- Endring:
- Lenker:
- Neste:
