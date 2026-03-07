# Fixpack-7 MUST-5 explainable alarm UI — evidence manifest (dev)

Status: VERIFIED (dev-only)

## BEVIST in repo (code evidence)
- `services/console/anomalies.html` renders three explainability sections for selected anomaly episode:
  - `Hva skjedde`
  - `Hvorfor uvanlig`
  - `Datagrunnlag`
- Missing room handling is explicit as `rominfo mangler` and does not infer room context.
- Explainability text is derived from anomaly score payload fields (`score`, `reasons`, `details.observed`) only.
- Event support deep-link points to `events.html` with bounded bucket window and room filter when available.
- Minimal backend compatibility fixes were added in:
  - `backend/services/anomaly_scoring.py`
  - `backend/services/scheduler.py`

## BEVIST in dev runtime
- `POST /v1/anomalies/run_latest` returns 200 OK on current dev schema.
- `GET /v1/anomalies/score?room=stue&bucket_start=2026-03-05T11:00:00Z` returns 200 OK with explainability payload.
- Dev-only inserted `door` events produced persisted `YELLOW` anomaly episode via deterministic anomalies job.
- `GET /v1/anomalies?last=14d&limit=20` returns persisted anomaly episode rows.
- Runtime missing-room case was exercised by inserting dev-only anomaly episode row with empty `room`.

## NO_EVIDENCE
- Browser screenshot/UI capture from Console with selected episode visible.
