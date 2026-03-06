# Fixpack-5 MUST-3 patch: events_limit clamp (exact fix)

Verified bug scope:
- Report used `thr.events_limit` directly in `/events?limit=...`.
- API limit must be <= 1000.

Patch verification:
- `loadThresholds()` now clamps effective `events_limit` to `1..1000`.
- Playwright check with `localStorage.events_limit=2000` captured request URL:
  - `http://127.0.0.1:8080/api/events?limit=1000&stream_id=prod`

Result:
- PASS for this patch: UI no longer sends `/events?limit=2000`.
