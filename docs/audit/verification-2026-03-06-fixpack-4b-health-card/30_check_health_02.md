# CHECK-HEALTH-02 — PASS

Dato: 2026-03-06
Miljø: dev-laptop
URL: http://127.0.0.1:8080/index.html
API key brukt: dev-key-2

Live UI-observasjon:
- Helsesjekk: RØD
- Forklaring: noe viktig virker ikke, årsak ingest lag >= 7200s
- Next steps viste konkret tiltak for datainnhenting og worker/container-logger
- Breakdown:
  - Ingest = ERROR
  - Baseline = OK
  - Anomali-worker = DEGRADED

Sammenholdt mot:
- 10_health_detail_raw.json
- 11_health_detail_focus.json

Truth note:
- `/health/detail` viste worker/anomalies_runner status = OK
- UI viste Anomali-worker = DEGRADED fordi UI også vurderer manglende `last_ok_at`
- Overall-status og ingest/baseline var i samsvar med `/health/detail`
