# Open WebUI service configuration

Open WebUI runs as a pinned stock container. Its chat, session, user, and application
records are stored in its dedicated PostgreSQL database. Uploaded and generated media
remain in the persistent `openwebui_data` Docker volume. Both the database and this volume
must be included in backups.

The Postgres container creates separate databases and roles for Open WebUI and LiteLLM.
LiteLLM uses its own database and credentials; the services do not share tables.

Set persistent, random secrets in the repository-root `.env` file:

```bash
for key in WEBUI_SECRET_KEY POSTGRES_PASSWORD OPENWEBUI_DB_PASSWORD LITELLM_DB_PASSWORD; do
  if ! grep -q "^${key}=" .env || grep -q "^${key}=$" .env; then
    value="$(openssl rand -hex 32)"
    if grep -q "^${key}=" .env; then
      sed -i "s|^${key}=.*|${key}=${value}|" .env
    else
      printf '%s=%s\n' "$key" "$value" >> .env
    fi
  fi
done
```

Keep `.env` private and do not commit it. The first user created through the login page
becomes the administrator. After creating the account, disable public signups in Open
WebUI's admin settings before exposing the service beyond your local machine.

Start and verify the stack from the repository root:

```bash
./scripts/start_stack.sh
docker compose logs --tail=50 postgres openwebui caddy litellm
```

Open `http://localhost` for local HTTP, or use the domain configured in `DOMAIN`.

The existing local `openwebui_data` volume may still contain the old SQLite database. It
is not used when `DATABASE_URL` points to PostgreSQL; keep the volume because it also holds
uploads and generated media. Since the initial admin account is disposable, create a new
admin account after the PostgreSQL-backed UI starts.
