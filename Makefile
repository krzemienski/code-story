# Code Story Development Makefile
# ================================
# Quick commands for local development with Docker Compose

.PHONY: help up down logs migrate seed shell test clean rebuild health

# Default target
help:
	@echo "Code Story Development Commands"
	@echo "================================"
	@echo ""
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - View service logs"
	@echo "  make logs-f      - Follow service logs"
	@echo "  make logs-backend- Follow backend logs"
	@echo ""
	@echo "  make migrate     - Run database migrations"
	@echo "  make migrate-new - Create new migration (msg=description)"
	@echo "  make seed        - Seed database with test data"
	@echo ""
	@echo "  make shell       - Open backend shell"
	@echo "  make shell-db    - Open PostgreSQL shell"
	@echo "  make shell-redis - Open Redis CLI"
	@echo ""
	@echo "  make test        - Run tests"
	@echo "  make test-cov    - Run tests with coverage"
	@echo ""
	@echo "  make clean       - Remove all containers and volumes"
	@echo "  make rebuild     - Rebuild all containers"
	@echo "  make health      - Check service health"
	@echo ""

# =============================================================================
# Service Management
# =============================================================================

# Start all services
up:
	docker compose up -d
	@echo ""
	@echo "Services starting..."
	@echo "  Frontend:       http://localhost:3000"
	@echo "  Backend API:    http://localhost:8000"
	@echo "  API Docs:       http://localhost:8000/api/docs"
	@echo "  Mobile (Web):   http://localhost:8081"
	@echo ""
	@echo "Run 'make logs-f' to follow logs"

# Start specific services
up-backend:
	docker compose up -d postgres redis backend

up-frontend:
	docker compose up -d frontend

up-mobile:
	docker compose up -d mobile

# Stop all services
down:
	docker compose down

# View logs
logs:
	docker compose logs

logs-f:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend celery-worker

logs-frontend:
	docker compose logs -f frontend

# =============================================================================
# Database Operations
# =============================================================================

# Run migrations
migrate:
	docker compose exec backend uv run alembic upgrade head

# Create a new migration
migrate-new:
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a migration message: make migrate-new msg='description'"; \
		exit 1; \
	fi
	docker compose exec backend uv run alembic revision --autogenerate -m "$(msg)"

# Downgrade last migration
migrate-down:
	docker compose exec backend uv run alembic downgrade -1

# Show migration history
migrate-history:
	docker compose exec backend uv run alembic history

# Seed database
seed:
	docker compose exec backend uv run python -m scripts.seed_db

# =============================================================================
# Shell Access
# =============================================================================

# Backend shell
shell:
	docker compose exec backend bash

# Python REPL with app context
shell-python:
	docker compose exec backend uv run python

# PostgreSQL shell
shell-db:
	docker compose exec postgres psql -U postgres -d codestory

# Redis CLI
shell-redis:
	docker compose exec redis redis-cli

# =============================================================================
# Testing
# =============================================================================

# Run tests
test:
	docker compose exec backend uv run pytest -v

# Run tests with coverage
test-cov:
	docker compose exec backend uv run pytest --cov=codestory --cov-report=html --cov-report=term

# Run specific test file
test-file:
	@if [ -z "$(file)" ]; then \
		echo "Error: Please provide a test file: make test-file file=tests/test_api.py"; \
		exit 1; \
	fi
	docker compose exec backend uv run pytest -v $(file)

# =============================================================================
# Local Development (without Docker)
# =============================================================================

# Install dependencies locally
install:
	uv sync

# Run backend locally
dev:
	uv run uvicorn codestory.api.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend locally
dev-frontend:
	cd src/codestory/frontend && npm run dev

# Run mobile locally
dev-mobile:
	cd src/codestory/mobile && npx expo start

# =============================================================================
# Cleanup
# =============================================================================

# Full cleanup (removes volumes)
clean:
	docker compose down -v --remove-orphans
	docker system prune -f

# Rebuild without cache
rebuild:
	docker compose down
	docker compose build --no-cache
	docker compose up -d

# Remove only containers (keep volumes)
stop:
	docker compose down --remove-orphans

# =============================================================================
# Health & Status
# =============================================================================

# Check service health
health:
	@echo "Checking service health..."
	@echo ""
	@echo "Backend:"
	@curl -sf http://localhost:8000/api/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  Not ready"
	@echo ""
	@echo "Frontend:"
	@curl -sf http://localhost:3000 >/dev/null 2>&1 && echo "  OK" || echo "  Not ready"
	@echo ""
	@echo "PostgreSQL:"
	@docker compose exec -T postgres pg_isready -U postgres 2>/dev/null && echo "  OK" || echo "  Not ready"
	@echo ""
	@echo "Redis:"
	@docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo "  OK" || echo "  Not ready"

# Show running containers
status:
	docker compose ps

# =============================================================================
# API Documentation
# =============================================================================

# Export OpenAPI spec
openapi:
	uv run python scripts/export_openapi.py

# Open API docs in browser
docs:
	@echo "Opening API documentation..."
	@xdg-open http://localhost:8000/api/docs 2>/dev/null || open http://localhost:8000/api/docs 2>/dev/null || echo "Open http://localhost:8000/api/docs in your browser"
