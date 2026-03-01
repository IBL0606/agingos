# AgingOS P1-2 — Rules Spec (R-001..R-010)

Denne filen er "source of truth" for regelbiblioteket i P1-2.

## Felles krav
- Deterministisk: Ingen regel bruker datetime.now() direkte. All tidslogikk baseres på (since, until, now).
- Read-only: Reglene skriver ikke til DB.
- Evidence: Skal være dict (v1) med event_ids + nøkkelparametre.
- MVP-scope: default/default/default (kan generaliseres senere via ctx/scope-parametre).

## R-001 — No activity in window (eksisterer)
- Trigger: Ingen activity events i [since, until).
- Severity: MEDIUM.

## R-002 — Front door open at night (eksisterer)
- Trigger: Front/ inngangsdør åpen i nattvindu (22:00–07:00 lokal).
- Severity: HIGH.

## R-003 — Front door open, no motion after (eksisterer)
- Trigger: Front/ inngangsdør åpner og det ikke kommer activity innen X minutter.
- Severity: HIGH (MEDIUM dag).

---

## R-004 — Prolonged bathroom presence (baderom)
**Basis-trigger**
- Segmenter presence on/off for room_id=baderom.
- Hvis sammenhengende "on" > day_threshold_min (default 45) -> avvik.

**Natt-boost**
- Nattvindu: 22:00–07:00 lokal.
- Hvis badopphold i natt og varighet > night_threshold_min (default 25) -> severity opp.

**Stillhet etterpå (severity opp)**
- Hvis badopphold har "off" og det ikke kommer activity i resten av boligen i silence_after_min (default 30) -> severity opp ett nivå.

**Stuck-beskyttelse**
- Hvis sammenhengende "on" > sensor_stuck_min (default 240) -> behandles som sensorfeil:
  - severity LOW
  - evidence.sensor_fault=true
  - ikke eskaler som "fall".

---

## R-005 — No bathroom activity in 24h (trend)
- Trigger: Ingen presence "on" i baderom i lookback_hours (default 24).
- Liveness-gate: Hvis R-009 (ingest stopped) trigges -> returner [] (ingen alarm).
- Baseline-adaptiv terskel: planlagt etter MVP.

---

## R-006 — No livingroom daytime activity (trend)
- Trigger: I dagvindu (08:00–20:00 lokal), 0 presence "on" i stue.
- "Mulig ute"-logikk (MVP):
  - Hvis inngangsdør åpner i dagvindu og det finnes activity i andre rom -> ikke trigge.
- Baseline: planlagt etter MVP.

---

## R-007 — Night wandering (romskifter)
- Trigger: I nattvindu, tell romskifter i stedet for raw event count.
- Def: Romskifte = activity i rom A etterfulgt av activity i rom B (B != A) innen switch_gap_max_min (default 10).
- Threshold: room_switches >= 6 (default).
- Dør-boost: Hvis inngangsdør involvert i natt -> severity HIGH.

---

## R-008 — Door burst (inngang)
- Trigger: door events i room_id=inngang, >= burst_count innen burst_minutes (default 3 innen 10 min).
- Natt-boost: hvis i nattvindu -> severity opp.
- Stillhet etterpå: hvis door-burst og ingen activity etterpå i silence_after_min (default 20) -> severity opp.

---

## R-009 — Ingest stopped (system)
- Trigger: Siste event i scope er eldre enn max_age_minutes (default 15).
- Severity: HIGH.
- Brukes som liveness-gate for R-005/R-010.

---

## R-010 — Sensor stuck / room stuck
- Trigger: presence "on" uten "off" i > stuck_minutes (default 240).
- Severity per room:
  - baderom/inngang: MEDIUM
  - stue/soverom: LOW
- Liveness-gate: hvis R-009 trigges -> returner [].

