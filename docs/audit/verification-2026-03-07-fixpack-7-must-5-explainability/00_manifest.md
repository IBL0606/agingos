# Fixpack-7 MUST-5 explainable alarm UI — evidence manifest (dev)

Status: DRAFT (dev-only)

## BEVIST in repo (code evidence)
- `services/console/anomalies.html` renders three explainability sections for selected anomaly episode:
  - `Hva skjedde`
  - `Hvorfor uvanlig`
  - `Datagrunnlag`
- Missing room handling is explicit as `rominfo mangler` and does not infer room context.
- Explainability text is derived from existing anomaly score payload fields (`score`, `reasons`, `details.observed`) only.
- Event support deep-link points to `events.html` with bounded bucket window and room filter when available.

## NO_EVIDENCE (runtime)
- Full browser/runtime validation against live backend API in this environment.
- End-to-end data-backed verification that specific alarms shown in UI include supporting event rows from `/events` in running stack.

## Suggested runtime capture commands (dev stack)
1. `docker compose up -d --build`
2. `curl -sS -H 'X-API-Key: dev-key-2' 'http://localhost:8000/v1/anomalies?last=14d&limit=20' | tee docs/audit/verification-2026-03-07-fixpack-7-must-5-explainability/10_api_anomalies.json`
3. `curl -sS -H 'X-API-Key: dev-key-2' 'http://localhost:8000/v1/anomalies/score?room=<ROOM>&bucket_start=<ISO_BUCKET>' | tee docs/audit/verification-2026-03-07-fixpack-7-must-5-explainability/11_api_anomaly_score.json`
4. Browser capture: anomalies page with selected episode and all three explainability sections visible.
