# Dokument-endringsjekk (v1)

Status: **NORMATIVE**  
Bruk denne når du har endret noe (kode, pilotoppsett, integrasjon), slik at dokumentasjon ikke driver ut av sync.

## Når kode endres (typisk)
- [ ] Påvirker det event-formatet? → oppdater `docs/contracts/event-v1.md`
- [ ] Påvirker det sensor/integrasjon? → oppdater `docs/mapping/sensor-event-mapping.md`
- [ ] Påvirker det scheduler/logging/backup? → oppdater `docs/ops/*`
- [ ] Påvirker det go/no-go eller pilotoppsett? → oppdater `docs/hw/*`
- [ ] Påvirker det scenarioer/test? → oppdater `docs/testing/*`
- [ ] Ligger temaet i INDEX? → oppdater `docs/INDEX.md` ved behov
- [ ] Noter beslutning/status (3–10 linjer) → `docs/project/master-log.md`
