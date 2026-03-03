# room_id derivation — evidence note (Devbox)

## What changed
- Added deterministic room_id derivation in `/event` ingest:
  - payload.room_id → payload.room → payload.area → room_map[entity_id]
- Added optional config: `backend/config/room_map.yaml` (default empty)
- Added helper: `backend/util/room_id.py`

## Evidence
- Code diff is captured in `room-id-derivation.diff.txt` (this folder).

## Limitations (truthfulness policy)
- **NO_EVIDENCE (runtime data effect)**: Devbox has no live events; DB query for last 24h returned 0 rows.
- **NO_EVIDENCE (py_compile/runtime)**: Python-based compile checks terminated the WSL session in this environment.
  Therefore we do not claim compile/runtime execution proof in this fixpack evidence.
