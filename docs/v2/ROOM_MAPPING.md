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

MUST-6: romnavn-varianter (truthful hardening)
- Systemstøtte (generisk kode-path):
  - `payload.room`/`payload.area` matches bare `rooms.display_name` case-insensitivt.
  - Det finnes **ikke** egen synonym-/aliasnormalisering i kode for ord som `bod`, `loft`, `kjellerstue`.
  - Variantstøtte oppnås derfor per hjem ved at operator registrerer ønsket `display_name` i `rooms`, eller via `sensor_room_map` på `entity_id`.
- Reell hjemmetesting (pilot/customer):
  - Ingen dokumentert real-home evidens i repo for spesifikke varianter (`bod`/`loft`/`kjellerstue`) per 2026-03-07.
  - Påstander om disse variantene skal derfor merkes `NO_EVIDENCE` inntil pilotbox/home-capture foreligger.

CHECK-status (MUST-6 scope)
- CHECK-ROOM-01: Referanse til Fixpack-3 (allerede PROVEN; ikke re-implementert her).
- CHECK-ROOM-02: `NO_EVIDENCE` per nå (generisk kode-path støttes, men ingen real-home variantbevis).

Backend API (v1)
- GET  /v1/rooms
- POST /v1/rooms (upsert)
- GET  /v1/room_mappings
- POST /v1/room_mappings (upsert; validerer room_id finnes)
- GET  /v1/room_mappings/unknown_sensors?stream_id=<selected-stream>
- POST /v1/room_mappings/self_heal?stream_id=<selected-stream>&dry_run=true|false

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


Self-heal (Fixpack-10)
- Endpoint: `POST /v1/room_mappings/self_heal`
- Query:
  - `stream_id` (default `prod`)
  - `dry_run` (default `true`)
- Datakilde: live `events` i samme scope + stream.
- Rooms rebuild:
  - leser `payload.room` / `payload.area`
  - oppretter bare rom som mangler (bevarer norske navn fra payload)
  - overskriver ikke eksisterende rom blindt
- Mapping rebuild:
  - mapper kun entydige `entity_id -> room` observasjoner
  - konflikt (`entity_id` i flere rom) auto-mappes ikke
  - eksisterende mapping til annen room_id overskrives ikke blindt
- Idempotens:
  - gjentatt kall uten nye observasjoner skal gi `*_unchanged`/`skipped_existing`, ikke duplikater

Console Rooms-side (Fixpack-10)
- Rooms-siden bruker valgt `stream_id` fra Console-konfigurasjon (localStorage), ikke hardkodet `prod`.
- Ved tom romkatalog vises eksplisitt operatør-state i UI (ikke stille tomside).
