#!/usr/bin/env bash

set -Eeuo pipefail

ENVIRONMENT="${1:?Usage: backup.sh <production|staging>}"
TARGET_DIR="${2:-$(pwd)}"

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

BACKUP_BASE="${BACKUP_ROOT:-/opt/yembro/backups/${APP_ENVIRONMENT:-${ENVIRONMENT}}}"
DAILY_DIR="${BACKUP_BASE}/daily"
WEEKLY_DIR="${BACKUP_BASE}/weekly"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}"

DB_FILE="${DAILY_DIR}/db-${TIMESTAMP}.sql.gz"
UPLOADS_FILE="${DAILY_DIR}/uploads-${TIMESTAMP}.tar.gz"

docker compose "${compose_args[@]}" up -d postgres redis >/dev/null

docker compose "${compose_args[@]}" exec -T postgres sh -c \
  'export PGPASSWORD="$POSTGRES_PASSWORD"; pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "${DB_FILE}"

docker run --rm \
  -v "${UPLOADS_VOLUME_NAME}:/source:ro" \
  -v "${DAILY_DIR}:/backup" \
  alpine:3.20 \
  sh -c "tar -czf /backup/$(basename "${UPLOADS_FILE}") -C /source ."

if [[ "$(date -u +%u)" == "7" ]]; then
  cp "${DB_FILE}" "${WEEKLY_DIR}/"
  cp "${UPLOADS_FILE}" "${WEEKLY_DIR}/"
fi

prune_backups() {
  local directory="$1"
  local prefix="$2"
  local keep="$3"
  mapfile -t files < <(find "${directory}" -maxdepth 1 -type f -name "${prefix}-*" | sort)
  if (( ${#files[@]} <= keep )); then
    return
  fi

  for file in "${files[@]:0:${#files[@]}-keep}"; do
    rm -f "${file}"
  done
}

prune_backups "${DAILY_DIR}" "db" 7
prune_backups "${DAILY_DIR}" "uploads" 7
prune_backups "${WEEKLY_DIR}" "db" 4
prune_backups "${WEEKLY_DIR}" "uploads" 4

echo "Backup completed:"
echo "  ${DB_FILE}"
echo "  ${UPLOADS_FILE}"
