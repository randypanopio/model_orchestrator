# Open WebUI service configuration

Open WebUI runs as a pinned stock container, stores its database and uploads in the
`openwebui_data` Docker volume, and is reachable through Caddy at `http://localhost`
when `DOMAIN=:80`.

Before starting the stack, set a persistent secret in the repository-root `.env` file:

```bash
printf 'WEBUI_SECRET_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
```

Keep `.env` private and do not commit it. The first user created through the login page
becomes the administrator. After creating the account, disable public signups in Open
WebUI's admin settings before exposing the service beyond your local machine.

Start and verify the frontend from the repository root:

```bash
docker compose up -d
docker compose ps
docker compose logs --tail=50 openwebui caddy
```

Open `http://localhost` for local HTTP, or use the domain configured in `DOMAIN`.

The initial local setup uses Open WebUI's default SQLite database. PostgreSQL integration
will be added as part of the full service stack.
