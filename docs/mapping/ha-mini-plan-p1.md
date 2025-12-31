# Home Assistant → AgingOS mini-plan (P1, uten HW)

**Status:** DRAFT  
**Formål:** Definere første, stabile HA→Event v1-strøm for pilot (ytterdør + presence/motion), slik at installasjon kan gjøres raskt når HW er på bordet.

## Se også
- docs/mapping/sensor-event-mapping.md (normativ mapping)
- docs/contracts/event-v1.md (Event v1 kontrakt)

---

## 1) Forventede HA entity_id-er (første)
Mål: starte med 2–3 entity_id-er for å minimere feilsøkingsflate. Hvis HA genererer andre navn, renavn entity_id i HA (eller lag tydelige alias) slik at de blir stabile og lesbare.

### Ytterdør (dørkontakt)
- binary_sensor.front_door_contact

### Første rom (presence/motion)
Velg én sensor i første bølge. Begge mappes til category = "motion" i v1.
- binary_sensor.<ROOM>_presence (presence-sensor, f.eks. FP2)
- binary_sensor.<ROOM>_motion (PIR)

### Roomlabels (kontrollerte)
- Bruk kun rom som faktisk inngår i piloten.
- Eksempler: gang, stue_kjokken, soverom

---

## 2) Hva som sendes til AgingOS (room/source/entity_id/state)
Alle events sendes som Event v1 til POST /event.

### Felles payload-felter (skal alltid være med i pilot)
- source: "homeassistant"
- room: kontrollert romlabel (f.eks. "gang")
- entity_id: HA entity_id (f.eks. "binary_sensor.front_door_contact")
- state: normalisert tilstand (se under)

### Kategori-spesifikt
- motion: state = "on" eller "off"
- door: door = "front" og state = "open" eller "closed"

### Eksempel: motion on

    {
      "id": "00000000-0000-0000-0000-000000000010",
      "timestamp": "2025-12-27T12:00:00Z",
      "category": "motion",
      "payload": {
        "state": "on",
        "room": "stue_kjokken",
        "source": "homeassistant",
        "entity_id": "binary_sensor.stue_kjokken_presence"
      }
    }

### Eksempel: ytterdør open

    {
      "id": "00000000-0000-0000-0000-000000000020",
      "timestamp": "2025-12-27T23:30:00Z",
      "category": "door",
      "payload": {
        "door": "front",
        "state": "open",
        "room": "gang",
        "source": "homeassistant",
        "entity_id": "binary_sensor.front_door_contact"
      }
    }

---

## 3) Rate-limit (transitions)
Pilot-prinsipp: send kun state-transitions.

- motion: kun off→on og on→off
- door: kun closed→open og open→closed

Støyreduksjon (i HA-automatisering / Node-RED):
- dedupe/cooldown: ikke send event hvis samme state allerede er sendt siste ca. 2 sekunder (kun hvis sensoren er chatty)
- ingen periodisk spam i P1 (heartbeat kan vurderes senere hvis dere trenger eksplisitt liveness-signal)

---

## 4) Sjekkliste når HW står på bordet
1. Legg til enheter i HA (ytterdør + én motion/presence i første rom).
2. Verifiser/renavn entity_id slik at de matcher seksjon 1.
3. Velg romlabel (payload.room) og lås den (ikke "Stue", "stue", "livingroom" om hverandre).
4. Lag HA-automatisering(er) som trigges på state change og POSTer Event v1 til AgingOS:
   - motion: category=motion, payload.state=on/off
   - door: category=door, payload.door=front, payload.state=open/closed
5. Verifiser end-to-end:
   - trigger sensor → bekreft HTTP 200 fra AgingOS
   - se at payload har room/source/entity_id/state
6. Hvis det blir støy:
   - slå på cooldown/dedupe i automatiseringen og re-test.
