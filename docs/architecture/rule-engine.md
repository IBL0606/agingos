# Rule engine (AgingOS) — arkitektur og utviklerflyt

## Formål
Rule engine er den eneste autoritative måten å evaluere regler på i AgingOS. Både API (manuell evaluering) og scheduler (persist-flow) skal bruke samme evaluering for å unngå duplisert logikk og avvikende oppførsel.

## Hovedprinsipper
- **Én sannhet:** Regel-evaluering skjer via `backend/services/rule_engine.py`.
- **Registry-prinsipp:** Regler er registrert i et registry slik at rule engine kan evaluere alle (eller et utvalg) uten at routes/scheduler hardkoder hvilke regler som finnes.
- **Deterministisk evaluering:** Regler evalueres deterministisk over et tidsvindu og returnerer `DeviationV1`-objekter.

## Flyt: evaluate_rules (inputs/outputs)

### Input
`evaluate_rules(db, since, until, now, ...)` tar typisk inn:
- `db`: SQLAlchemy Session (leser events fra DB)
- `since`: start på evalueringsvindu (inkludert)
- `until`: slutt på evalueringsvindu (ekskludert)
- `now`: tidspunktet avviket genereres (brukes som `timestamp` i Avvik v1)

### Output
Returnerer en liste av `DeviationV1` (Avvik v1) med feltene:
- `rule_id`
- `timestamp` (typisk `now`)
- `severity` ("LOW" / "MEDIUM" / "HIGH")
- `title`
- `explanation`
- `evidence` (liste av UUID; kan være tom)
- `window` (`since`, `until`)

### Vinduskontrakt
Rule engine og alle regler følger vinduskontrakt **[since, until)**:
- `since` er inklusiv
- `until` er eksklusiv

Dette sikrer deterministisk grensesnitt og unngår “dobbeltelling” når man evaluerer tilstøtende vinduer.

## Now-injection (determinisme)
For deterministiske tester og simulering brukes en felles “now provider” (`utcnow()`), slik at “nå” kan kontrolleres i test.
Se: `docs/testing/determinism.md`.

## Hvordan registry fungerer
Registry inneholder mapping fra `rule_id` (f.eks. "R-002") til eval-funksjon for regelen.
Rule engine bruker registry til å kalle hver regel med standardisert signatur (db, since, until, now).

Konsekvens:
- Routes og scheduler trenger ikke “vite” hvilke regler som finnes.
- Nye regler kan legges til ved å registrere dem i registry (én endring), uten å endre scheduler og routes.

## Hvordan legge til en ny regel (utvikler)
1. Lag regelmodul i `backend/services/rules/` (f.eks. `r004.py`).
2. Implementer eval-funksjon med signatur:
   - `eval_rXXX_... (session, since, until, now) -> List[DeviationV1]`
3. Les parametre fra `backend/config/rules.yaml` via `backend/config/rule_config.py` (ingen hardkodede terskler).
4. Registrer regelen i rule registry i `backend/services/rule_engine.py`.
5. Oppdater smoke test (hvis relevant) og dokumentasjon:
   - README (hvordan verifisere manuelt)
   - docs/contracts/rule-config.md (nye parametre)
   - Master arbeidslogg (status/avgjørelser)

## Lenker
- Implementasjon: `backend/services/rule_engine.py`
- Regler: `backend/services/rules/`
- Kontrakt for konfig: `docs/contracts/rule-config.md`
