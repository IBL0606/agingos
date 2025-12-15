.PHONY: up down logs smoke

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

smoke:
	./examples/scripts/smoke_test.sh

help:
	@echo "Targets:"
	@echo "  make up     - start services"
	@echo "  make down   - stop services"
	@echo "  make logs   - follow logs"
	@echo "  make smoke  - run smoke test"
