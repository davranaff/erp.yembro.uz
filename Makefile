SHELL := /bin/bash

COMPOSE_FILE ?= docker-compose.yml
PYTHON ?= python
BACKEND_DIR ?= backend
DC := docker compose -f $(COMPOSE_FILE)

.PHONY: help init install install-backend install-frontend install-all \
        up down restart rebuild build logs ps \
        backend-logs frontend-logs celery-logs \
        backend-sh frontend-sh db-sh \
        migrate makemigrations superuser shell collectstatic \
        test test-integration \
        fixtures fixtures-list \
        clean prune

help:
	@echo "Available targets:"
	@echo ""
	@echo "  make init              - copy backend/.env.example -> backend/.env (and frontend)"
	@echo "  make install           - install backend dependencies"
	@echo "  make install-frontend  - install frontend dependencies"
	@echo "  make install-all       - install backend + frontend dependencies"
	@echo ""
	@echo "  make build             - build all images"
	@echo "  make up                - start all services"
	@echo "  make down              - stop all services (keep volumes)"
	@echo "  make restart           - restart all services"
	@echo "  make rebuild           - rebuild and restart"
	@echo "  make logs              - tail all logs"
	@echo "  make ps                - show running services"
	@echo ""
	@echo "  make migrate           - run Django migrations"
	@echo "  make makemigrations    - create Django migrations"
	@echo "  make superuser         - create Django superuser"
	@echo "  make shell             - open Django shell"
	@echo "  make collectstatic     - collect static files"
	@echo ""
	@echo "  make backend-sh        - shell into backend container"
	@echo "  make frontend-sh       - shell into frontend container"
	@echo "  make db-sh             - psql into postgres"
	@echo ""
	@echo "  make test              - run backend tests"
	@echo "  make fixtures          - loaddata for every yaml in backend/fixtures"
	@echo "  make fixtures-list     - print available backend fixture files"
	@echo ""
	@echo "  make clean             - stop and remove containers + volumes"
	@echo "  make prune             - prune docker resources"

init:
	@test -f backend/.env || cp backend/.env.example backend/.env
	@test -f frontend/.env || cp frontend/.env.example frontend/.env 2>/dev/null || true
	@echo "env files ready"

install:
	cd $(BACKEND_DIR) && $(PYTHON) -m pip install -r requirements.txt

install-backend: install

install-frontend:
	cd frontend && npm install

install-all: install-backend install-frontend

build:
	$(DC) build

up:
	$(DC) up -d

down:
	$(DC) down --remove-orphans

restart:
	$(DC) restart

rebuild:
	$(DC) down --remove-orphans
	$(DC) build
	$(DC) up -d

logs:
	$(DC) logs -f

ps:
	$(DC) ps

backend-logs:
	$(DC) logs -f api

frontend-logs:
	$(DC) logs -f frontend

celery-logs:
	$(DC) logs -f worker scheduler

backend-sh:
	$(DC) exec api sh

frontend-sh:
	$(DC) exec frontend sh

db-sh:
	$(DC) exec postgres psql -U $${POSTGRES_USER:-erp} -d $${POSTGRES_DB:-erp}

migrate:
	$(DC) exec api python manage.py migrate

makemigrations:
	$(DC) exec api python manage.py makemigrations

superuser:
	$(DC) exec api python manage.py createsuperuser

shell:
	$(DC) exec api python manage.py shell

collectstatic:
	$(DC) exec api python manage.py collectstatic --noinput

test:
	cd $(BACKEND_DIR) && pytest

test-integration:
	cd $(BACKEND_DIR) && pytest tests/integration

fixtures:
	@for f in $(BACKEND_DIR)/fixtures/*.yaml $(BACKEND_DIR)/fixtures/*.json; do \
	  [ -e "$$f" ] || continue; \
	  echo "loaddata $$f"; \
	  $(DC) exec -T api python manage.py loaddata "$$(basename $$f)"; \
	done

fixtures-list:
	@echo "Available fixtures in $(BACKEND_DIR)/fixtures"
	@find $(BACKEND_DIR)/fixtures -maxdepth 1 -type f \( -name '*.yaml' -o -name '*.json' \) -print 2>/dev/null || echo "  (none)"

clean:
	$(DC) down -v --remove-orphans

prune:
	docker system prune -f
