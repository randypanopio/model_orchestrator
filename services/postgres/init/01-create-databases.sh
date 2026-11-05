#!/usr/bin/env bash
set -Eeuo pipefail

: "${OPENWEBUI_DB_NAME:?OPENWEBUI_DB_NAME is required}"
: "${OPENWEBUI_DB_USER:?OPENWEBUI_DB_USER is required}"
: "${OPENWEBUI_DB_PASSWORD:?OPENWEBUI_DB_PASSWORD is required}"
: "${LITELLM_DB_NAME:?LITELLM_DB_NAME is required}"
: "${LITELLM_DB_USER:?LITELLM_DB_USER is required}"
: "${LITELLM_DB_PASSWORD:?LITELLM_DB_PASSWORD is required}"

psql \
  --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=openwebui_db_name="$OPENWEBUI_DB_NAME" \
  --set=openwebui_db_user="$OPENWEBUI_DB_USER" \
  --set=openwebui_db_password="$OPENWEBUI_DB_PASSWORD" \
  --set=litellm_db_name="$LITELLM_DB_NAME" \
  --set=litellm_db_user="$LITELLM_DB_USER" \
  --set=litellm_db_password="$LITELLM_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'openwebui_db_user', :'openwebui_db_password') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'openwebui_db_name', :'openwebui_db_user') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'litellm_db_user', :'litellm_db_password') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'litellm_db_name', :'litellm_db_user') \gexec
SQL
