# Master logg (beslutninger + status)

Status: **GUIDANCE**  
Formål: Kort, løpende logg over beslutninger og status. Dette erstatter “levende” bruk av docx.  
Regel: Hvis kontrakter/ops/pilot-kriterier endres, legg inn 5–10 linjer her + lenker.

## Format (per entry)
- Dato (YYYY-MM-DD)
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

### YYYY-MM-DD — <Tittel>
- Endring:
- Lenker:
- Neste:
