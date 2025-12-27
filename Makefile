PYTHON := .venv/bin/python

RUFF_VERSION ?= 0.14.10
RUFF_IMAGE := ghcr.io/astral-sh/ruff:$(RUFF_VERSION)

.PHONY: fmt fmt-check lint lint-fix
fmt:
	docker run --rm -v "$(PWD)":/work -w /work $(RUFF_IMAGE) format .

fmt-check:
	docker run --rm -v "$(PWD)":/work -w /work $(RUFF_IMAGE) format --check .

lint:
	docker run --rm -v "$(PWD)":/work -w /work $(RUFF_IMAGE) check .

lint-fix:
	docker run --rm -v "$(PWD)":/work -w /work $(RUFF_IMAGE) check --fix .

.PHONY: field-up field-down field-logs up down logs smoke statusflow help backup-db restore-db scenario-reset scenario

up:
	docker compose up -d --build
	@echo "Waiting for db..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do \
	  if docker compose exec -T db pg_isready -U agingos -d agingos >/dev/null 2>&1; then \
	    echo "DB is ready"; \
	    break; \
	  fi; \
	  sleep 1; \
	done
	@echo "Running migrations..."
	docker compose exec -T backend alembic -c alembic.ini upgrade head

down:
	docker compose down

field-up:
	docker compose -f docker-compose.yml -f docker-compose.field.yml up -d --build db
	@echo "Waiting for db..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do \
	  if docker compose -f docker-compose.yml -f docker-compose.field.yml exec -T db pg_isready -U agingos -d agingos >/dev/null 2>&1; then \
	    echo "DB is ready"; \
	    break; \
	  fi; \
	  sleep 1; \
	done
	@echo "Running migrations..."
	docker compose -f docker-compose.yml -f docker-compose.field.yml run --rm backend alembic -c alembic.ini upgrade head
	@echo "Starting backend..."
	docker compose -f docker-compose.yml -f docker-compose.field.yml up -d --build backend

field-down:
	docker compose -f docker-compose.yml -f docker-compose.field.yml down

field-logs:
	docker compose -f docker-compose.yml -f docker-compose.field.yml logs -f

logs:
	docker compose logs -f

smoke:
	./examples/scripts/smoke_test.sh

statusflow:
	PYTHONPATH=backend DATABASE_URL="postgresql://agingos:agingos@localhost:5432/agingos" $(PYTHON) -m pytest -q backend/tests/test_status_flow_open_ack_close_reopen.py

scenario-reset:
	docker compose exec -T db psql -U agingos -d agingos -c "TRUNCATE TABLE events RESTART IDENTITY CASCADE;" >/dev/null 2>&1 || true
	docker compose exec -T db psql -U agingos -d agingos -c "TRUNCATE TABLE deviations_v1 RESTART IDENTITY CASCADE;" >/dev/null 2>&1 || true
	docker compose exec -T db psql -U agingos -d agingos -c "TRUNCATE TABLE deviations RESTART IDENTITY CASCADE;" >/dev/null 2>&1 || true

scenario:
	./examples/scripts/scenario_runner.py docs/testing/scenarios/sc_empty_no_devs.yaml

backup-db:
	@mkdir -p backups
	@ts=$$(date -u +"%Y%m%dT%H%M%SZ"); \
	out="backups/agingos_$${ts}.sql"; \
	echo "Creating backup: $${out}"; \
	docker compose exec -T db pg_dump -U agingos -d agingos > "$${out}"; \
	echo "OK: wrote $${out}"

restore-db:
	@if [ -z "$$FILE" ]; then \
	  echo "Usage: make restore-db FILE=backups/<file>.sql"; \
	  echo "Available backups:"; \
	  ls -1 backups 2>/dev/null || true; \
	  exit 2; \
	fi
	@echo "Restoring from $$FILE"
	@echo "Resetting schema (DROP SCHEMA public CASCADE; CREATE SCHEMA public;)"
	docker compose exec -T db psql -U agingos -d agingos -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	docker compose exec -T db psql -U agingos -d agingos < "$$FILE"
	@echo "OK: restore complete"

help:
	@echo "Targets:"
	@echo "  make up          - start services (dev)"
	@echo "  make down        - stop services (dev)"
	@echo "  make logs        - follow logs (dev)"
	@echo "  make field-up    - start services (field profile)"
	@echo "  make field-down  - stop services (field profile)"
	@echo "  make field-logs  - follow logs (field profile)"
	@echo "  make smoke       - run smoke test"
	@echo "  make statusflow  - run status flow test (T-0303)"
	@echo "  make scenario    - run scenario smoke"
	@echo "  make backup-db   - create a local SQL backup in ./backups"
	@echo "  make restore-db  - restore DB from FILE=backups/<file>.sql"
	@echo "  make fmt         - format code (ruff via docker)"
	@echo "  make fmt-check   - check formatting (same as CI)"
	@echo "  make lint        - lint (ruff via docker)"
	@echo "  make lint-fix    - lint with auto-fix (ruff via docker)"
