.PHONY: dev test build clean docker-up docker-down

PYTHON ?= python

dev-api:
	$(PYTHON) -m uvicorn apps.api.src.main:app --host 0.0.0.0 --port 8000 --reload

dev-web:
	cd apps/web && npm run dev

test:
	PYTHONPATH=. $(PYTHON) -m pytest tests/ -v

docker-up:
	docker compose -f infra/docker-compose.yml up --build

docker-down:
	docker compose -f infra/docker-compose.yml down

clean:
	rm -rf .pytest_cache tests/__pycache__ apps/api/src/**/__pycache__ apps/worker/src/**/__pycache__
