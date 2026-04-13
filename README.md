# Yembro

![Yembro](assets/yembro.png)

Yembro is a full-stack poultry management platform with a FastAPI backend, a React/Vite frontend, and Docker-based local and server deployment.

## Repository layout

- `backend/` - FastAPI application, Alembic migrations, Taskiq workers, fixtures, and tests
- `frontend/` - React 18 + Vite application
- `deploy/` - deployment scripts, Caddy config, backup and rollback tooling
- `.github/workflows/` - staging and production deployment workflows

## Stack

- FastAPI
- PostgreSQL
- Redis
- Alembic
- Taskiq
- React
- Vite
- Docker Compose

## Local development

Create the local environment file and start the stack from the repository root:

```bash
cp .env.example .env
docker compose up --build
```

Alternative via `make`:

```bash
make up
```

## Useful commands

```bash
make install-all
make up
make down
make logs
make test
make test-integration
make fixtures
make permissions-check
```

## Services

- `frontend` - Vite development server
- `api` - FastAPI application
- `worker` - background jobs
- `scheduler` - scheduled jobs
- `postgres` - primary database
- `redis` - queue and cache

## Environments and deployment

- Local development uses `.env.example`
- Staging uses `.env.staging.example`
- Production uses `.env.prod.example`
- Edge proxy configuration uses `.env.edge.example`

GitHub Actions build and publish backend/frontend images, then deploy them to the target server. Deployment details are documented in [deploy/README.md](deploy/README.md).

## Additional docs

- [backend/README.md](backend/README.md)
- [deploy/README.md](deploy/README.md)
