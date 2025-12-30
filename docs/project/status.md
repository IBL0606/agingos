# Prosjektstatus og avgrensninger

Status: **GUIDANCE**  
Formål: Én side som sier “hva er AgingOS nå”, “hva er det ikke”, og hvilke beslutninger som må tas før hardware.

## Hva AgingOS er i dag (software)
AgingOS er et lokalt kjørt, Docker-basert backend-system som:
- mottar, lagrer og lister events (Event v1)
- evaluerer et thin-slice av regler (R-001–R-003) og produserer avvik (Avvik v1)
- kan kjøres som:
  - beregning via API (`GET /deviations/evaluate`)
  - persist via scheduler (for regler aktivert i `rule-config`)

## Hva AgingOS ikke er (ennå)
- full “smarthusplattform”
- ferdig varslings-/notifiseringsprodukt (kan være manuelt/API i MVP)
- hardware-installasjon er eksplisitt holdt igjen til stopp-kriterier er oppfylt

## Nåværende software-status (stikkord)
- Grunnplattform: Docker Compose + FastAPI + PostgreSQL
- Event-modell/kontrakt: Event v1 dokumentert og brukt
- Regelmotor: konsolidert i rule_engine (én sannhet)
- Avvik: både beregnet (evaluate) og persistert (scheduler) støttes

## Åpne beslutninger (låses før hardware)
- subject_key-strategi utover midlertidig `default`
- når/hvordan R-001 skal automatiseres uten å skape støy

## Stopp-kriterier før hardware
Se `docs/project/stop-criteria.md`.

## Kilde
Sammenfattet fra `docs/_legacy/[AgingOS] - Master arbeidslogg NY.docx` (legacy snapshot).
