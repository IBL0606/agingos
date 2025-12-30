# Legacy snapshots (read-only)

Status: **SNAPSHOT (LEGACY)**  
Regel: Disse dokumentene er historikk. Gjeldende sannhet ligger i `README.md` og `docs/`. Se `docs/INDEX.md` for riktig oppdateringssted.

| Legacy fil | Innhold | Erstattes av (living) | Handling |
|---|---|---|---|
| [AgingOS-Teknisk-Arkitektur.docx](AgingOS-Teknisk-Arkitektur.docx) | Arkitektur + eldre beskrivelser av event/kontrakter | `docs/hw/architecture.md` + `docs/architecture/` + `docs/contracts/` | Snapshot; ikke rediger |
| [AgingOS - Logikkspesifikasjon.docx](AgingOS%20-%20Logikkspesifikasjon.docx) | Regler/avvik-logikk + felter/eksempler | `docs/architecture/rule-engine.md` + `docs/contracts/deviation-v1.md` | Snapshot; ekstraher kun det som eksplisitt skal gjelde videre |
| [[AgingOS] - Master arbeidslogg NY.docx](%5BAgingOS%5D%20-%20Master%20arbeidslogg%20NY.docx) | Status/beslutninger + “låste” kontrakt-notater | `docs/project/master-log.md` + lenker til kontrakter | Snapshot; levende logg føres i repo |
| [Gloser og forklaring.docx](Gloser%20og%20forklaring.docx) | Ordliste/definisjoner | `docs/project/glossary.md` | Snapshot; levende ordliste føres i repo |
| [MVP.docx](MVP.docx) | Scope og avgrensninger | `docs/project/mvp.md` | Snapshot; ev. kort oppsummering i repo |
| [AgingOS-Sprint-backlog.docx](AgingOS-Sprint-backlog.docx) | Backlog-notat (viser til Trello) | `docs/project/working-method.md` + `docs/project/master-log.md` | Snapshot |
| [AgingOS-Forretningsplan.docx](AgingOS-Forretningsplan.docx) | Forretningsplan | `docs/project/vision.md` (rammer) | Snapshot |
| [AgingOS-Kjopsliste.docx](AgingOS-Kjopsliste.docx) | Innkjøpstekst (peker til regneark) | `docs/hw/pilot-bom.md` | Snapshot |
| [Kjopsliste-Utstyr-og-budsjett.xlsx](Kjopsliste-Utstyr-og-budsjett.xlsx) | Pris/status (historikk) | `docs/hw/pilot-bom.md` | Snapshot; ikke rediger |

## Legacy-banner (standard)

> LEGACY SNAPSHOT (READ-ONLY)  
> Dette dokumentet er et historisk snapshot og skal ikke oppdateres som “sannhet”.  
> Gjeldende (living) dokumentasjon finnes i repo: `README.md` og `docs/`.  
> For riktig oppdateringssted, se `docs/INDEX.md`.  
> Sist frosset: 2025-12-29.

Merk: Banneret er lagt inn på alle `.docx` i denne mappen, og `.xlsx` har egen `INFO`-fane.

## Note
Nøkkelinnhold fra legacy docx er portet til repo (se `docs/project/` + `docs/api/` + `docs/rules/`). Legacy-filene er kun arkiv.
