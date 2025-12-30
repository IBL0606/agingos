# MVP (Minimum Viable Product)

Status: **GUIDANCE**  
Formål: Fast, versjonert definisjon av hva “MVP” betyr i AgingOS – slik at scope ikke lever i docx eller muntlig.

## MVP-mål
Levere en løsning som gir pårørende bedre oversikt gjennom:
- datainnsamling (sensorer → Event v1)
- enkle regler for “avvik i rutine”
- varsling/oppfølging (Avvik v1)

## MVP – funksjonelt scope
- **Datainnsamling i hjemmet**
  - bevegelse, dør, evt. assist-knapp og enkle miljødata
  - normalisert inn i Event v1 (se `docs/contracts/event-v1.md` og `docs/mapping/`)
- **Rutine-/adferdsavvik (thin-slice)**
  - regler med forklarbarhet (se `docs/rules/rule-catalog.md`)
- **Varsling / oppfølging**
  - i MVP holder det med én kanal (SMS/push/e-post), eller manuell oppfølging via API/DB

## MVP skal ikke være
- helsejournalsystem
- generisk plattform for alle kommuner
- “full integrasjon” mot alle tredjepartstjenester

## Kilder
Basert på `docs/_legacy/MVP.docx` (legacy snapshot).