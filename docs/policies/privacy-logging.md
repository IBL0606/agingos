# Privacy & log hygiene (AgingOS)

## Formål
Sikre at logger er nyttige for drift/feilsøking i feltpilot, uten at logger inneholder personopplysninger, hemmeligheter eller rå payload.

Denne policyen gjelder for alle komponenter (API, scheduler, rule engine, DB-feil), og bygger på at logg er strukturert (JSON per linje / JSONL) iht. `docs/ops/logging.md`.

## Grunnprinsipper

1. **Data-minimering**
   - Logg metadata og summeringer, ikke innhold.
   - Unngå å logge hele objekter/strukturer; logg nøkkel-felter.

2. **Ingen hemmeligheter i logg**
   - Aldri logg API keys, tokens, passord, secrets, connection strings (inkludert `DATABASE_URL`).

3. **Personvern**
   - Aldri logg rå request body, event payload eller annen fritekst som kan inneholde personopplysninger.
   - Payload kan lagres i DB der det er nødvendig, men skal ikke “dumpes” i logger.

4. **Stabil loggkontrakt**
   - Felt og eventnavn skal være stabile og maskinlesbare.
   - Følg felter og nivåer definert i `docs/ops/logging.md`.

## Allow-list (eksempler på lov å logge)

### Felles (alle komponenter)
- `ts`, `level`, `component`, `event`, `run_id`, `msg`
- `duration_ms`, `counts` (summeringer), `rule_id`, `subject_key`
- `since` / `until` (UTC ISO 8601)

### Scheduler / evaluering
- Start/stop for run, start/result per regel
- Antall events behandlet (count), antall deviations opprettet/lukket, antall feil per run (counts)

### Feil
- `error.type`, `error.message` (kort), `error.stacktrace` når det er nødvendig for feilsøking
- Stacktrace må ikke inneholde rå payload eller hemmeligheter

## Deny-list (ikke lov å logge)

- Rå request body (`request.json()`, `request.body()`, “dump av payload”)
- `db_event.payload` eller event payload generelt (hele strukturen eller store deler av den)
- Headers som inneholder autentisering:
  - `Authorization`
  - `X-API-Key`
- Secrets og credentials:
  - tokens, passord, `DATABASE_URL` / connection strings
- Fritekst eller felt som kan inneholde personopplysninger (navn, e-post, telefon, adresse, fritekstnotat)

## Debug-toggle (kun lokal dev)

For lokal feilsøking kan man aktivere mer detaljert logging. Dette skal aldri brukes i produksjon eller feltpilot.

Forslag til env var:
- `AGINGOS_DEBUG_LOG_PAYLOADS=false|true` (default: `false`)

Krav når `AGINGOS_DEBUG_LOG_PAYLOADS=true`:
- Autentiseringsheaders og secrets skal fortsatt aldri logges.
- Eventuell payload-logging må være **sanitized/redacted**:
  - maskering av sensitive keys
  - truncation på store verdier
  - begrenset dybde (maks nivåer)

## Implementasjonskrav (kort)

- Alle logg-events skal være basert på eksplisitt allow-list av felter.
- Ingen logger skal inkludere rå payload eller sensitive headers.
- Ved behov for payload i dev: logg kun sanitized/redacted via debug-toggle.
