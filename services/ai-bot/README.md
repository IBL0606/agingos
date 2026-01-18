# AgingOS AI Bot (Sprint 0)

Dette er en ekstern AI-bot-tjeneste som kan kobles til AgingOS Backend, men som alltid kan slås av/på.
Sprint 0 leverer kun "skjelett": health, capabilities og tomme insights.

## Kjøre lokalt (Docker Compose)
- Tjenesten kjøres via `docker compose up -d ai-bot`.
- Standard port lokalt: http://127.0.0.1:8010

## Endepunkter (Sprint 0)
- GET /healthz
- GET /v1/capabilities
- GET /v1/insights (returnerer tomme findings/proposals)

## Integrasjon i AgingOS Backend
AgingOS eksponerer:
- GET /ai/status
- GET /ai/insights

## Konfig (repo-roten .env)
Disse må finnes og være koblet inn i backend service i docker-compose.yml:

- AI_BOT_ENABLED=true|false
- AI_BOT_BASE_URL=http://ai-bot:8010

## Smoke test
1) Bot direkte:
   - curl -s http://127.0.0.1:8010/healthz
   - curl -s http://127.0.0.1:8010/v1/capabilities

2) Via backend (krever X-API-Key):
   - curl -s -H "X-API-Key: <key>" http://127.0.0.1:8000/ai/status
   - curl -s -H "X-API-Key: <key>" "http://127.0.0.1:8000/ai/insights?since=2026-01-01T00:00:00Z&until=2026-01-02T00:00:00Z"
