# Room Mapping (Fixpack-3)

Formål
- Gi Console og regelmotor et deterministisk rom-felt (events.room_id) for presence/door.
- Løse pilot-blocker: room_id var tom for alle presence/door events (24h) på pilotbox 2026-03-03.

Datamodell (scope-aware)
1) rooms (per org_id + home_id)
- room_id (slug, f.eks. bathroom)
- display_name (f.eks. Bad)
- room_type (f.eks. BATHROOM, ENTRANCE, ...)

2) sensor_room_map (per org_id + home_id)
- entity_id (HA entity_id)
- room_id (ref til rooms)
- active (bool)
- note (valgfritt)

Ingest: deterministisk room_id-resolve (presence/door)
Rekkefølge:
1) payload-first
- payload.room_id dersom gyldig (room finnes i rooms)
- payload.room eller payload.area matcher rooms.display_name (case-insens)
2) mapping-second
- payload.entity_id lookup i sensor_room_map der active=true
3) fallback
- legacy derive (payload/yaml) brukes kun hvis ingen av over treffer

Backend API (v1)
- GET  /v1/rooms
- POST /v1/rooms (upsert)
- GET  /v1/room_mappings
- POST /v1/room_mappings (upsert; validerer room_id finnes)
- GET  /v1/room_mappings/unknown_sensors?stream_id=prod

Console: Romoppsett (operator)
URL:
- http://localhost:8080/rooms.html

Bruk:
1) Sett API base = /api
2) Skriv inn API key (maskert)
3) Oppdater
4) Opprett rom i “Romkatalog (rooms)”
5) Se “Ukjente sensorer” og map entity_id -> room_id
6) Verifiser at room_id_set_24h > 0 (dev) og at unknown_sensors går ned

Dev verifikasjon (evidence)
- docs/audit/verification-2026-03-05-fixpack-3-dev/01_roomid_after_ingest_fix.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/45_api_get_rooms.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/46_api_get_room_mappings.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/47_api_get_unknown_sensors_initial.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/52_console_rooms_html_served.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/53_console_nav_rooms_link_present.txt
- docs/audit/verification-2026-03-05-fixpack-3-dev/54_rooms_html_api_key_masked.txt

Pilotbox verifikasjon
- Template only (NO_EVIDENCE):
  docs/audit/_templates/pilotbox_capture/fixpack-3_room_mapping.md
