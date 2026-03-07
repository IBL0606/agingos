# SoT claims verification checklist v1

Assumptions for commands below (pilotbox style):
- Repo path: `/opt/agingos`
- Stack is running: `cd /opt/agingos && docker compose ps`
- If auth is enabled, set: `export AGINGOS_API_KEY='<key>'`

1. **Claim ID: SOT-001**  
   **Claim:** The base stack starts with `docker compose up -d --build` after copying `.env.example` to `.env`.  
   **Where stated:** `README.md` → `Run (Docker)` / `Base stack`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   test -f .env.example && echo OK_ENV_EXAMPLE
   docker compose config >/dev/null && echo OK_COMPOSE_CONFIG
   ```

2. **Claim ID: SOT-002**  
   **Claim:** Dev startup via `make up` runs Alembic migrations automatically after DB readiness.  
   **Where stated:** `README.md` → `Migrering / DB schema (robust standard)`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   docker compose logs --tail=400 backend | grep -E 'alembic|upgrade head'
   docker compose exec -T backend alembic -c alembic.ini current
   ```

3. **Claim ID: SOT-003**  
   **Claim:** Field profile uses compose override `docker-compose.field.yml` and starts with `make field-up`.  
   **Where stated:** `README.md` → `Felt (pilot/HW, robust profil)`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   docker compose -f docker-compose.yml -f docker-compose.field.yml config >/dev/null && echo OK_FIELD_CONFIG
   ```

4. **Claim ID: SOT-004**  
   **Claim:** In field mode, API-key auth is enabled by setting `AGINGOS_AUTH_MODE=api_key` and key env var.  
   **Where stated:** `README.md` → `Felt (pilot/HW, robust profil)`; `docs/ops/security-minimum.md` → `Konfigurasjon`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   grep -E '^AGINGOS_AUTH_MODE=|^AGINGOS_API_KEYS=|^AGINGOS_API_KEY=' .env
   ```

5. **Claim ID: SOT-005**  
   **Claim:** Runtime logs are emitted to container stdout/stderr and viewed through `docker compose logs`.  
   **Where stated:** `README.md` → `Logs (hvor finner jeg logs)`; `docs/ops/logging.md` → `Mål`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   docker compose logs --tail=50 backend
   ```

6. **Claim ID: SOT-006**  
   **Claim:** Default retention policy is 30 days for `events`.  
   **Where stated:** `README.md` → `Retention`; `docs/policies/retention.md` → `Policy (minstekrav) / Events`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   sed -n '/Retention/,/Logs/p' README.md
   sed -n '/### Events/,/### Deviations/p' docs/policies/retention.md
   ```

7. **Claim ID: SOT-007**  
   **Claim:** Default retention policy is 180 days for `deviations`, and active OPEN/ACK deviations should be retained.  
   **Where stated:** `README.md` → `Retention`; `docs/policies/retention.md` → `Policy (minstekrav) / Deviations`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   sed -n '/deviations/,/Status/p' README.md
   sed -n '/### Deviations/,/### Backups/p' docs/policies/retention.md
   ```

8. **Claim ID: SOT-008**  
   **Claim:** This repo version has no built-in automatic retention job.  
   **Where stated:** `README.md` → `Retention`; `docs/policies/retention.md` → `Hva er ikke implementert`  
   **How to verify:**  
   ```bash
   cd /opt/agingos
   rg -n 'retention job|retention' README.md docs/policies/retention.md backend/services
   ```

9. **Claim ID: SOT-009**  
   **Claim:** `/health` returns health status over HTTP GET.  
   **Where stated:** `README.md` → `Helse`; `docs/api/http-api.md` → `Health`  
   **How to verify:**  
   ```bash
   curl -sS http://localhost:8000/health
   ```

10. **Claim ID: SOT-010**  
    **Claim:** HTTP API includes endpoints `/deviations`, `/deviations/evaluate`, `/event`, `/events`, `/health`, and `/rules` CRUD subset shown in docs.  
    **Where stated:** `docs/api/http-api.md` → `Endepunkter`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    sed -n '/## Endepunkter/,/## Kontrakter/p' docs/api/http-api.md
    curl -sS http://localhost:8000/openapi.json | jq -r '.paths | keys[]'
    ```

11. **Claim ID: SOT-011**  
    **Claim:** Event timestamps in API input must be UTC timezone-aware ISO 8601 (`Z` or `+00:00`).  
    **Where stated:** `docs/contracts/event-v1.md` → `timestamp / Requirements`; `docs/policies/time-and-timezone.md` → `Policy`  
    **How to verify:**  
    ```bash
    curl -sS -o /tmp/ok.out -w '%{http_code}\n' -X POST http://localhost:8000/event \
      -H 'Content-Type: application/json' \
      -H "X-API-Key: ${AGINGOS_API_KEY}" \
      -d '{"id":"11111111-1111-1111-1111-111111111111","timestamp":"2025-12-22T10:00:00Z","category":"motion","payload":{}}'
    ```

12. **Claim ID: SOT-012**  
    **Claim:** Naive timestamps (without timezone) are rejected by API input validation.  
    **Where stated:** `docs/contracts/event-v1.md` → `Rejected`; `docs/policies/time-and-timezone.md` → `Input requirements`  
    **How to verify:**  
    ```bash
    curl -sS -o /tmp/bad.out -w '%{http_code}\n' -X POST http://localhost:8000/event \
      -H 'Content-Type: application/json' \
      -H "X-API-Key: ${AGINGOS_API_KEY}" \
      -d '{"id":"22222222-2222-2222-2222-222222222222","timestamp":"2025-12-22T10:00:00","category":"motion","payload":{}}'
    cat /tmp/bad.out
    ```

13. **Claim ID: SOT-013**  
    **Claim:** Rule/window contract is `[since, until)` (since inclusive, until exclusive).  
    **Where stated:** `README.md` → `Vinduskontrakt`; `docs/contracts/rule-config.md` → `Vinduskontrakt`; `docs/policies/time-and-timezone.md`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    sed -n '/Vinduskontrakt/,/Helse/p' README.md
    sed -n '/## Vinduskontrakt/,/## Felter/p' docs/contracts/rule-config.md
    ```

14. **Claim ID: SOT-014**  
    **Claim:** Persisted deviations have statuses OPEN/ACK/CLOSED and ACK is considered active.  
    **Where stated:** `README.md` → `Avvik-livssyklus`; `docs/contracts/deviation-v1.md` → `Aktive statuser`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    docker compose exec -T db psql -U agingos -d agingos -c "SELECT DISTINCT status FROM deviations ORDER BY status;"
    ```

15. **Claim ID: SOT-015**  
    **Claim:** There must be at most one active deviation row per `(rule_id, subject_key)` at a time.  
    **Where stated:** `docs/contracts/deviation-v1.md` → `Deviation key-policy (aktivt avvik)`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    docker compose exec -T db psql -U agingos -d agingos -c "SELECT rule_id, subject_key, COUNT(*) AS active_rows FROM deviations WHERE status IN ('OPEN','ACK') GROUP BY rule_id, subject_key HAVING COUNT(*) > 1;"
    ```

16. **Claim ID: SOT-016**  
    **Claim:** If a CLOSED deviation triggers again, a new OPEN episode is created (reopen policy).  
    **Where stated:** `README.md` → `Avvik-livssyklus`; `docs/contracts/deviation-v1.md` → `Reopen-policy`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    make statusflow
    ```

17. **Claim ID: SOT-017**  
    **Claim:** `GET /deviations` is sorted by severity descending, then `last_seen_at` descending.  
    **Where stated:** `docs/contracts/deviation-v1.md` → `API: sortering for GET /deviations`  
    **How to verify:**  
    ```bash
    curl -sS -H "X-API-Key: ${AGINGOS_API_KEY}" "http://localhost:8000/deviations" | jq -r '.[] | [.severity,.last_seen_at] | @tsv'
    ```

18. **Claim ID: SOT-018**  
    **Claim:** Scheduler interval is configured via `scheduler.interval_minutes` in `backend/config/rules.yaml`.  
    **Where stated:** `docs/ops/scheduler.md` → `Hva scheduler gjør`; `docs/contracts/rule-config.md` → `Scheduler (globalt)`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    yq '.scheduler.interval_minutes' backend/config/rules.yaml
    ```

19. **Claim ID: SOT-019**  
    **Claim:** Rule participation in scheduler flow is controlled by `rules.<RULE_ID>.enabled_in_scheduler`.  
    **Where stated:** `docs/ops/scheduler.md` → `Policy: hvilke regler kjøres`; `docs/contracts/rule-config.md` → `Semantikk: enabled_in_scheduler`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    yq '.rules | to_entries[] | {rule: .key, enabled_in_scheduler: .value.enabled_in_scheduler}' backend/config/rules.yaml
    ```

20. **Claim ID: SOT-020**  
    **Claim:** Baseline policy sets R-001 disabled in scheduler while R-002 and R-003 are enabled.  
    **Where stated:** `docs/contracts/rule-config.md` → `Scheduler-policy (baseline)`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    yq '.rules."R-001".enabled_in_scheduler, .rules."R-002".enabled_in_scheduler, .rules."R-003".enabled_in_scheduler' backend/config/rules.yaml
    ```

21. **Claim ID: SOT-021**  
    **Claim:** Scheduler/persist default subject key is `default`.  
    **Where stated:** `docs/contracts/deviation-v1.md` → `subject_key-policy`; `docs/contracts/rule-config.md` → `scheduler.default_subject_key`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    yq '.scheduler.default_subject_key' backend/config/rules.yaml
    ```

22. **Claim ID: SOT-022**  
    **Claim:** Rule engine is the single authoritative evaluation path used by both API evaluate flow and scheduler flow.  
    **Where stated:** `docs/architecture/rule-engine.md` → `Formål` and `Hovedprinsipper`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    rg -n 'evaluate_rules|rule_engine' backend/routes backend/services/scheduler.py backend/services/rule_engine.py
    ```

23. **Claim ID: SOT-023**  
    **Claim:** R-001 semantics are “trigger when no motion event exists in the evaluation window.”  
    **Where stated:** `README.md` → `R-001`; `docs/rules/rule-catalog.md` → `R-001`  
    **How to verify:**  
    ```bash
    curl -sS "http://localhost:8000/deviations/evaluate?since=2025-12-23T10:00:00Z&until=2025-12-23T11:00:00Z" -H "X-API-Key: ${AGINGOS_API_KEY}" | jq '.[] | select(.rule_id=="R-001")'
    ```

24. **Claim ID: SOT-024**  
    **Claim:** R-002 semantics are “door open in night window (23:00–06:00) triggers deviation.”  
    **Where stated:** `README.md` → `R-002`; `docs/rules/rule-catalog.md` → `R-002`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    yq '.rules."R-002".params.night_window' backend/config/rules.yaml
    ```

25. **Claim ID: SOT-025**  
    **Claim:** R-003 semantics are “front door open with no motion-on in follow-up window (default 10 minutes).”  
    **Where stated:** `README.md` → `R-003`; `docs/rules/rule-catalog.md` → `R-003`; `docs/contracts/rule-config.md` → R-003 params  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    yq '.rules."R-003".params.followup_minutes' backend/config/rules.yaml
    ```

26. **Claim ID: SOT-026**  
    **Claim:** Event category register implemented in code currently includes `motion` and `door`.  
    **Where stated:** `docs/mapping/sensor-event-mapping.md` → `Kategori-register / Implementert i kode per i dag`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    rg -n 'motion|door' backend/services/rules backend/tests/rules
    ```

27. **Claim ID: SOT-027**  
    **Claim:** Presence sensors should be mapped to `motion` until dedicated `presence` category is implemented in code.  
    **Where stated:** `docs/mapping/sensor-event-mapping.md` → `Kategori-register`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    sed -n '/Kategori-register/,/Payload/p' docs/mapping/sensor-event-mapping.md
    ```

28. **Claim ID: SOT-028**  
    **Claim:** Door payload for v1 uses `door: "front"` and `state: "open|closed"` conventions.  
    **Where stated:** `docs/mapping/sensor-event-mapping.md` → `Dørkontakt ytterdør`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    sed -n '/Dørkontakt ytterdør/,/Bruk i regler/p' docs/mapping/sensor-event-mapping.md
    ```

29. **Claim ID: SOT-029**  
    **Claim:** Scenario runner contract resets DB tables before execution (`events`, `deviations_v1`, `deviations`) for deterministic runs.  
    **Where stated:** `docs/testing/scenario-format.md` → `Forutsetninger`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    rg -n 'scenario-reset|deviations_v1|deviations' docs/testing/scenario-format.md Makefile examples/scripts/scenario_runner.py
    ```

30. **Claim ID: SOT-030**  
    **Claim:** Scenario pass condition supports only `contains` and `exact`.  
    **Where stated:** `docs/testing/scenario-format.md` → `Expect objekt`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    sed -n '/pass_condition/,/ExpectedDeviation/p' docs/testing/scenario-format.md
    ```

31. **Claim ID: SOT-031**  
    **Claim:** Deterministic tests rely on `backend/util/time.py:utcnow()` as the single “now” source.  
    **Where stated:** `docs/testing/determinism.md` → `Mønster: utcnow() som én inngang`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    rg -n 'def utcnow|utcnow\(' backend/util/time.py backend/services backend/routes backend/tests
    ```

32. **Claim ID: SOT-032**  
    **Claim:** Logging contract requires JSONL with UTC timestamps and stable fields for scheduler events.  
    **Where stated:** `docs/ops/logging.md` → `Format` and `Obligatoriske felter`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    docker compose logs --tail=200 backend | grep -E 'scheduler_run_start|scheduler_run_end|scheduler_rule_'
    ```

33. **Claim ID: SOT-033**  
    **Claim:** Logs must not contain authentication headers (`Authorization`, `X-API-Key`) or secrets.  
    **Where stated:** `docs/policies/privacy-logging.md` → `Deny-list`; `docs/ops/security-minimum.md` → `Prinsipper`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    docker compose logs --tail=1000 backend | grep -E 'Authorization|X-API-Key|DATABASE_URL' || true
    ```

34. **Claim ID: SOT-034**  
    **Claim:** Backup files are written under `./backups` with `agingos_<UTC-timestamp>.sql` naming.  
    **Where stated:** `docs/ops/backup-restore.md` → `Hvor backup lagres`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    ls -1 backups | grep -E '^agingos_[0-9]{8}T[0-9]{6}Z\.sql$'
    ```

35. **Claim ID: SOT-035**  
    **Claim:** Restore operation is destructive and resets schema before importing backup.  
    **Where stated:** `docs/ops/backup-restore.md` → `Restore (happy path)`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    make restore-db 2>&1 | sed -n '1,80p'
    ```

36. **Claim ID: SOT-036**  
    **Claim:** MiniPC pilot runbook operates from `/opt/agingos` and uses docker compose commands there.  
    **Where stated:** `docs/runbook_minipc.md` → `Location` and `Start/Stop/Status`  
    **How to verify:**  
    ```bash
    test -d /opt/agingos && echo OK_REPO_PATH
    cd /opt/agingos && docker compose ps
    ```

37. **Claim ID: SOT-037**  
    **Claim:** MiniPC runbook expects nginx front-door checks on `:8080` for `/api/health`, `/api/ai/status`, and events/proposals APIs.  
    **Where stated:** `docs/runbook_minipc.md` → `Sanity curls (via nginx on :8080)`  
    **How to verify:**  
    ```bash
    curl -sS -i http://127.0.0.1:8080/api/health -H "X-API-Key: ${AGINGOS_API_KEY}"
    curl -sS http://127.0.0.1:8080/api/ai/status -H "X-API-Key: ${AGINGOS_API_KEY}"
    ```

38. **Claim ID: SOT-038**  
    **Claim:** AI bot is enabled in pilot via `.env` with `AI_BOT_ENABLED=true`.  
    **Where stated:** `docs/runbook_minipc.md` → `Config`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    grep -E '^AI_BOT_ENABLED=' .env
    ```

39. **Claim ID: SOT-039**  
    **Claim:** Pilot architecture data flow is HA on Raspberry Pi posting events over LAN to AgingOS `/event` on mini-PC.  
    **Where stated:** `docs/hw/architecture.md` → `Oversikt` / `Datakjede`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    sed -n '/Datakjede/,/Nettverk/p' docs/hw/architecture.md
    ```

40. **Claim ID: SOT-040**  
    **Claim:** Perimeter policy requires port 8000 reachable from expected LAN clients and not exposed to internet/unwanted segments.  
    **Where stated:** `docs/hw/go-no-go.md` → `M8 Perimeter/tilgang`; `docs/ops/runbook.md` → `E8`  
    **How to verify:**  
    ```bash
    # From allowed segment
    curl -sS -o /dev/null -w '%{http_code}\n' "http://<MINIPC>:8000/health"

    # From disallowed segment
    curl -m 3 -sS -o /dev/null -w '%{http_code}\n' "http://<MINIPC>:8000/health" || true
    ```

41. **Claim ID: SOT-041**  
    **Claim:** Room-name variant support is generic (display-name/mapping based) and must not be reported as real-home support for specific variants (e.g., `bod`, `loft`, `kjellerstue`) without direct evidence.  
    **Where stated:** `docs/v2/ROOM_MAPPING.md` → `MUST-6: romnavn-varianter (truthful hardening)`  
    **How to verify:**  
    ```bash
    cd /opt/agingos
    sed -n '/MUST-6: romnavn-varianter/,/CHECK-status/p' docs/v2/ROOM_MAPPING.md
    rg -n '\\bbod\\b|\\bloft\\b|kjellerstue' docs/audit/verification-2026-03-07-fixpack-8-must-6-room-hardening/20_variant_term_scan.txt
    ```
