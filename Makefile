.PHONY: up down logs smoke statusflow help

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

smoke:
	./examples/scripts/smoke_test.sh

statusflow:
	PYTHONPATH=backend DATABASE_URL="postgresql://agingos:agingos@localhost:5432/agingos" python3 -m pytest -q backend/tests/test_status_flow_open_ack_close_reopen.py



help:
	@echo "Targets:"
	@echo "  make up         - start services"
	@echo "  make down       - stop services"
	@echo "  make logs       - follow logs"
	@echo "  make smoke      - run smoke test"
	@echo "  make statusflow - run status flow test (T-0303)"
