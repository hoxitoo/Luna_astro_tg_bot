.PHONY: up down logs test migrate shell lint

# Docker
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f bot

restart:
	docker-compose restart bot

# Database
migrate:
	docker-compose exec bot alembic upgrade head

migration:
	docker-compose exec bot alembic revision --autogenerate -m "$(name)"

# Tests (run locally without Docker)
test:
	python -m pytest tests/ -v

test-cov:
	python -m pytest tests/ -v --tb=short

# Dev shell inside container
shell:
	docker-compose exec bot python

# Linting
lint:
	python -m ruff check bot/ tests/

# Build
build:
	docker-compose build --no-cache

# Production deploy (run on VPS)
deploy:
	git pull origin main
	docker-compose up -d --build
	docker-compose exec bot alembic upgrade head
