# Longrun-simulering (syntetisk data) – runbook

Denne runbooken beskriver hvordan man kjører en langkjøring (typisk 1–6 timer) med syntetiske events for å observere stabilitet, DB-vekst og scheduler-cadence.

Målet er driftssikkerhet: jevn flyt, forutsigbar vekst og ingen ukontrollert feillogging.

## Forutsetninger

- Backend og DB kjører lokalt (typisk via `make up`).
- Tidsstempler i events må være UTC timezone-aware (ISO 8601 med `Z`).

## Moduser

### A) Longrun med scheduler (anbefalt for driftssimulering)
- Scheduler må være aktiv (default). Ikke sett `SCHEDULER_ENABLED=0`.
- Forventer at scheduler evaluerer scheduler-enabled regler iht. `backend/config/rules.yaml`.

### B) Longrun uten scheduler (kontrollert/isolert)
- Brukes hvis man kun vil poste events og manuelt evaluere via `/deviations/evaluate`.
- Sett `SCHEDULER_ENABLED=0`.

## Kjøring

### 1) Start stack
```bash
make up
```
### 2) (Valgfritt) Reset før kjøring

Hvis du ønsker ren baseline:
```bash
make scenario-reset
```

### 3) Generer syntetiske events over tid

Velg én av disse tilnærmingene:

Bruk eksisterende event-generator dersom den finnes i repoet (anbefalt).

Alternativt: kjør en enkel “poster loop” i shell som poster events periodisk.

Eksempel (manuell posting av én event):
```bash
curl -s -X POST "http://localhost:8000/event" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "00000000-0000-0000-0000-000000000001",
    "timestamp": "2025-12-23T12:00:00Z",
    "category": "motion",
    "payload": {"state": "on"}
  }'
  ```

## Hva man forventer å se (sunn kjøring)
### API / helse
- /health svarer stabilt med 200.

### DB-vekst
- events vokser jevnt i tråd med event-rate.
- deviations_v1 og/eller deviations vokser kun dersom scheduler/persist-flow er aktivert og regler trigges.

Eksempel på enkle observasjonskommandoer:
```bash
docker compose exec db psql -U agingos -d agingos -c "select count(*) from events;"
docker compose exec db psql -U agingos -d agingos -c "select count(*) from deviations_v1;"
docker compose exec db psql -U agingos -d agingos -c "select count(*) from deviations;"
```
### Scheduler-cadence (dersom scheduler er aktiv)
- Loggene viser periodisk evaluering uten error-spam.
- Avvik opprettes/oppdateres i forventet takt i tråd med regler og lookback.

Eksempler på “sunn kjøring” (illustrativt):

- “scheduler tick … evaluate rules … ok”
- “rule_engine … evaluated … devs=N”
- “persist … upsert deviations … ok”

(Erstatt gjerne med faktiske logglinjer fra ditt miljø når de er verifisert.)

## Stoppkriterier (hvis noe går galt)

### Stopp kjøringen og feilsøk hvis ett eller flere av disse inntreffer:

1. Vedvarende ERROR/WARN-støy
- Gjentatte exceptions i scheduler eller API-ruter.
- Økende feilrate som ikke stabiliserer seg.

2. Uventet DB-vekst
- Kraftig vekst i deviations* uten tilsvarende forklaring (f.eks. samme avvik persisteres ukontrollert).
- Tegn på “hot loop”/for hyppig scheduler-tick.

3. Ressursproblemer
- Backend blir treg eller utilgjengelig.
- DB CPU/disk øker ukontrollert.

4. Tidsrelaterte avvik
- Timestamps ser ut til å bli lagret/parsset feil (ikke UTC-aware), eller evalueringsvinduer oppfører seg inkonsistent.

### Etterkjøring / nedstengning
```bash
make down
```

### Notater
Denne runbooken er ment som en driftssjekkliste. Hold den kort, praktisk og oppdatert etter hvert som dere får mer erfaring med longrun.