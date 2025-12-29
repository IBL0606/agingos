# Ordliste (Glossary)

Status: **GUIDANCE**  
Formål: Felles definisjoner av begreper brukt i AgingOS (docs + kode). Hold forklaringene korte og praktiske.

---

## API / data

### Endpoint
En fast adresse i API-et der du kan sende data til eller hente data fra (f.eks. `POST /event`).

### JSON
Et tekstformat for data som brukes i API-kall (nøkler og verdier). Eksempel:
{ "category": "motion", "payload": { "state": "on" } }

### ISO 8601 (timestamp)
Standard måte å skrive dato og tid på, f.eks.:
2025-12-29T21:44:34Z  
I AgingOS brukes UTC (slutter ofte med Z).

### UUID
En unik ID i standardformat, f.eks.:
550e8400-e29b-41d4-a716-446655440000

---

## Event / kontrakter

### Event (Event v1)
En enkelt hendelse som sendes inn i AgingOS (f.eks. bevegelse eller dør åpnet).  
Se: `docs/contracts/event-v1.md`

### Category
Overordnet type for eventet (hvilken “klasse” hendelsen tilhører).  
Eksempler implementert i kode v1:
- `motion`
- `door`

Planlagt for pilot (når implementert i kode):
- `presence`
- `environment`
- `assist_button`

### Payload
Detaljene i eventet. Innholdet avhenger av `category`. Eksempel:
{ "state": "on", "room": "gang" }

### State
Normalisert tilstand brukt i regler.
- `motion`: "on" / "off"
- `door`: "open" / "closed"

### Room
Kontrollert romlabel (f.eks. `gang`, `stue_kjokken`). Anbefales sendt i `payload.room`.

### Entity ID
Identifikator fra Home Assistant (f.eks. `binary_sensor.front_door_contact`). Anbefales sendt i `payload.entity_id`.

### Source
Hvor eventet kom fra (f.eks. `homeassistant`). Anbefales sendt i `payload.source`.

---

## Regelmotor / avvik

### Rule engine
Komponenten som evaluerer regler mot events og produserer avvik.

### Deviation (avvik)
Et oppdaget avvik fra forventet mønster (fra regelmotoren) og kan persisteres i DB.  
Se: `docs/contracts/deviation-v1.md`

### Scheduler
Bakgrunnsjobb som kjører periodisk evaluering/vedlikehold (f.eks. regel-evaluering).

---

## Dokumentstyring

### NORMATIVE
Må følges. Brukes for kontrakter, policies og sjekklister.

### GUIDANCE
Forklaring/oppskrift. Hjelper deg å bruke systemet, men er ikke en format-kontrakt.

### SNAPSHOT (LEGACY)
Historisk dokument. Skal ikke oppdateres som sannhet. Se `docs/_legacy/README.md`.
