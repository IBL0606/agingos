# Scenario catalog

Denne filen katalogiserer scenarioer som brukes av scenario runneren.

- Scenariofiler ligger i: `docs/testing/scenarios/`
- Scenario-format (kontrakt): `docs/testing/scenario-format.md`

## Smoke / plumbing

### sc_smoke_no_devs_with_motion
- Fil: `docs/testing/scenarios/sc_empty_no_devs.yaml`
- Beviser:
  - Scenario runner fungerer end-to-end (reset → post events → evaluate → assert).
  - Minst én `motion` i vinduet gir ingen avvik (R-001 skal ikke trigge).
- Edge cases:
  - Verifiserer at tomt vindu ellers ville trigget R-001 (implicit via tidligere observasjon).

## Regel-scenarioer (pakke 1)

(T-0503) Her kommer scenarioer som dekker R-001, R-002, R-003 “on-demand” med tydelig hensikt og forventet avvik.

- R-001: no-motion i vindu → forvent R-001
- R-002: front door open at night → forvent R-002
- R-003: door open + ingen motion etter N minutter → forvent R-003

### sc_r001_no_motion
- Fil: `docs/testing/scenarios/sc_r001_no_motion.yaml`
- Beviser:
  - R-001 trigges når evalueringsvinduet ikke inneholder motion-events (inkl. tomt vindu).
- Forventning:
  - Avvik med `rule_id=R-001`, `severity=MEDIUM`, og tom `evidence`.
- Edge cases:
  - Dette scenarioet er bevisst “tomt” for å verifisere baseline-adferd.

### sc_r002_door_open_at_night
- Fil: `docs/testing/scenarios/sc_r002_door_open_at_night.yaml`
- Beviser:
  - R-002 trigges når en `door`-event med `payload.state=open` skjer innen nattvinduet.
- Forventning:
  - Avvik med `rule_id=R-002`, `severity=HIGH`.
- Edge cases:
  - Evidence for R-002 er “best effort” i implementasjonen og kan være tom; scenario matcher derfor ikke `evidence`.
  - Inkluderer en `motion`-event for å unngå at R-001 trigges i samme vindu.

### sc_r003_front_door_open_no_motion_after
- Fil: `docs/testing/scenarios/sc_r003_front_door_open_no_motion_after.yaml`
- Beviser:
  - R-003 trigges når `door` med `state=open` og `name/door=front` skjer, og det ikke finnes `motion` med `state=on` i follow-up vinduet (default 10 min, evt. fra config).
- Forventning:
  - Avvik med `rule_id=R-003`, `severity=MEDIUM`.
- Edge cases:
  - Evidence for R-003 er “best effort” i implementasjonen og kan være tom; scenario matcher derfor ikke `evidence`.
  - Follow-up vinduets lengde styres av `rules.R-003.params.followup_minutes`.

## Anti-regression / støy og overlapp (pakke 2)

Formålet med disse scenarioene er å forhindre regresjoner som gir falske triggere ved støy, overlappende events og “nesten”-tilfeller.

### sc_r003_no_trigger_with_motion_followup
- Fil: `docs/testing/scenarios/sc_r003_no_trigger_with_motion_followup.yaml`
- Anti-regression:
  - Verifiserer at R-003 ikke trigges når det finnes `motion` med `state=on` innen follow-up vinduet etter `front` dør åpnes.
- Beviser:
  - “Ingen falsk trigger” for R-003 ved overlapp/støy.
- Forventning:
  - Ingen avvik (`pass_condition=exact`, `deviations=[]`).

### sc_r002_no_trigger_daytime
- Fil: `docs/testing/scenarios/sc_r002_no_trigger_daytime.yaml`
- Anti-regression:
  - Verifiserer at R-002 ikke trigges når `door` med `state=open` skjer utenfor nattvinduet.
- Forventning:
  - Ingen avvik (`pass_condition=exact`, `deviations=[]`).
