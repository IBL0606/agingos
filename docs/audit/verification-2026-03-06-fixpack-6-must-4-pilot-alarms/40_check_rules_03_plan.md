# CHECK-RULES-03 execution plan (OPEN->ACK and OPEN->CLOSED)

Runtime precondition:
- Dev stack running and `/v1/deviations` contains at least two OPEN alarms.

Commands (copy/paste):
1) Capture OPEN before:
```bash
curl -sS "http://127.0.0.1:8000/v1/deviations?status=OPEN&limit=50" -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/30_deviations_open_before.json
```
2) Pick IDs A/B from file above.
3) ACK A:
```bash
curl -sS -X PATCH "http://127.0.0.1:8000/v1/deviations/<A>" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"status":"ACK"}' | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/31_deviation_A_ack.json
```
4) CLOSE B:
```bash
curl -sS -X PATCH "http://127.0.0.1:8000/v1/deviations/<B>" -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"status":"CLOSED"}' | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/32_deviation_B_closed.json
```
5) Capture after:
```bash
curl -sS "http://127.0.0.1:8000/v1/deviations?limit=50" -H "X-API-Key: $API_KEY" | tee docs/audit/verification-2026-03-06-fixpack-6-must-4-pilot-alarms/33_deviations_after.json
```

NO_EVIDENCE notes:
- Dedicated deviation status history/audit endpoint/table is NO_EVIDENCE in current repo.
- Automatic reopen as an API transition is NO_EVIDENCE in this check; only explicit PATCH transitions are tested.
