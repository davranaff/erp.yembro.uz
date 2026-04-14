#!/usr/bin/env bash

set -Eeuo pipefail

ENVIRONMENT="${1:?Usage: seed-data.sh <production|staging> <minimal|full> [target_dir] }"
FIXTURE_SET="${2:?Usage: seed-data.sh <production|staging> <minimal|full> [target_dir] }"
TARGET_DIR="${3:-$(pwd)}"
CONFIRM_RESET="${CONFIRM_RESET:-}"

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

case "${FIXTURE_SET}" in
  minimal)
    LOADER_MODULE="app.scripts.load_minimal_fixtures"
    ;;
  full)
    LOADER_MODULE="app.scripts.load_fixtures"
    ;;
  *)
    echo "Unsupported fixture set: ${FIXTURE_SET}. Expected minimal or full." >&2
    exit 1
    ;;
esac

if [[ "${CONFIRM_RESET}" != "${ENVIRONMENT}" ]]; then
  echo "Refusing to reset ${ENVIRONMENT} data." >&2
  echo "Set CONFIRM_RESET=${ENVIRONMENT} and run again if you really want to load fixtures." >&2
  exit 1
fi

cd "${TARGET_DIR}"

if [[ ! -f .env ]]; then
  echo "Missing ${TARGET_DIR}/.env" >&2
  exit 1
fi

if [[ ! -f .release.env && -z "${BACKEND_IMAGE:-}" ]]; then
  echo "Missing ${TARGET_DIR}/.release.env. Deploy the stack first or export BACKEND_IMAGE." >&2
  exit 1
fi

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
    POSTGRES_READY=1
    break
  fi
  sleep 3
done

if [[ "${POSTGRES_READY:-0}" != "1" ]]; then
  echo "Postgres did not become ready in time." >&2
  exit 1
fi

docker compose "${compose_args[@]}" run --rm api python -m "${LOADER_MODULE}"

echo "Fixtures loaded for ${ENVIRONMENT}: ${FIXTURE_SET}"
