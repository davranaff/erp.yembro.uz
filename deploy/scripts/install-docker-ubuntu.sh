#!/usr/bin/env bash

set -Eeuo pipefail

TARGET_USER="${1:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or through sudo." >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer supports apt-based systems only." >&2
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "Cannot detect distribution: /etc/os-release is missing." >&2
  exit 1
fi

. /etc/os-release

case "${ID:-}" in
  ubuntu|debian)
    DOCKER_DISTRO="${ID}"
    ;;
  *)
    echo "Unsupported distribution: ${ID:-unknown}. Supported: ubuntu, debian." >&2
    exit 1
    ;;
esac

apt-get update
apt-get install -y ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL "https://download.docker.com/linux/${DOCKER_DISTRO}/gpg" -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

ARCHITECTURE="$(dpkg --print-architecture)"
CODENAME="${VERSION_CODENAME:-}"

if [[ -z "${CODENAME}" ]]; then
  echo "Cannot detect VERSION_CODENAME from /etc/os-release." >&2
  exit 1
fi

cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${ARCHITECTURE} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${DOCKER_DISTRO} ${CODENAME} stable
EOF

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

if [[ -n "${TARGET_USER}" ]]; then
  if id "${TARGET_USER}" >/dev/null 2>&1; then
    groupadd -f docker
    usermod -aG docker "${TARGET_USER}"
    echo "Added ${TARGET_USER} to the docker group."
    echo "The user must log out and log back in before group membership takes effect."
  else
    echo "User ${TARGET_USER} does not exist. Skipping docker group assignment." >&2
  fi
fi

docker version
docker compose version

echo "Docker installation completed."

