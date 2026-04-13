#!/usr/bin/env bash

set -Eeuo pipefail

ENVIRONMENT="${1:?Usage: deploy.sh <production|staging>}"
TARGET_DIR="${2:-$(pwd)}"
EDGE_DIR="${EDGE_DIR:-/opt/yembro/edge}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"

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

if [[ -z "${BACKEND_IMAGE:-}" || -z "${FRONTEND_IMAGE:-}" ]]; then
  echo "BACKEND_IMAGE and FRONTEND_IMAGE must be provided" >&2
  exit 1
fi

cd "${TARGET_DIR}"

if [[ ! -f .env ]]; then
  echo "Missing ${TARGET_DIR}/.env" >&2
  exit 1
fi

set -a
source ./.env
if [[ -f "${EDGE_DIR}/.env" ]]; then
  source "${EDGE_DIR}/.env"
fi
set +a

mkdir -p "${BACKUP_ROOT:-/opt/yembro/backups/${APP_ENVIRONMENT:-${ENVIRONMENT}}}"

if [[ -f .release.env ]]; then
  cp .release.env .release.env.previous
fi

cat > .release.env <<EOF
BACKEND_IMAGE=${BACKEND_IMAGE}
FRONTEND_IMAGE=${FRONTEND_IMAGE}
EOF

docker network create "${PROD_PUBLIC_NETWORK_NAME:-yembro_prod_public}" >/dev/null 2>&1 || true
docker network create "${STAGING_PUBLIC_NETWORK_NAME:-yembro_staging_public}" >/dev/null 2>&1 || true

compose_args=(
  --env-file .env
  --env-file .release.env
  -f compose.base.yml
  -f "${OVERRIDE_FILE}"
)

docker compose "${compose_args[@]}" up -d postgres redis
docker compose "${compose_args[@]}" pull api worker scheduler frontend
if [[ "${RUN_MIGRATIONS}" == "1" ]]; then
  docker compose "${compose_args[@]}" run --rm migrate
fi
docker compose "${compose_args[@]}" up -d api worker scheduler frontend

if [[ -f "${EDGE_DIR}/compose.edge.yml" && -f "${EDGE_DIR}/.env" ]]; then
  edge_compose_args=(
    --env-file "${EDGE_DIR}/.env"
    -f "${EDGE_DIR}/compose.edge.yml"
  )
  docker compose "${edge_compose_args[@]}" up -d proxy
fi

service_is_ready() {
  local service="$1"
  local container_id
  local state
  local health

  container_id="$(docker compose "${compose_args[@]}" ps -q "${service}")"
  if [[ -z "${container_id}" ]]; then
    return 1
  fi

  state="$(docker inspect -f '{{.State.Status}}' "${container_id}")"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "${container_id}")"

  if [[ "${state}" != "running" ]]; then
    return 1
  fi

  if [[ -n "${health}" && "${health}" != "healthy" ]]; then
    return 1
  fi

  return 0
}

for attempt in $(seq 1 30); do
  if service_is_ready postgres \
    && service_is_ready redis \
    && service_is_ready api \
    && service_is_ready worker \
    && service_is_ready scheduler \
    && service_is_ready frontend; then
    echo "Deployment is healthy for ${ENVIRONMENT}"
    exit 0
  fi

  sleep 5
done

echo "Deployment health checks failed for ${ENVIRONMENT}" >&2
docker compose "${compose_args[@]}" ps >&2
exit 1
