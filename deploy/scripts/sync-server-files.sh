#!/usr/bin/env bash

set -Eeuo pipefail

TARGET="${1:?Usage: sync-server-files.sh <user@host> [ssh_port] [server_root] }"
SSH_PORT="${2:-22}"
SERVER_ROOT="${3:-/opt/yembro}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SSH_CMD=(ssh -p "${SSH_PORT}")
RSYNC_SSH="ssh -p ${SSH_PORT}"

"${SSH_CMD[@]}" "${TARGET}" "mkdir -p \
  '${SERVER_ROOT}/prod/deploy' \
  '${SERVER_ROOT}/staging/deploy' \
  '${SERVER_ROOT}/edge/deploy/caddy' \
  '${SERVER_ROOT}/registry' \
  '${SERVER_ROOT}/registry/auth' \
  '${SERVER_ROOT}/registry/data' \
  '${SERVER_ROOT}/backups/prod' \
  '${SERVER_ROOT}/backups/staging'"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/compose.base.yml" \
  "${ROOT_DIR}/compose.prod.yml" \
  "${ROOT_DIR}/.env.prod.example" \
  "${TARGET}:${SERVER_ROOT}/prod/"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/compose.base.yml" \
  "${ROOT_DIR}/compose.staging.yml" \
  "${ROOT_DIR}/.env.staging.example" \
  "${TARGET}:${SERVER_ROOT}/staging/"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/deploy/" \
  "${TARGET}:${SERVER_ROOT}/prod/deploy/"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/deploy/" \
  "${TARGET}:${SERVER_ROOT}/staging/deploy/"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/compose.edge.yml" \
  "${ROOT_DIR}/.env.edge.example" \
  "${TARGET}:${SERVER_ROOT}/edge/"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/deploy/caddy/" \
  "${TARGET}:${SERVER_ROOT}/edge/deploy/caddy/"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/.env.registry.example" \
  "${TARGET}:${SERVER_ROOT}/registry/"

rsync -az -e "${RSYNC_SSH}" \
  "${ROOT_DIR}/deploy/registry/" \
  "${TARGET}:${SERVER_ROOT}/registry/"

"${SSH_CMD[@]}" "${TARGET}" "find '${SERVER_ROOT}' -type f -path '*/deploy/scripts/*.sh' -exec chmod +x {} +"

echo "Deployment assets synced to ${TARGET}:${SERVER_ROOT}"
echo "Next:"
echo "  1. Copy .env.prod.example to ${SERVER_ROOT}/prod/.env and fill secrets"
echo "  2. Copy .env.staging.example to ${SERVER_ROOT}/staging/.env if staging is needed"
echo "  3. Copy .env.edge.example to ${SERVER_ROOT}/edge/.env and fill domains"
echo "  4. Or run deploy/scripts/merge-env.sh ${TARGET} all ${SSH_PORT} ${SERVER_ROOT} to upload real .env files from .envs/"
