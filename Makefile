SHELL := /bin/bash

COMPOSE_FILE ?= docker-compose.yml
PYTHON ?= python
BACKEND_DIR ?= backend

.PHONY: help install install-backend install-frontend install-all up down logs logs-frontend test test-integration db-clean fixtures fixtures-minimal fixtures-list permissions-sync permissions-sync-dry permissions-sync-codes-only permissions-check

help:
	@echo "Available targets:"
	@echo "  make install         - install backend dependencies"
	@echo "  make install-frontend - install frontend dependencies"
	@echo "  make install-all      - install backend + frontend dependencies"
	@echo "  make up              - build and start docker compose services"
	@echo "  make down            - stop and remove compose services (volumes)"
	@echo "  make logs            - show logs of all services"
	@echo "  make logs-frontend   - show frontend container logs"
	@echo "  make test            - run all backend tests"
	@echo "  make test-integration - run backend integration tests"
	@echo "  make db-clean        - truncate all database tables and reset identities"
	@echo "  make fixtures        - load backend fixtures into the running database"
	@echo "  make fixtures-minimal - reset database and load a minimal seed (1 org, 1 admin user)"
	@echo "  make fixtures-list   - print available backend fixture files"
	@echo "  make permissions-sync - auto-sync all permissions discovered in project sources"
	@echo "  make permissions-sync-dry - preview permission sync changes without writing to DB"
	@echo "  make permissions-sync-codes-only - sync permissions table only (skip privileged role grants)"
	@echo "  make permissions-check - fail if there are missing permissions or privileged role grants"

install:
	cd $(BACKEND_DIR) && $(PYTHON) -m pip install -r requirements.txt

install-backend:
	cd $(BACKEND_DIR) && $(PYTHON) -m pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

install-all: install-backend install-frontend

up:
	docker compose -f $(COMPOSE_FILE) up --build -d

down:
	docker compose -f $(COMPOSE_FILE) down --remove-orphans -v

logs:
	docker compose -f $(COMPOSE_FILE) logs -f

logs-frontend:
	docker compose -f $(COMPOSE_FILE) logs -f frontend

test:
	cd $(BACKEND_DIR) && pytest

test-integration:
	cd $(BACKEND_DIR) && pytest tests/integration

db-clean:
	docker compose -f $(COMPOSE_FILE) exec -T api python -m app.scripts.db_clean

fixtures:
	docker compose -f $(COMPOSE_FILE) exec -T api python -m app.scripts.load_fixtures

fixtures-minimal:
	docker compose -f $(COMPOSE_FILE) exec -T api python -m app.scripts.load_minimal_fixtures

fixtures-list:
	@echo "Available fixtures in $(BACKEND_DIR)/fixtures"
	@find $(BACKEND_DIR)/fixtures -maxdepth 1 -type f -name '*.yaml' -print

permissions-sync:
	docker compose -f $(COMPOSE_FILE) exec -T api python -m app.scripts.sync_permissions

permissions-sync-dry:
	docker compose -f $(COMPOSE_FILE) exec -T api python -m app.scripts.sync_permissions --dry-run

permissions-sync-codes-only:
	docker compose -f $(COMPOSE_FILE) exec -T api python -m app.scripts.sync_permissions --skip-privileged-roles

permissions-check:
	docker compose -f $(COMPOSE_FILE) exec -T api python -m app.scripts.sync_permissions --dry-run --fail-on-diff
