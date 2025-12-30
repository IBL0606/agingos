# Nattvindu-test (eksempel)

Dette er et konkret, reproduserbart eksempel på at nattlogikk fungerer som forventet for R-002.

## R-002: Frontdør åpnes i nattvindu → avvik

Kjør:
    ./examples/scripts/scenario_runner.py docs/testing/scenarios/sc_r002_door_open_at_night.yaml

Input (fra scenariofilen, forkortet):
- Event: `category="door"`
- Payload: `door="front"`, `state="open"`
- Timestamp: innen nattvindu (se scenariofilen for eksakt tidspunkt)

Evaluering:
- Scenario-runner kaller `GET /deviations/evaluate?since=...&until=...` med samme vindu som definert i scenariofilen.

Forventet output:
- Responsen inneholder minst ett deviation-objekt med `rule_id="R-002"`.
- Responsen inneholder ikke `R-001` i samme vindu (scenarioet inkluderer motion i vinduet for å unngå at R-001 trigges der).
