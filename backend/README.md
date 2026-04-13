# Yembro FastAPI Async Backend (base scaffold)

Базовый асинхронный backend шаблон, вынесенный в папку `backend/`:

- FastAPI
- asyncpg (пул подключений)
- Alembic
- PostgreSQL
- Redis
- Taskiq + Scheduler + Worker

## Структура

- `app/core` — конфигурация, логирование, базовые абстракции.
- `app/db` — асинхронный пул данных.
- `app/api` — HTTP слой (`/health`, `/api/v1/system/ping`).
- `app/tasks` — Taskiq брокер и scheduler.
- `app/utils` — служебные утилиты.
- `alembic` — миграции (базовый шаблон).

## Быстрый старт (из корня репозитория)

```bash
cp .env.example .env
docker compose up --build
```

## Прод окружение

```bash
cp .env.example .env
docker compose up --build
```

## API

- `GET /health`
- `GET /api/v1/system/ping`

## Планировщик и воркер

- `worker` сервис запускает `taskiq worker app.taskiq_app:broker --fs-discover`
- `scheduler` сервис запускает `taskiq scheduler app.tasks.scheduler:scheduler app.tasks.jobs`
- пример фоновой задачи: `heartbeat_task` в `app/tasks/jobs.py`
