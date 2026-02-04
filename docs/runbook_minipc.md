# AgingOS MiniPC Runbook (pilot)

## Location
Repo lives at: `/opt/agingos`

## Start/Stop/Status
~~~bash
cd /opt/agingos
sudo docker compose up -d
sudo docker compose ps
sudo docker compose down --remove-orphans
~~~

## Logs
~~~bash
cd /opt/agingos
sudo docker compose logs -f --tail=200 backend
sudo docker compose logs -f --tail=200 ai-bot
sudo docker compose logs -f --tail=200 console
sudo docker compose logs -f --tail=200 db
sudo docker compose logs -f --tail=200 heartbeat
~~~

## Sanity curls (via nginx on :8080)
~~~bash
curl -sS -i http://127.0.0.1:8080/api/health -H "X-API-Key: YOUR_API_KEY"
curl -sS http://127.0.0.1:8080/api/ai/status -H "X-API-Key: YOUR_API_KEY" | jq
curl -sS "http://127.0.0.1:8080/api/events?limit=20" -H "X-API-Key: YOUR_API_KEY" | jq '.[0:5]'
curl -sS "http://127.0.0.1:8080/api/ai/proposals?until=$(date -u +%Y-%m-%dT%H:%M:%SZ)&meaningful_recent_floor=0&min_abs_increase=0&z_threshold=0"   -H "X-API-Key: YOUR_API_KEY" | jq
~~~

## Smoke / Scenario
~~~bash
cd /opt/agingos
AGINGOS_API_KEY=YOUR_API_KEY bash scripts/smoke_sprint2.sh
~~~

## Config
`/opt/agingos/.env` is used for local overrides (not committed). Minimum required:
~~~env
AI_BOT_ENABLED=true
~~~
