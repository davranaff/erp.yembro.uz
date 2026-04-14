#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  build-and-push-images.sh <production|staging> <backend_repo> <frontend_repo> [sha_tag] [alias_tag]

Docker Hub example:
  build-and-push-images.sh production davranaff/yembro-backend davranaff/yembro-frontend

Legacy common-prefix mode is also supported:
  build-and-push-images.sh production registry.example.com/yembro [sha_tag] [alias_tag]
EOF
}

ENVIRONMENT="${1:-}"
ARG2="${2:-}"
ARG3="${3:-}"

if [[ -z "${ENVIRONMENT}" || -z "${ARG2}" ]]; then
  usage
  exit 1
fi

case "${ENVIRONMENT}" in
  production)
    DEFAULT_ALIAS_TAG="production"
    FRONTEND_API_BASE_URL="/api/v1"
    ;;
  staging)
    DEFAULT_ALIAS_TAG="staging"
    FRONTEND_API_BASE_URL="/api/v1"
    ;;
  *)
    echo "Unsupported environment: ${ENVIRONMENT}" >&2
    exit 1
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -n "${ARG3}" && "${ARG3}" == *"/"* ]]; then
  BACKEND_REPO="${ARG2}"
  FRONTEND_REPO="${ARG3}"
  SHA_TAG="${4:-sha-$(git rev-parse --short=12 HEAD)}"
  ALIAS_TAG="${5:-${DEFAULT_ALIAS_TAG}}"
else
  REGISTRY_REPO="${ARG2}"
  BACKEND_REPO="${REGISTRY_REPO}/backend"
  FRONTEND_REPO="${REGISTRY_REPO}/frontend"
  SHA_TAG="${3:-sha-$(git rev-parse --short=12 HEAD)}"
  ALIAS_TAG="${4:-${DEFAULT_ALIAS_TAG}}"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required." >&2
  exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
  echo "docker buildx is required." >&2
  exit 1
fi

BACKEND_IMAGE_SHA="${BACKEND_REPO}:${SHA_TAG}"
BACKEND_IMAGE_ALIAS="${BACKEND_REPO}:${ALIAS_TAG}"
FRONTEND_IMAGE_SHA="${FRONTEND_REPO}:${SHA_TAG}"
FRONTEND_IMAGE_ALIAS="${FRONTEND_REPO}:${ALIAS_TAG}"

docker buildx build \
  --platform linux/amd64 \
  -f "${ROOT_DIR}/backend/Dockerfile" \
  -t "${BACKEND_IMAGE_SHA}" \
  -t "${BACKEND_IMAGE_ALIAS}" \
  --push \
  "${ROOT_DIR}/backend"

docker buildx build \
  --platform linux/amd64 \
  -f "${ROOT_DIR}/frontend/Dockerfile" \
  --build-arg "VITE_API_BASE_URL=${FRONTEND_API_BASE_URL}" \
  --build-arg "VITE_AUTH_LOGIN_ENDPOINT=/auth/login" \
  --build-arg "VITE_REQUEST_TIMEOUT_MS=15000" \
  --build-arg "VITE_APP_NAME=Yembro" \
  -t "${FRONTEND_IMAGE_SHA}" \
  -t "${FRONTEND_IMAGE_ALIAS}" \
  --push \
  "${ROOT_DIR}/frontend"

echo "Images pushed successfully."
echo "Backend:  ${BACKEND_IMAGE_SHA}"
echo "Frontend: ${FRONTEND_IMAGE_SHA}"
echo
echo "Deploy with:"
echo "BACKEND_IMAGE=${BACKEND_IMAGE_SHA} FRONTEND_IMAGE=${FRONTEND_IMAGE_SHA} EDGE_DIR=/opt/yembro/edge ./deploy/scripts/deploy.sh ${ENVIRONMENT}"
