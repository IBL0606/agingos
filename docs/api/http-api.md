# HTTP API (AgingOS)

Status: **GUIDANCE**  
Formål: Dokumentere den stabile API-overflaten (endepunkter) med lenker til kontrakter og eksempler.

## Endepunkter (per 2025-12-30)
- `GET /deviations`
- `GET /deviations/evaluate`
- `PATCH /deviations/{deviation_id}`
- `POST /event`
- `GET /events`
- `GET /health`
- `GET /rules`
- `POST /rules`
- `PATCH /rules/{rule_id}`

## Kontrakter
- Event: `docs/contracts/event-v1.md`
- Avvik: `docs/contracts/deviation-v1.md`
- Regel-config/policy: `docs/contracts/rule-config.md`

## Eksempler (curl)
### Health
```bash
curl -s http://localhost:8000/health
```

### Post event
```bash
curl -s -X POST http://localhost:8000/event \
  -H "Content-Type: application/json" \
  -d '{"id":"00000000-0000-0000-0000-000000000001","timestamp":"2025-12-30T12:00:00Z","category":"motion","payload":{"state":"on","room":"hall"}}'
```

### List events
```bash
curl -s "http://localhost:8000/events?category=motion&limit=10"
```
