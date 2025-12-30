# Visjon og produktmål (AgingOS)

Status: **GUIDANCE**  
Formål: Samle “hvorfor” og overordnede avgrensninger for AgingOS i repo, slik at vi ikke trenger å lese legacy `.docx` for å forstå prosjektets hensikt.

## Problem / behov
AgingOS er ment å redusere friksjon og risiko i hverdagen for personer som trenger oppfølging i hjemmet, og gi pårørende bedre innsikt uten å gjøre løsningen til et helsejournalsystem.

## Løsning (kort)
- Lokal sensorinnsamling (via Home Assistant) normaliseres til **Event v1** og lagres i database.
- Regler evaluerer events og produserer **Avvik v1** som kan forklares og følges opp.
- Pilot #1 fokuserer på én husholdning og operasjonell robusthet (logging, backup, longrun-sim).

## MVP-prinsipper (ikke-mål)
MVP er eksplisitt **ikke**:
- et komplett helsejournalsystem
- full integrasjon mot “alt”
- en ferdig plattform for alle kommuner

MVP skal være en fungerende prototype for én husholdning med kvalitet nok til demo/pilot.

## Kilder
Dette dokumentet er en sammenfatning av `docs/_legacy/AgingOS – Forretningsplan.docx` og `docs/_legacy/MVP.docx` (legacy snapshot).
