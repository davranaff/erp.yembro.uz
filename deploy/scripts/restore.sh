#!/usr/bin/env bash

set -Eeuo pipefail

ENVIRONMENT="${1:?Usage: restore.sh <production|staging> <db_dump.sql.gz> [uploads.tar.gz] [target_dir]}"
DB_DUMP="${2:?Usage: restore.sh <production|staging> <db_dump.sql.gz> [uploads.tar.gz] [target_dir]}"
UPLOADS_ARCHIVE="${3:-}"
TARGET_DIR="${4:-$(pwd)}"

case "${ENVIRONMENT}" in
  production)
    OVERRIDE_FILE="compose.prod.yml"
    ;;
  staging)
    OVERRIDE_FILE="compose.staging.yml"
    ;;
  *)
    echo "Unsupported environment: ${ENVIRONMENT}" >&2
    exit 1
    ;;
esac

cd "${TARGET_DIR}"

if [[ ! -f .env ]]; then
  echo "Missing ${TARGET_DIR}/.env" >&2
  exit 1
fi

set -a
source ./.env
if [[ -f .release.env ]]; then
  source ./.release.env
fi
set +a

compose_args=(
  --env-file .env
  -f compose.base.yml
  -f "${OVERRIDE_FILE}"
)

if [[ -f .release.env ]]; then
  compose_args+=(--env-file .release.env)
fi

docker compose "${compose_args[@]}" up -d postgres redis

for attempt in $(seq 1 20); do
  if docker compose "${compose_args[@]}" exec -T postgres sh -c \
    'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" -h 127.0.0.1 -p 5432' >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

docker compose "${compose_args[@]}" exec -T postgres sh -c \
  'export PGPASSWORD="$POSTGRES_PASSWORD"; psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'

gunzip -c "${DB_DUMP}" \
  | docker compose "${compose_args[@]}" exec -T postgres sh -c \
      'export PGPASSWORD="$POSTGRES_PASSWORD"; psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'

if [[ -n "${UPLOADS_ARCHIVE}" ]]; then
  docker run --rm \
    -v "${UPLOADS_VOLUME_NAME}:/target" \
    -v "$(dirname "${UPLOADS_ARCHIVE}"):/restore:ro" \
    alpine:3.20 \
    sh -c "find /target -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -xzf /restore/$(basename "${UPLOADS_ARCHIVE}") -C /target"
fi

docker compose "${compose_args[@]}" run --rm migrate
docker compose "${compose_args[@]}" up -d api worker scheduler frontend

echo "Restore completed for ${ENVIRONMENT}"
