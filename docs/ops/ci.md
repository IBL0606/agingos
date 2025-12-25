# CI (GitHub Actions) – feilsøking

Denne siden er for feilsøking og detaljer. Daglig “hvordan lese CI” ligger i README.md.

## Hva CI kjører (oversikt)

- Lint/format (fail fast): `ruff format --check` og `ruff check`
- Docker-baserte tester: `make up` → `make smoke` → `make scenario` → `make down`

## Vanlige feil og tiltak

### 1) Lint/format feiler
Symptomer:
- `ruff format --check` sier “Would reformat …”
- `ruff check` viser f.eks. `F401 imported but unused`

Tiltak:
- Kjør lokalt:
  - `ruff format .`
  - `ruff check --fix .`
  - `ruff check .`

### 2) Docker/Compose-feil i CI
Symptomer:
- Compose starter ikke, images kan ikke hentes, eller containere dør umiddelbart.

Tiltak:
- Åpne jobbloggen og finn første reelle feil (ofte under `make up`).
- Se containerstatus og logs lokalt for å reprodusere:
  - `docker compose ps`
  - `docker compose logs --tail=200`

### 3) Database ikke klar / connection refused
Symptomer:
- `psycopg2.OperationalError: connection refused`
- Tester feiler tidlig.

Tiltak:
- Sørg for at DB readiness-sjekk er i kjeden (CI bruker `make up` som venter på db).
- Ved lokal debugging:
  - `docker compose exec -T db pg_isready -U agingos -d agingos`

### 4) Migrasjoner / schema-problemer
Symptomer:
- `relation "events" does not exist`
- Alembic feiler på `upgrade head`

Tiltak:
- Kjør migrasjoner eksplisitt:
  - `docker compose exec -T backend alembic -c alembic.ini upgrade head`
- Ved “fresh DB”:
  - `make down`
  - `docker volume rm agingos_pgdata`
  - `make up`

### 5) Smoke/scenario feiler
Tiltak:
- Kjør samme sekvens lokalt som CI:
  - `make down || true`
  - `make up`
  - `make smoke`
  - `make scenario`
  - `make down`
- Reset av scenario-data kjøres via `make scenario-reset`.
