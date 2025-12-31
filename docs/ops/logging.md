# Logging (AgingOS)

## Hurtigguide (for drift / amatører)

Dette er den praktiske delen: slik finner du logger og hva du ser etter.
Detaljert logg-format (“loggkontrakt”) står lenger ned.

### 1) Se logger (dev)
Kjør:

    make logs

Stoppe loggvisning:
- Trykk Ctrl + C (stopper bare visning, ikke systemet)

### 2) Se logger (feltprofil / pilot)
Kjør:

    make field-logs

### 3) Når noe “ikke virker”: gjør dette
A) Se etter feil (ERROR/WARN)
Dev:

    docker compose logs backend | grep -E '("level":"ERROR"|"level":"WARN"| ERROR | WARN )'

Feltprofil:

    docker compose -f docker-compose.yml -f docker-compose.field.yml logs backend | grep -E '("level":"ERROR"|"level":"WARN"| ERROR | WARN )'

B) Sjekk om scheduler kjører i det hele tatt
Dev:

    docker compose logs backend | grep -E 'scheduler_configured|scheduler_run_start|scheduler_run_end'

C) Hvis du ser en run_id, filtrer på den (samler hele “historien” for én kjøring)
Eksempel (dev):

    docker compose logs backend | grep '<RUN_ID_HER>'

Hvis du står fast:
- Kjør `make logs` / `make field-logs` og kopier ut 20–50 linjer rundt en ERROR/WARN.

---

## Mål
Scheduler og drift skal være feilsøkbar i feltpilot uten å åpne DB eller kjøre ad-hoc debug.
All logg skrives til stdout/stderr (container logs) og er maskinlesbar.

## Format
- Én logglinje per event (JSON per linje / “JSONL”).
- Alle tider i UTC (ISO 8601 med `Z`).
- Felt skal være stabile (“loggkontrakt”).

## Nivåer
- INFO: Normal drift (run start/end, rule start/result)
- WARN: Delvis feil / degradert drift (enkeltregel feiler)
- ERROR: Feil som hindrer planlagt kjøring eller som krever operatør-oppfølging

## Obligatoriske felter (alle scheduler-events)
- ts (string): UTC-tid, f.eks. 2025-12-25T12:00:00Z
- level (string): INFO | WARN | ERROR
- component (string): "scheduler"
- event (string): eventnavn, se under
- run_id (string): UUID for en scheduler-run (korrelerer alle linjer)
- msg (string): kort menneskelig tekst (maks 1 linje)

## Anbefalte felter (når relevant)
- subject_key (string)
- rule_id (string)
- since / until (string, UTC ISO 8601) – evalueringsvindu
- interval_minutes (int)
- duration_ms (int)
- counts (object): summerte tall (se under)
- error (object):
  - type (string)
  - message (string)
  - stacktrace (string) – typisk ved ERROR

## Sikkerhet i logger (viktig)
Policy (må følges i kode):
- Ikke logg hemmeligheter (API-keys, tokens, passord, database-URL).
- Ikke logg store payloads rått.
- Hvis noe må logges for feilsøking: maskér/rediger verdier.

---

## Eventnavn (kontrakt)

### Scheduler-konfig (ved oppstart)
1) scheduler_configured (INFO)
   - felter: interval_minutes

### Scheduler-run (en hel kjøring)
1) scheduler_run_start (INFO)
   - felter: interval_minutes, since, until

2) scheduler_rule_start (INFO)
   - felter: rule_id, subject_key, since, until

3) scheduler_rule_result (INFO)
   - felter: rule_id, duration_ms, counts
   - counts (typisk):
     - evaluated (int)
     - deviations_upserted (int)
     - deviations_closed (int)

4) scheduler_rule_error (ERROR)
   - felter: rule_id, subject_key, duration_ms, error

5) scheduler_run_end (INFO eller ERROR)
   - ved suksess (INFO):
     - felter: duration_ms, counts
     - counts (typisk):
       - rules_total
       - rules_ok
       - rules_failed
       - deviations_upserted
       - deviations_closed
   - ved feil (ERROR):
     - felter: duration_ms, error

