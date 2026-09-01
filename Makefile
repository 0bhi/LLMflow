.PHONY: up down build logs migrate test lint format clean seed demo

up:
	docker compose up -d

up-build:
	docker compose up -d --build

down:
	docker compose down

down-clean:
	docker compose down -v

build:
	docker compose build

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-worker:
	docker compose logs -f worker

logs-inference:
	docker compose logs -f inference

logs-frontend:
	docker compose logs -f frontend

migrate:
	docker compose exec backend alembic upgrade head

migrate-create:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

migrate-downgrade:
	docker compose exec backend alembic downgrade -1

test:
	docker compose exec backend pytest tests/ -v

test-cov:
	docker compose exec backend pytest tests/ -v --cov=app --cov-report=html

lint:
	docker compose exec backend ruff check app/
	cd frontend && npm run lint

format:
	docker compose exec backend ruff format app/

seed:
	docker compose exec backend python -m scripts.seed_data

shell-backend:
	docker compose exec backend /bin/bash

shell-db:
	docker compose exec postgres psql -U llmflow -d llmflow

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

# ---------- One-command demo ----------
# Starts all services, runs migrations, then drives the full pipeline:
#   upload dataset → split → fine-tune GPT-2 with LoRA → eval perplexity → deploy → query
demo:
	@echo "=== LLMflow Demo ==="
	@echo "Starting services..."
	docker compose up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 15
	docker compose exec backend alembic upgrade head
	@echo "Running end-to-end pipeline..."
	pip install requests --quiet 2>/dev/null || true
	python demo/run_demo.py --api-url http://localhost:8000 --inference-url http://localhost:8001
