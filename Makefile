.PHONY: install run test lint format typecheck migrate model docker-up docker-down

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

model:
	mkdir -p models
	test -f models/qwen2.5-1.5b-instruct-q4_k_m.gguf || curl -L --fail --retry 3 -o models/qwen2.5-1.5b-instruct-q4_k_m.gguf https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf

docker-up:
	docker compose up --build

docker-down:
	docker compose down
