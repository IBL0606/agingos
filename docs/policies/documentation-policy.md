# Dokument-policy (v1)

Status: **NORMATIVE**  
Formål: Hindre dobbelt-/trippeldokumentasjon og gi deg full kontroll over “hva som gjelder”.

## Source of truth
- **Levende teknisk dokumentasjon**: `README.md` og `docs/`
- **Legacy snapshots**: `.docx/.xlsx` (read-only)

## Én plass per tema
Hvert tema har **ett** hjemmedokument. Hvis du må skrive det samme to steder, gjør du det feil: behold én versjon og lenk.

## Status-merking (bruk i toppen av dokumenter)
- **NORMATIVE**: kontrakter, policies, sjekklister som må følges
- **GUIDANCE**: forklaringer/oppskrifter
- **TEMPLATE**: maler
- **SNAPSHOT (LEGACY)**: arkiv (ikke oppdater)

## Hvis dokumenter er uenige
Prioritet (høyest vinner):
1) Kode
2) `docs/contracts/`
3) Øvrige `docs/` (hjemmedokument)
4) `README.md`
5) Legacy snapshots
