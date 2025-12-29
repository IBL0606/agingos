# Ordliste (Glossary)

Status: **GUIDANCE**
Formål: Felles definisjoner av begreper brukt i AgingOS.

## Endpoint
Et endpoint er en fast adresse i et system der man kan sende data til eller hente data fra.

## ISO 8601
ISO 8601 er en internasjonal standard for hvordan dato og tid skrives som tekst, slik at både mennesker og datamaskiner forstår det likt
.
2025-12-14T19:30:00

## UUID
En UUID er en universelt unik identifikator – et langt, tilfeldig generert ID-nummer som er ekstremt lite sannsynlig å bli likt et annet.

550e8400-e29b-41d4-a716-446655440000

## Payload
Payload er selve innholdet i eventet – detaljene som forteller hva som faktisk ble målt eller rapportert.

Eksempler:
{ "state": "motion" }
{ "battery": 82 }
{ "status": "started" }

## Category
Category er en overordnet klassifisering av hva slags type hendelse dette er, uavhengig av detaljer.

sensor
Hendelser som kommer direkte fra fysiske sensorer
(f.eks. bevegelse, dør, temperatur)
system
Hendelser generert av selve systemet
(f.eks. oppstart, feil, statusendringer)
user
Hendelser utløst direkte av et menneske
(f.eks. knappetrykk, manuell handling)
derived
Hendelser som er avledet fra andre events
(f.eks. “ingen bevegelse på 4 timer”)

## Derived
Derived betyr avledet.
Et derived event er ikke noe som skjedde direkte i verden, men noe systemet har konkludert med basert på andre events.
Eksempel:
Sensor-events:
 “Bevegelse registrert kl 08:12”
 “Bevegelse registrert kl 08:30”

Derived event:
 “Ingen bevegelse mellom 09:00 og 13:00”

Viktig:
Derived events er fortsatt events

De er rå resultater, ikke alarmer eller varsler

De brukes videre av regler og avvik

I AgingOS er derived en måte å:
gjøre mønstre eksplisitte

uten å blande tolkning inn i rå sensor-data

## Event (Event v1)
En enkelt hendelse som sendes inn i AgingOS (f.eks. bevegelse eller dør åpnet). Se: `docs/contracts/event-v1.md`.

## Deviation (avvik)
Et oppdaget avvik fra forventet mønster, produsert av regelmotoren og eventuelt persistert i DB. Se: `docs/contracts/deviation-v1.md`.

## Rule engine
Komponenten som evaluerer regler mot event-strøm og produserer avvik.
