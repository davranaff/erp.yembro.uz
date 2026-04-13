#!/usr/bin/env bash

set -Eeuo pipefail

ENVIRONMENT="${1:?Usage: rollback.sh <production|staging>}"
TARGET_DIR="${2:-$(pwd)}"

cd "${TARGET_DIR}"

if [[ ! -f .release.env.previous ]]; then
  echo "Missing previous release file: ${TARGET_DIR}/.release.env.previous" >&2
  exit 1
fi

set -a
source ./.release.env.previous
set +a

export BACKEND_IMAGE
export FRONTEND_IMAGE

RUN_MIGRATIONS=0 EDGE_DIR="${EDGE_DIR:-/opt/yembro/edge}" "$(dirname "$0")/deploy.sh" "${ENVIRONMENT}" "${TARGET_DIR}"
