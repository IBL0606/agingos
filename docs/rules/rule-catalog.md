# Rule catalog (AgingOS)

Status: **GUIDANCE**  
Formål: Én katalog for regel-ID-er, semantikk og implementasjonsstatus. Dette hindrer at planlagte regler lever i docx.

Se også:
- Runtime-parametre per regel: `docs/contracts/rule-config.md`
- Avvik-kontrakt: `docs/contracts/deviation-v1.md`
- Scenarioer som verifiserer reglene: `docs/testing/scenario-catalog.md`

## R-001 — Ingen bevegelse i våkentidsvindu
- Input: `category="motion"` med `payload.state="on"`
- Semantikk: trigger hvis 0 motion-events i definert våkentidsvindu.
- Status: **Implementert**, men **bevisst deaktivert i scheduler** i baseline (for å unngå støy).

## R-002 — Ytterdør åpnet på natt
- Input: `category="door"` med `payload.state="open"` og `payload.door=<id>`
- Semantikk: trigger hvis dør åpnes i nattvindu.
- Status: **Implementert** (inkl. scenario).

## R-003 — Dør åpnet, men ingen aktivitet etterpå
- Input: `door(open)` etterfulgt av fravær av `motion(on)` i oppfølgingstid.
- Status: **Implementert** (inkl. scenario).

## R-004 — Uvanlig høy aktivitet på kort tid (motion burst)
- Input: `motion(on)`-events
- Semantikk: trigger hvis antall motion-events i et rullerende vindu overstiger terskel (terskel skal komme fra `rule-config`).
- Status: **Planlagt** (ikke i kode per {today}).

## R-005 — Langvarig åpen dør
- Input: `door(open/closed)` for en dør-id
- Semantikk: trigger hvis `open` ikke etterfølges av `closed` innen terskel.
- Status: **Planlagt** (ikke i kode per {today}).

## Kilde
Regelsemantikk er sammenfattet fra `docs/_legacy/AgingOS - Logikkspesifikasjon.docx` (legacy snapshot).
