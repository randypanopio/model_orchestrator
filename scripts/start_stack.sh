#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI not found. Install Docker Desktop or Docker Engine first." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing .env in the project root. Copy .env.example to .env and configure it first." >&2
  exit 1
fi

docker compose version >/dev/null
echo "Validating Compose configuration..."
docker compose config --quiet

echo "Starting PostgreSQL and waiting for it to become healthy..."
docker compose up --detach --wait --wait-timeout 180 postgres

echo "Starting all configured services in dependency order..."
docker compose up --detach --wait --wait-timeout 180

echo "Stack is running:"
docker compose ps
