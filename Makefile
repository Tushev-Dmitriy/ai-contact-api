.PHONY: install run test lint format typecheck migrate docker-up docker-down

install:
	uv sync --all-groups

run:
	uv run uvicorn app.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app

migrate:
	uv run alembic upgrade head

docker-up:
	docker compose up --build

docker-down:
	docker compose down
