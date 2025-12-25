# Logging (AgingOS)

## Mål
Scheduler og drift skal være feilsøkbar i feltpilot uten å åpne DB eller kjøre ad-hoc debug.
All logg skrives til stdout/stderr (container logs) og er maskinlesbar.

## Format
- Én logglinje per event (JSON per linje / “JSONL”).
- Alle tider i UTC (ISO 8601 med `Z`).
- Felt skal være stabile (“loggkontrakt”).

## Nivåer
- **INFO**: Normal drift (run start/end, rule start/result)
- **WARN**: Delvis feil / degradert drift (enkeltregel feiler, DB-latency over terskel)
- **ERROR**: Feil som hindrer planlagt kjøring eller som krever operatør-oppfølging

## Obligatoriske felter (alle events)
- `ts` (string): UTC-tid, f.eks. `2025-12-25T12:00:00Z`
- `level` (string): `INFO|WARN|ERROR`
- `component` (string): f.eks. `scheduler`
- `event` (string): eventnavn, se under
- `run_id` (string): UUID for en scheduler-run (korrelerer alle linjer)
- `msg` (string): kort menneskelig tekst (maks 1 linje)

## Anbefalte felter (når relevant)
- `subject_key` (string)
- `rule_id` (string)
- `since` / `until` (string, UTC ISO 8601) – evalueringsvindu
- `duration_ms` (int)
- `counts` (object): summerte tall for run/regler (se under)
- `error` (object):
  - `type` (string)
  - `message` (string)
  - `stacktrace` (string) – kun ved ERROR/WARN der det hjelper feilsøking

## Eventnavn (kontrakt)

### Scheduler-run
1. `scheduler_run_start` (INFO)
   - felter: `interval_minutes`, `since`, `until`
2. `scheduler_rule_start` (INFO)
   - felter: `rule_id`, `since`, `until`, `subject_key`
3. `scheduler_rule_result` (INFO)
   - felter: `rule_id`, `duration_ms`, `counts`
   - `c
