# Deployment infrastructure

Этот каталог содержит production/staging deployment stack для `Yembro` и набор утилит для ручного деплоя на VPS.

## Что входит

- `compose.base.yml` — общий app stack
- `compose.prod.yml` — production override
- `compose.staging.yml` — staging override
- `compose.edge.yml` — общий edge proxy с `Caddy`
- `deploy/caddy/Caddyfile` — TLS и host-based routing
- `deploy/scripts/bootstrap-server.sh` — подготовка каталогов на сервере
- `deploy/scripts/install-docker-ubuntu.sh` — установка Docker Engine и Compose plugin на Ubuntu/Debian VPS
- `deploy/scripts/sync-server-files.sh` — синхронизация compose/env example/deploy assets на сервер
- `deploy/scripts/build-and-push-images.sh` — ручная сборка и публикация backend/frontend образов в registry
- `deploy/scripts/deploy.sh` — выкатка новой версии
- `deploy/scripts/rollback.sh` — откат на предыдущие image refs
- `deploy/scripts/backup.sh` — backup PostgreSQL и uploads
- `deploy/scripts/restore.sh` — restore БД и uploads
- `deploy/scripts/seed-data.sh` — загрузка demo/minimal fixtures в уже развернутый stack

## Схема

Production stack:

- `frontend` — статический React/Vite build в `nginx`
- `api` — FastAPI
- `worker` — Taskiq worker
- `scheduler` — Taskiq scheduler
- `postgres` — основная база
- `redis` — очередь и cache

Edge stack:

- `proxy` — `Caddy`, который публикует `80/443`, получает TLS-сертификаты и маршрутизирует трафик по hostname

## Server layout

На VPS ожидается следующая структура:

```text
/opt/yembro/
  prod/
    .env
    .release.env
    compose.base.yml
    compose.prod.yml
    deploy/
  staging/
    .env
    .release.env
    compose.base.yml
    compose.staging.yml
    deploy/
  edge/
    .env
    compose.edge.yml
    deploy/caddy/Caddyfile
  backups/
    prod/
    staging/
```

`.env` создаются вручную из шаблонов:

- `.env.prod.example` -> `/opt/yembro/prod/.env`
- `.env.staging.example` -> `/opt/yembro/staging/.env`
- `.env.edge.example` -> `/opt/yembro/edge/.env`

`.release.env` управляется `deploy.sh` и хранит текущие `BACKEND_IMAGE` и `FRONTEND_IMAGE`.

## Когда нужен `edge`

Если на одном VPS живут и `production`, и `staging`, только один процесс может слушать `80/443`. Поэтому `Caddy` вынесен в отдельный stack и работает поверх двух compose-сетей:

- production frontend: `https://erp.yembro.uz`
- production api: `https://api.erp.yembro.uz`
- staging frontend: `https://staging.yembro.uz`
- staging api: `https://staging.api.yembro.uz`

Если staging не нужен, можно:

1. не разворачивать `/opt/yembro/staging`
2. использовать только `/opt/yembro/prod` и `/opt/yembro/edge`
3. удалить staging blocks из `deploy/caddy/Caddyfile` до первого запуска `Caddy`

## Требования

- VPS c Ubuntu 22.04/24.04 или Debian 12
- публичный IPv4
- открытые порты `22`, `80`, `443`
- пользователь с `sudo`
- настроенные DNS A-records на VPS
- registry для образов, обычно private Docker Registry

## 1. Подготовить DNS

Для production:

- `erp.yembro.uz` -> IP VPS
- `api.erp.yembro.uz` -> IP VPS

Для staging:

- `staging.yembro.uz` -> IP VPS
- `staging.api.yembro.uz` -> IP VPS

Пока DNS не резолвится наружу, `Caddy` не сможет выпустить TLS-сертификаты.

## 2. Установить Docker на VPS

Самый простой путь:

```bash
curl -fsSL https://raw.githubusercontent.com/<your-org>/<your-repo>/<your-branch>/deploy/scripts/install-docker-ubuntu.sh -o /tmp/install-docker-ubuntu.sh
sudo bash /tmp/install-docker-ubuntu.sh <server-user>
```

Либо скопировать репозиторий на сервер и выполнить:

```bash
chmod +x deploy/scripts/install-docker-ubuntu.sh
sudo ./deploy/scripts/install-docker-ubuntu.sh <server-user>
```

Скрипт ставит:

- `docker-ce`
- `docker-ce-cli`
- `containerd.io`
- `docker-buildx-plugin`
- `docker-compose-plugin`

После добавления пользователя в группу `docker` нужно перелогиниться.

Официальные инструкции Docker:

- Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Docker Compose plugin on Linux: https://docs.docker.com/compose/install/linux/

## 3. Подготовить каталоги на сервере

Один раз:

```bash
chmod +x deploy/scripts/bootstrap-server.sh
./deploy/scripts/bootstrap-server.sh /opt/yembro
```

## 4. Скопировать deployment assets на сервер

С локальной машины:

```bash
chmod +x deploy/scripts/sync-server-files.sh
./deploy/scripts/sync-server-files.sh deploy@YOUR_SERVER_IP 22 /opt/yembro
```

Скрипт:

- создаёт каталоги `prod`, `staging`, `edge`, `backups`
- копирует `compose.base.yml`, `compose.prod.yml`, `compose.staging.yml`
- копирует `.env.*.example`
- копирует `deploy/scripts/*`
- копирует `deploy/caddy/Caddyfile`

Если staging не нужен, его каталог можно просто не использовать.

Если реальные env-файлы уже лежат локально в `.envs`, можно сразу залить их на сервер:

```bash
chmod +x deploy/scripts/merge-env.sh
./deploy/scripts/merge-env.sh deploy@YOUR_SERVER_IP
```

Скрипт берёт:

- `.envs/.env.prod` -> `/opt/yembro/prod/.env`
- `.envs/.env.staging` -> `/opt/yembro/staging/.env`
- `.envs/.env.edge` -> `/opt/yembro/edge/.env`

По умолчанию он обновляет все три файла. Если нужен только один:

```bash
./deploy/scripts/merge-env.sh deploy@YOUR_SERVER_IP staging
./deploy/scripts/merge-env.sh deploy@YOUR_SERVER_IP prod
./deploy/scripts/merge-env.sh deploy@YOUR_SERVER_IP edge
```

Опционально можно передать `ssh_port` и `server_root`:

```bash
./deploy/scripts/merge-env.sh deploy@YOUR_SERVER_IP all 2222 /opt/yembro
```

Перед заменой удалённый `.env` автоматически сохраняется в `.env-backups/`.

## 5. Заполнить `.env` файлы

### `/opt/yembro/prod/.env`

Создай файл из `.env.prod.example` и обязательно замени:

- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `APP_AUTH_SECRET_KEY`
- `APP_PUBLIC_WEB_BASE_URL`
- `APP_CORS_ALLOW_ORIGINS`
- `APP_TELEGRAM_BOT_TOKEN`, если нужны Telegram notifications
- `BACKUP_ROOT`, если нужен нестандартный путь

Минимальный production checklist:

```dotenv
APP_ENVIRONMENT=production
APP_DATABASE_URL=postgresql://yembro_prod:<strong-password>@postgres:5432/yembro_prod
DATABASE_URL=postgresql://yembro_prod:<strong-password>@postgres:5432/yembro_prod
APP_REDIS_URL=redis://:<strong-password>@redis:6379/0
REDIS_URL=redis://:<strong-password>@redis:6379/0
POSTGRES_USER=yembro_prod
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=yembro_prod
REDIS_PASSWORD=<strong-password>
APP_AUTH_SECRET_KEY=<long-random-secret>
APP_PUBLIC_WEB_BASE_URL=https://erp.yembro.uz
APP_CORS_ALLOW_ORIGINS=https://erp.yembro.uz
APP_STORAGE_BACKEND=local
APP_STORAGE_LOCAL_ROOT=/data/uploads
BACKUP_ROOT=/opt/yembro/backups/prod
```

### `/opt/yembro/edge/.env`

Создай файл из `.env.edge.example` и заполни:

```dotenv
COMPOSE_PROJECT_NAME=yembro-edge
CADDY_ACME_EMAIL=ops@example.com
PRIMARY_DOMAIN=erp.yembro.uz
API_PRIMARY_DOMAIN=api.erp.yembro.uz
STAGING_DOMAIN=staging.yembro.uz
API_STAGING_DOMAIN=staging.api.yembro.uz
PROD_PUBLIC_NETWORK_NAME=yembro_prod_public
STAGING_PUBLIC_NETWORK_NAME=yembro_staging_public
```

Если staging не используется, убери staging-сайты из `deploy/caddy/Caddyfile`.

## 6. Собрать и опубликовать образы

`deploy.sh` работает через `docker compose pull`, значит на сервере должны быть доступны уже собранные образы.

Для собственного registry удобна схема:

- `registry.example.com/yembro/backend`
- `registry.example.com/yembro/frontend`

Ручная сборка и push:

```bash
chmod +x deploy/scripts/build-and-push-images.sh
./deploy/scripts/build-and-push-images.sh production registry.example.com/yembro
```

Для staging:

```bash
./deploy/scripts/build-and-push-images.sh staging registry.example.com/yembro
```

Скрипт:

- строит `backend` образ
- строит `frontend` образ
- для фронтенда прошивает корректный `VITE_API_BASE_URL`
- пушит два тега: `sha-<commit>` и environment alias (`production` или `staging`)

Если нужен свой tag:

```bash
./deploy/scripts/build-and-push-images.sh production registry.example.com/yembro sha-20260414 manual-prod
```

## 7. Первый deploy на VPS

На сервере:

```bash
docker login
cd /opt/yembro/prod
chmod +x deploy/scripts/*.sh
```

Выкатить production:

```bash
BACKEND_IMAGE=registry.example.com/yembro/backend:sha-<commit> \
FRONTEND_IMAGE=registry.example.com/yembro/frontend:sha-<commit> \
EDGE_DIR=/opt/yembro/edge \
./deploy/scripts/deploy.sh production
```

Выкатить staging:

```bash
cd /opt/yembro/staging
BACKEND_IMAGE=registry.example.com/yembro/backend:sha-<commit> \
FRONTEND_IMAGE=registry.example.com/yembro/frontend:sha-<commit> \
EDGE_DIR=/opt/yembro/edge \
./deploy/scripts/deploy.sh staging
```

Что делает `deploy.sh`:

1. читает `.env`
2. сохраняет текущий release в `.release.env.previous`
3. записывает новый `.release.env`
4. поднимает `postgres` и `redis`
5. делает `docker compose pull`
6. прогоняет `alembic upgrade head`
7. поднимает `api`, `worker`, `scheduler`, `frontend`
8. поднимает `edge/proxy`, если есть `EDGE_DIR`
9. ждёт health checks всех сервисов

## 8. Первая инициализация данных

Для пустой production БД можно загрузить minimal fixtures:

```bash
cd /opt/yembro/prod
CONFIRM_RESET=production ./deploy/scripts/seed-data.sh production minimal
```

Для полной demo-базы:

```bash
cd /opt/yembro/prod
CONFIRM_RESET=production ./deploy/scripts/seed-data.sh production full
```

Скрипт намеренно требует `CONFIRM_RESET`, потому что загрузка fixtures очищает данные.

Стартовый логин из minimal fixtures:

- username: `EMP-ADM-00`
- password: `changeme`

После первого входа пароль нужно сменить.

## 9. Проверка после deploy

Проверить наружные health endpoints:

```bash
curl -f https://erp.yembro.uz/health
curl -f https://api.erp.yembro.uz/health
```

Проверить контейнеры:

```bash
cd /opt/yembro/prod
docker compose --env-file .env --env-file .release.env -f compose.base.yml -f compose.prod.yml ps
```

Логи:

```bash
docker compose --env-file .env --env-file .release.env -f compose.base.yml -f compose.prod.yml logs -f api
docker compose --env-file /opt/yembro/edge/.env -f /opt/yembro/edge/compose.edge.yml logs -f proxy
```

## 10. Регулярный deploy

Production:

```bash
cd /opt/yembro/prod
BACKEND_IMAGE=registry.example.com/yembro/backend:sha-<new-commit> \
FRONTEND_IMAGE=registry.example.com/yembro/frontend:sha-<new-commit> \
EDGE_DIR=/opt/yembro/edge \
./deploy/scripts/deploy.sh production
```

Staging:

```bash
cd /opt/yembro/staging
BACKEND_IMAGE=registry.example.com/yembro/backend:sha-<new-commit> \
FRONTEND_IMAGE=registry.example.com/yembro/frontend:sha-<new-commit> \
EDGE_DIR=/opt/yembro/edge \
./deploy/scripts/deploy.sh staging
```

## 11. Rollback

```bash
cd /opt/yembro/prod
EDGE_DIR=/opt/yembro/edge ./deploy/scripts/rollback.sh production
```

`rollback.sh` использует `.release.env.previous`.

Важно:

- rollback переключает только image refs
- rollback не откатывает схему БД автоматически
- если новая версия уже применила несовместимые миграции, rollback нужно планировать отдельно

## 12. Backup

Ежедневный backup:

```bash
cd /opt/yembro/prod
./deploy/scripts/backup.sh production
```

Скрипт делает:

- `pg_dump` текущей БД
- архив named volume с uploads
- retention `7 daily + 4 weekly`

Пример cron:

```cron
15 2 * * * cd /opt/yembro/prod && ./deploy/scripts/backup.sh production >> /var/log/yembro-prod-backup.log 2>&1
45 2 * * * cd /opt/yembro/staging && ./deploy/scripts/backup.sh staging >> /var/log/yembro-staging-backup.log 2>&1
```

## 13. Restore

```bash
cd /opt/yembro/prod
./deploy/scripts/restore.sh production /opt/yembro/backups/prod/daily/db-<timestamp>.sql.gz /opt/yembro/backups/prod/daily/uploads-<timestamp>.tar.gz
```

Порядок:

1. поднимаются `postgres` и `redis`
2. очищается schema `public`
3. восстанавливается SQL dump
4. опционально восстанавливаются uploads
5. прогоняются миграции
6. перезапускаются `api`, `worker`, `scheduler`, `frontend`

## 14. GitHub Actions

Branch mapping:

- `main` -> `staging`
- `production` -> `production`

Workflow:

1. build backend image
2. build frontend image
3. push оба образа в private registry
4. sync deployment assets на сервер
5. remote `docker login`
6. remote `deploy.sh`
7. `curl` публичного health endpoint

Нужные environment-specific secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_KNOWN_HOSTS`
- `REGISTRY_USERNAME`
- `REGISTRY_PASSWORD`
- `PUBLIC_BASE_URL`

Нужные GitHub Actions vars:

- `REGISTRY_HOST`
- `REGISTRY_BACKEND_REPO`
- `REGISTRY_FRONTEND_REPO`

## 15. Частые проблемы

### `proxy` не поднимается

Проверь:

- DNS уже указывает на VPS
- `80/443` открыты
- `PRIMARY_DOMAIN` и `API_PRIMARY_DOMAIN` заполнены корректно

### `frontend` открывается, но API requests падают

Проверь:

- правильный `VITE_API_BASE_URL` был зашит при сборке frontend image
- `Caddy` проксирует `/api/*` на `prod-api:30000`
- `APP_CORS_ALLOW_ORIGINS` соответствует домену фронтенда

### `docker compose pull` просит login

На сервере нужен:

```bash
docker login
```

### `seed-data.sh` отказывается запускаться

Это нормальная защита. Нужен явный confirm:

```bash
CONFIRM_RESET=production ./deploy/scripts/seed-data.sh production minimal
```

### `api` unhealthy

Проверь:

- `APP_DATABASE_URL`
- `APP_REDIS_URL`
- применились ли миграции
- логи `api` и `postgres`
