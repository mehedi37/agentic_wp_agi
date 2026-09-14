.PHONY: up down logs lint test fmt seed eval migrate env

env:
	test -f .env || cp .env.example .env

up: env
	docker compose up -d --build
	bash scripts/wait_for_services.sh
	$(MAKE) migrate

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	cd backend && uv run ruff check . && uv run mypy app
	cd frontend && npm run lint

fmt:
	cd backend && uv run ruff format app tests

test:
	cd backend && uv run pytest -q

migrate:
	cd backend && uv run alembic upgrade head

seed: migrate
	cd backend && uv run python -m scripts.seed

eval:
	cd backend && uv run python -m scripts.run_eval
