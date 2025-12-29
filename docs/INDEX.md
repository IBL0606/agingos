# Dokumentasjonsindeks (AgingOS) — v1

Status: **NORMATIVE**  
Formål: Dette er **startpunktet**. Hvis du lurer på “hvor skal jeg oppdatere dette?”, så er svaret alltid her.

## Regler (v1)
- **Én sannhet:** Levende teknisk dokumentasjon ligger i `README.md` og `docs/`.
- **Ingen duplisering:** Hvert tema har **ett** “hjemmedokument”. Andre steder lenker vi dit.
- **Legacy er read-only:** `.docx/.xlsx` beholdes kun som historikk (snapshot) og skal ikke konkurrere med repo-dokumentasjonen.
- **Ved konflikt:** Kode → `docs/contracts/` → øvrige `docs/` → `README.md` → legacy.

---

## Start her
- Kjøre / install / feilsøke: `../README.md`
- Dokumentasjonsregler: `policies/documentation-policy.md`
- Endringsjekk (husk docs når kode endres): `policies/doc-change-checklist.md`

---

## Kontrakter (normative format/API)
- Event v1: `contracts/event-v1.md`
- Deviation v1 (persistert): `contracts/deviation-v1.md`
- Rule config: `contracts/rule-config.md`

---

## Mapping (integrasjoner → Event v1)
- Sensor → Event mapping (inkl. kategori-register og payload-konvensjoner): `mapping/sensor-event-mapping.md`

---

## Arkitektur
- Rule engine: `architecture/rule-engine.md`
- Beslutninger (ADR): `adr/`

---

## Drift (runbooks)
- Logging: `ops/logging.md`
- Scheduler: `ops/scheduler.md`
- Backup/restore: `ops/backup-restore.md`
- CI: `ops/ci.md`
- Incident template: `ops/incident-template.md`
- Longrun-sim: `ops/longrun-sim.md`
- Security minimum: `ops/security-minimum.md`

---

## HW / Pilot
- Pilot-arkitektur: `hw/architecture.md`
- Go/No-Go: `hw/go-no-go.md`
- Pilot BOM: `hw/pilot-bom.md`

---

## Testing
- Determinisme / tid: `testing/determinism.md`
- Scenario-format: `testing/scenario-format.md`
- Scenario-katalog: `testing/scenario-catalog.md`
- Status-flow: `testing/status-flow.md`
- Scenario-filer: `testing/scenarios/`

---

## Prosjekt
- Master logg (beslutninger + status): `project/master-log.md`
- Ordliste (glossary): `project/glossary.md`

---

## Legacy snapshots (read-only)
- Legacy indeks: `_legacy/README.md`
