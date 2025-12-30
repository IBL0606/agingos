# System overview (software)

Status: **GUIDANCE**  
Formål: Gi en ny person en 60-sekunders forståelse av AgingOS-backenden uten å lese legacy docx.

## Komponenter
- **HTTP API (FastAPI):** mottak av events, listing av events, regler og avvik.
- **Database (PostgreSQL):** persistens av events og (ved scheduler) avvik.
- **Rule engine:** konsolidert “én sannhet” for regel-evaluering (brukes av både API og scheduler).
- **Scheduler/persist-flow:** periodisk evaluering og persistering av avvik (policy styres av `rule-config`).

## Kilde til sannhet
- Event-format: `docs/contracts/event-v1.md`
- Avvik-format: `docs/contracts/deviation-v1.md`
- Regelparametre: `docs/contracts/rule-config.md`
- API-overflate: `docs/api/http-api.md`
- Testing/simulering: `docs/testing/` + `docs/ops/longrun-sim.md`

## Pilot-kontekst
Pilot #1 sin fysiske arkitektur er dokumentert i `docs/hw/architecture.md` (HA sensorhub → AgingOS/DB).
