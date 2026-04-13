# Deployment infrastructure

Этот каталог содержит production/staging deployment stack для `Yembro`.

## Что входит

- `compose.base.yml` — общий app stack
- `compose.prod.yml` — production override
- `compose.staging.yml` — staging override
- `compose.edge.yml` — общий edge proxy с `Caddy` для обоих окружений на одном VPS
- `deploy/caddy/Caddyfile` — TLS и host-based routing
- `deploy/scripts/deploy.sh` — выкатка новой версии
- `deploy/scripts/rollback.sh` — откат на предыдущие image refs
- `deploy/scripts/backup.sh` — backup PostgreSQL и uploads
- `deploy/scripts/restore.sh` — restore БД и uploads
- `deploy/scripts/bootstrap-server.sh` — подготовка каталогов на сервере

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

Отдельный `edge` stack нужен потому, что `production` и `staging` делят один сервер и только один процесс может публиковать `80/443`. `Caddy` принимает внешний HTTPS-трафик и маршрутизирует его в нужную compose-сеть по hostname.

`.env` создаются вручную из шаблонов:

- `.env.prod.example` -> `/opt/yembro/prod/.env`
- `.env.staging.example` -> `/opt/yembro/staging/.env`
- `.env.edge.example` -> `/opt/yembro/edge/.env`

`.release.env` управляется deploy-скриптом и хранит текущие `BACKEND_IMAGE` и `FRONTEND_IMAGE`.

## Bootstrap

На сервере один раз:

```bash
chmod +x deploy/scripts/bootstrap-server.sh
./deploy/scripts/bootstrap-server.sh /opt/yembro
```

Потом:

1. заполнить `/opt/yembro/prod/.env`
2. заполнить `/opt/yembro/staging/.env`
3. заполнить `/opt/yembro/edge/.env`
4. поставить Docker Engine + Docker Compose plugin

## Manual deploy

Production:

```bash
cd /opt/yembro/prod
BACKEND_IMAGE=ghcr.io/<owner>/<repo>/backend:sha-<commit> \
FRONTEND_IMAGE=ghcr.io/<owner>/<repo>/frontend:sha-<commit> \
EDGE_DIR=/opt/yembro/edge \
./deploy/scripts/deploy.sh production
```

Staging:

```bash
cd /opt/yembro/staging
BACKEND_IMAGE=ghcr.io/<owner>/<repo>/backend:sha-<commit> \
FRONTEND_IMAGE=ghcr.io/<owner>/<repo>/frontend:sha-<commit> \
EDGE_DIR=/opt/yembro/edge \
./deploy/scripts/deploy.sh staging
```

## Rollback

```bash
cd /opt/yembro/prod
EDGE_DIR=/opt/yembro/edge ./deploy/scripts/rollback.sh production
```

Скрипт использует `.release.env.previous`.
Откат image refs не откатывает схему БД автоматически и не гоняет миграции назад.

## Backups

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

## Restore

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

## GitHub Actions secrets

Ожидаются environment-specific secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_KNOWN_HOSTS`
- `GHCR_PULL_USERNAME`
- `GHCR_PULL_TOKEN`
- `PUBLIC_BASE_URL`

`staging` environment должен указывать на staging VPS/host values.  
`production` environment должен указывать на production values.
