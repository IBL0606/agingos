# ADR-0301: Deviation key-policy og subject_key-policy (minimalt)

## Status
Accepted (thin-slice)

## Kontekst
AgingOS persisterer avvik i DB via scheduler. Vi trenger en minimal, deterministisk policy for:
- når et avvik regnes som “samme” over tid (upsert key)
- hvordan `subject_key` settes i nåværende thin-slice

## Beslutning
1) Aktivt avvik identifiseres av `(rule_id, subject_key)` for statuser `OPEN` og `ACK`.
2) Scheduler upserter eksisterende aktiv rad (OPEN/ACK). `CLOSED` er ikke aktiv.
3) `subject_key` settes i nåværende persist-flow til `scheduler.default_subject_key` (default: "default").

## Begrunnelse (minimalt riktig nå)
- Thin-slice kjører én global scheduler/persist-flow uten multi-home eller device-separasjon.
- Dette gir en enkel og robust identitet for “samme aktive avvik”, og forhindrer duplikater.
- Policyen er konsistent med rule-config-kontrakten som omtaler OPEN/ACK som “stale-close”-kandidater.

## Konsekvenser
- DB håndhever unikhet for aktive statuser (OPEN/ACK) per `(rule_id, subject_key)`.
- Når multi-home/device introduseres, må kontrakten utvides og key-policy revurderes.

## Referanser
- Kontrakt: `docs/contracts/deviation-v1.md`
