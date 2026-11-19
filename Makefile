.PHONY: dev dev-api dev-worker dev-web test lint typecheck fixtures docker-up docker-down clean

PYTHON ?= python

dev:
	@echo "Starting full development stack with Docker Compose..."
	docker compose -f infra/docker-compose.yml up --build

dev-api:
	$(PYTHON) -m uvicorn apps.api.src.main:app --host 0.0.0.0 --port 8000 --reload

dev-worker:
	arq apps.worker.src.runner.WorkerSettings

dev-web:
	cd apps/web && npm run dev

test:
	PYTHONPATH=. $(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check apps/ tests/

typecheck:
	$(PYTHON) -m mypy apps/api/src/core apps/api/src/schemas

fixtures:
	PYTHONPATH=. $(PYTHON) tests/fixtures/make_fixtures.py

docker-up:
	docker compose -f infra/docker-compose.yml up -d --build

docker-down:
	docker compose -f infra/docker-compose.yml down

clean:
	rm -rf .pytest_cache tests/**/__pycache__ apps/**/__pycache__ apps/web/.next
