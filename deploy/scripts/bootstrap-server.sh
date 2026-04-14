#!/usr/bin/env bash

set -Eeuo pipefail

BASE_DIR="${1:-/opt/yembro}"

mkdir -p \
  "${BASE_DIR}/prod" \
  "${BASE_DIR}/prod/deploy" \
  "${BASE_DIR}/staging" \
  "${BASE_DIR}/staging/deploy" \
  "${BASE_DIR}/edge" \
  "${BASE_DIR}/edge/deploy/caddy" \
  "${BASE_DIR}/registry" \
  "${BASE_DIR}/registry/auth" \
  "${BASE_DIR}/registry/data" \
  "${BASE_DIR}/backups/prod" \
  "${BASE_DIR}/backups/staging"

echo "Server directories prepared under ${BASE_DIR}"
echo "Next:"
echo "  1. Copy .env.prod.example to ${BASE_DIR}/prod/.env and fill secrets"
echo "  2. Copy .env.staging.example to ${BASE_DIR}/staging/.env and fill secrets"
echo "  3. Copy .env.edge.example to ${BASE_DIR}/edge/.env and fill domains"
echo "  4. Sync compose files and deploy scripts into each directory"
