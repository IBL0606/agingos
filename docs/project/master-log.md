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

### YYYY-MM-DD — <Tittel>
- Endring:
- Lenker:
- Neste:
