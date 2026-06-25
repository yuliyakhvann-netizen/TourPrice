.PHONY: up down build migrate shell-db shell-backend test lint

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

migrate:
	docker-compose exec backend alembic upgrade head

migrate-create:
	docker-compose exec backend alembic revision --autogenerate -m "$(name)"

shell-db:
	docker-compose exec db psql -U tourprice -d tourprice

shell-backend:
	docker-compose exec backend bash

test:
	docker-compose exec backend pytest tests/ -v

lint:
	docker-compose exec backend ruff check app/ && mypy app/

logs:
	docker-compose logs -f backend
