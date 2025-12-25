# Scheduler (AgingOS) — drift og verifisering

## Formål
Scheduler kjører regel-evaluering periodisk og persisterer triggende avvik (OPEN) til databasen for regler som er aktivert for scheduler/persist-flow.

## Hva scheduler gjør
- Kjører en bakgrunnsjobb med intervall definert i `backend/config/rules.yaml`:
  - `scheduler.interval_minutes`
- Kaller rule engine for scheduler-flow (samme regel-evaluering som systemet ellers bruker)
- Persisterer resultater til DB (typisk som OPEN avvik) for regler som er `enabled_in_scheduler: true`

## Policy: hvilke regler kjøres
- Styres per regel i `backend/config/rules.yaml`:
  - `rules.<RULE_ID>.enabled_in_scheduler`
- `true`: regelen inngår i scheduler/persist-flow (kan gi persisterte avvik i DB)
- `false`: regelen kjøres ikke av scheduler (kan fortsatt evalueres manuelt via API)

Semantikken er kontraktfestet i:
- `docs/contracts/rule-config.md`

## Forventede logger
Ved normal kjøring forventes det logglinjer som indikerer at scheduler-jobben kjører, og hvor mange avvik som ble beregnet/persistert.

Typiske signaler å se etter:
- “scheduler started” / “job executed”
- “computed N deviations” (der N kan være 0)

Hvis du ikke ser logg i terminal:
- sjekk at backend faktisk starter scheduler (startup-hook)
- sjekk log level / logger-navn

## Feilhåndtering
Scheduler-jobben skal være robust:
- DB-session skal alltid lukkes (try/finally)
- Exceptions i én kjøring skal ikke stoppe scheduler permanent (feil skal logges, neste intervall kjører videre)

Hvis du ser exceptions:
- Noter stack trace
- Sjekk om feilen kommer fra:
  - DB-tilkobling (DATABASE_URL, db-container nede)
  - JSON-serialisering (context/evidence må være JSON-serialiserbart)
  - Regelkode (payload-antagelser)

## Hvordan verifisere lokalt at scheduler går

### A) Se at jobben kjører
1. Start stack:
   - `make up` (eller `docker compose up -d --build`)
2. Se logs:
   - `make logs` (eller `docker compose logs -f backend`)
3. Bekreft at scheduler-jobben trigges med forventet intervall.

### B) Verifiser at den persisterer avvik
1. Legg inn events som skal trigge en scheduler-aktiv regel (f.eks. R-003).
2. Vent minimum ett intervall (i henhold til config).
3. Kall API for å liste persisted deviations (hvis aktuelt i prosjektet), eller les direkte fra DB.

### C) Endre intervall for rask test
Juster:
- `scheduler.interval_minutes` i `backend/config/rules.yaml`
Restart backend for at ny verdi skal tas i bruk.

## Failure modes (minimum) og forventet oppførsel

1) DB utilgjengelig
- Symptomer: connect timeout, auth-feil, “could not connect”
- Forventet oppførsel:
  - Logg `ERROR` på run-nivå (f.eks. `event=scheduler_run_end`) med `error`-detaljer
  - Run avsluttes tidlig, neste run prøver igjen ved neste intervall

2) Enkeltregel/persist-feil (error isolation)
- Symptomer: exception ved upsert/persist for én regel/ett avvik
- Forventet oppførsel:
  - Logg `ERROR` med `event=scheduler_rule_error` og `rule_id`
  - Fortsett med neste element i samme run (ikke stopp hele scheduler-run)

3) Konfigurasjonsfeil
- Symptomer: manglende/ugyldige config-verdier (f.eks. `scheduler.interval_minutes`)
- Forventet oppførsel:
  - Logg `ERROR` med tydelig hvilke felt som er ugyldige
  - Run avsluttes, og vil fortsette å feile til config er rettet

4) Tid/UTC-feil
- Symptomer: naive timestamps, parsing-feil, eller uventede tidsverdier
- Forventet oppførsel:
  - Logg `ERROR` på run-nivå med `error`-detaljer
  - Run avsluttes, neste run prøver igjen

## Operasjonelle tellere (minstekrav)
Per scheduler-run skal følgende summeres og logges:
- `rules_total`
- `rules_ok`
- `rules_failed`
- `deviations_upserted`
- `deviations_closed`

## Incident note template (feltpilot)
Bruk `docs/ops/incident-template.md` som minimumsformat.

## Konfigurasjon
- `backend/config/rules.yaml` (source of truth for intervall og rule enablement)
- `backend/config/rule_config.py` (lesing av config)

## Lenker
- Scheduler-kode: `backend/services/scheduler.py`
- Rule engine: `backend/services/rule_engine.py`
- Kontrakt: `docs/contracts/rule-config.md`
