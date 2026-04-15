#!/usr/bin/env bash

set -Eeuo pipefail

TARGET="${1:?Usage: merge-env.sh <user@host> [all|prod|production|staging|edge] [ssh_port] [server_root]}"
TARGET_ENVIRONMENT="${2:-all}"
SSH_PORT="${3:-22}"
SERVER_ROOT="${4:-/opt/yembro}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_SOURCE_DIR="${ROOT_DIR}/.envs"
SSH_CMD=(ssh -p "${SSH_PORT}")
RSYNC_SSH="ssh -p ${SSH_PORT}"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") <user@host> [all|prod|production|staging|edge] [ssh_port] [server_root]

Examples:
  $(basename "$0") deploy@203.0.113.10
  $(basename "$0") deploy@203.0.113.10 staging
  $(basename "$0") deploy@203.0.113.10 edge 2222 /opt/yembro
EOF
}

normalize_environment() {
  case "$1" in
    "" | all)
      printf '%s\n' "all"
      ;;
    prod | production)
      printf '%s\n' "prod"
      ;;
    staging)
      printf '%s\n' "staging"
      ;;
    edge)
      printf '%s\n' "edge"
      ;;
    *)
      echo "Unsupported environment: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
}

resolve_source_file() {
  case "$1" in
    prod)
      printf '%s\n' "${ENV_SOURCE_DIR}/.env.prod"
      ;;
    staging)
      printf '%s\n' "${ENV_SOURCE_DIR}/.env.staging"
      ;;
    edge)
      printf '%s\n' "${ENV_SOURCE_DIR}/.env.edge"
      ;;
    *)
      echo "Unknown source environment: $1" >&2
      exit 1
      ;;
  esac
}

resolve_remote_dir() {
  case "$1" in
    prod)
      printf '%s\n' "${SERVER_ROOT}/prod"
      ;;
    staging)
      printf '%s\n' "${SERVER_ROOT}/staging"
      ;;
    edge)
      printf '%s\n' "${SERVER_ROOT}/edge"
      ;;
    *)
      echo "Unknown remote environment: $1" >&2
      exit 1
      ;;
  esac
}

sync_env_file() {
  local environment="$1"
  local source_file
  local remote_dir
  local remote_file
  local backup_dir
  local tmp_file
  local timestamp
  local remote_owner_group

  source_file="$(resolve_source_file "${environment}")"
  remote_dir="$(resolve_remote_dir "${environment}")"
  remote_file="${remote_dir}/.env"
  backup_dir="${remote_dir}/.env-backups"
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  tmp_file="${remote_file}.incoming.${timestamp}.$$"

  if [[ ! -f "${source_file}" ]]; then
    echo "Missing source file: ${source_file}" >&2
    exit 1
  fi

  "${SSH_CMD[@]}" "${TARGET}" "mkdir -p '${remote_dir}' '${backup_dir}'"

  remote_owner_group="$("${SSH_CMD[@]}" "${TARGET}" "\
    if [ -f '${remote_file}' ]; then \
      stat -c '%u:%g' '${remote_file}'; \
    else \
      stat -c '%u:%g' '${remote_dir}'; \
    fi")"

  if "${SSH_CMD[@]}" "${TARGET}" "test -f '${remote_file}'"; then
    "${SSH_CMD[@]}" "${TARGET}" \
      "cp '${remote_file}' '${backup_dir}/.env.${timestamp}'"
  fi

  rsync -az --no-owner --no-group -e "${RSYNC_SSH}" \
    "${source_file}" \
    "${TARGET}:${tmp_file}"

  "${SSH_CMD[@]}" "${TARGET}" "\
    mv '${tmp_file}' '${remote_file}' && \
    chmod 600 '${remote_file}' && \
    if [ \"\$(id -u)\" = '0' ]; then chown '${remote_owner_group}' '${remote_file}'; fi"

  echo "Synced ${source_file} -> ${TARGET}:${remote_file}"
}

normalized_environment="$(normalize_environment "${TARGET_ENVIRONMENT}")"

case "${normalized_environment}" in
  all)
    for environment in prod staging edge; do
      sync_env_file "${environment}"
    done
    ;;
  prod | staging | edge)
    sync_env_file "${normalized_environment}"
    ;;
esac

echo "Environment sync complete for ${TARGET}"
