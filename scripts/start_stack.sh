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

database_mode="${1:-local}"
if [[ "$database_mode" != "local" && "$database_mode" != "external" ]]; then
  echo "Usage: $0 [local|external]" >&2
  exit 2
fi

docker compose version >/dev/null
compose=(docker compose)
if [[ "$database_mode" == "local" ]]; then
  compose+=(--profile local-db)
else
  compose+=(-f docker-compose.yml -f docker-compose.rds.yml)
  if [[ ! -s deploy/certs/rds-global-bundle.pem ]]; then
    echo "Missing deploy/certs/rds-global-bundle.pem. Install the current AWS RDS CA bundle before using external mode." >&2
    exit 1
  fi
fi

echo "Validating Compose configuration..."
"${compose[@]}" config --quiet

if [[ "$database_mode" == "local" ]]; then
  echo "Validating local PostgreSQL URLs..."
  "${compose[@]}" config --format json | python3 -c '
import json
import sys
from urllib.parse import urlparse

services = json.load(sys.stdin)["services"]
urls = [
    services["openwebui"]["environment"]["DATABASE_URL"],
    services["litellm"]["environment"]["DATABASE_URL"],
]
parsed_urls = [urlparse(url) for url in urls]
if any(url.hostname != "postgres" for url in parsed_urls):
    raise SystemExit("Local mode requires both database URL variables to be empty in .env.")
if parsed_urls[0].path == parsed_urls[1].path:
    raise SystemExit("Open WebUI and LiteLLM must use separate databases.")
'
  echo "Starting local PostgreSQL and waiting for it to become healthy..."
  "${compose[@]}" up --detach --wait --wait-timeout 180 postgres
else
  echo "Validating external PostgreSQL URLs and TLS settings..."
  "${compose[@]}" config --format json | python3 -c '
import json
import sys
from urllib.parse import parse_qs, urlparse

config = json.load(sys.stdin)
services = config["services"]
urls = [
    services["openwebui"]["environment"]["DATABASE_URL"],
    services["litellm"]["environment"]["DATABASE_URL"],
]
parsed_urls = [urlparse(url) for url in urls]
if any(not url.hostname or url.hostname == "postgres" or not url.path.strip("/") for url in parsed_urls):
    raise SystemExit("Set both external database URLs to their RDS endpoints and database names.")
if parsed_urls[0].path == parsed_urls[1].path:
    raise SystemExit("Open WebUI and LiteLLM must use separate databases.")
for url in parsed_urls:
    query = parse_qs(url.query)
    if query.get("sslmode") != ["verify-full"]:
        raise SystemExit("Both RDS URLs must set sslmode=verify-full.")
    if query.get("sslrootcert") != ["/etc/ssl/certs/rds-global-bundle.pem"]:
        raise SystemExit("Both RDS URLs must use the mounted AWS RDS CA bundle.")
'
  docker compose --profile local-db stop postgres
  echo "Using external PostgreSQL; local PostgreSQL has been stopped but its volume is retained."
fi

echo "Starting all configured services in dependency order..."
"${compose[@]}" up --detach --wait --wait-timeout 180

echo "Stack is running:"
"${compose[@]}" ps
