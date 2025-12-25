PYTHON := .venv/bin/python
.PHONY: up down logs smoke statusflow help

up:
	docker compose up -d --build
	@echo "Running migrations..."
	docker compose exec -T backend alembic -c alembic.ini upgrade head

down:
	docker compose down

logs:
	docker compose logs -f

smoke:
	./examples/scripts/smoke_test.sh

statusflow:
	PYTHONPATH=backend DATABASE_URL="postgresql://agingos:agingos@localhost:5432/agingos" $(PYTHON) -m pytest -q backend/tests/test_status_flow_open_ack_close_reopen.py

.PHONY: scenario-reset

scenario-reset:
	docker compose exec db psql -U agingos -d agingos -c "TRUNCATE TABLE events, deviations_v1, deviations RESTART IDENTITY CASCADE;"

.PHONY: scenario

scenario:
	./examples/scripts/scenario_runner.py docs/testing/scenarios/sc_empty_no_devs.yaml

help:
	@echo "Targets:"
	@echo "  make up         - start services"
	@echo "  make down       - stop services"
	@echo "  make logs       - follow logs"
	@echo "  make smoke      - run smoke test"
	@echo "  make statusflow - run status flow test (T-0303)"
