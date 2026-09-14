.PHONY: up down logs lint test fmt seed eval

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	cd backend && uv run ruff check app && uv run mypy app
	cd frontend && npm run lint

fmt:
	cd backend && uv run ruff format app tests

test:
	cd backend && uv run pytest -q

seed:
	cd backend && uv run python -m scripts.seed

eval:
	cd backend && uv run python -m scripts.run_eval
