# Stopp-kriterier (simulering og hardware)

Status: **NORMATIVE**  
Formål: Målbare kriterier som må være oppfylt før vi går videre til fysisk installasjon.

## Simulering (må være oppfylt)
- Reproduserbart døgnscenario er definert (kommando + input er dokumentert).
- Resultat av simulering er notert (observasjoner: hva fungerer / hva er støy).
- Kjøpsliste/BOM er oppdatert basert på definert test-scope (rom + sensortyper).

## Hardware (må være oppfylt)
- Event-kontrakt er skrevet, forstått og låst (`docs/contracts/event-v1.md`).
- Koden er verifisert mot kontrakt (smoke test grønn på clean checkout).
- Minst ett døgnscenario kan simuleres reproduserbart (scenario runner / longrun-sim).
- Drift-minstekrav er på plass (logger, backup/restore, scheduler failure modes).

## Lenker
- `docs/contracts/event-v1.md`
- `docs/testing/scenario-catalog.md`
- `docs/ops/longrun-sim.md`
- `docs/hw/pilot-bom.md`
