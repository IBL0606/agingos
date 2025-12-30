# Arbeidsform og backlog

Status: **GUIDANCE**

## Backlog = ett sted
AgingOS skal ha én living backlog (ikke i `.docx`):
- Foretrukket: GitHub Issues (eller Trello hvis det er etablert der)
- Repo-dokumentasjon (`docs/`) skal kun beskrive:
  - scope/krav (MVP, pilot)
  - kontrakter, runbooks og arkitektur
  - beslutninger og “hva er sant nå” (master-logg)

## Definition of Done (DoD) – minimum
Et arbeidspunkt er “ferdig” når:
- dokumentasjon (hjemmedokument) er oppdatert eller lenket riktig fra `docs/INDEX.md`
- smoke/statusflow/scenario runner (der relevant) verifiserer at endringen fungerer
- endringen er sporbar i master-logg (5–10 linjer med lenker)

## Risikoer (typisk for pilot)
- tid frem mot installasjon (HW-lead time)
- miljøavhengighet for test/simulering
- regress i scheduler/statusflyt uten test-gate

## Kilde
Sammenfattet fra `docs/_legacy/AgingOS – Sprint-backlog.docx` (legacy snapshot).
