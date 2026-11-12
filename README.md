# Self-Hosted Multi-LLM Chat Orchestrator

The local frontend runs Open WebUI behind Caddy, with PostgreSQL for structured data and
LiteLLM as the private model gateway.
See [AGENTS.md](./AGENTS.md) for project goals, stack, architecture, and build order, and
[services/openwebui/README.md](./services/openwebui/README.md) for local setup instructions.

Start all services currently defined in Compose, in dependency order, with:

```bash
./scripts/start_stack.sh
```

The script validates `.env` and the Compose configuration. By default, it starts the local
PostgreSQL container first and waits for it to become healthy, then starts the application
services. To use AWS RDS, configure both database URLs as below and run
`./scripts/start_stack.sh external`. This selects the RDS Compose override and does not start
the local PostgreSQL container. The script waits for services to become healthy or running,
then prints their status. It does not remove containers or data volumes.

### AWS RDS staging

For RDS:

1. Create a private RDS PostgreSQL instance and allow inbound port 5432 only from the EC2
   security group.
2. Create separate databases and least-privilege login roles for Open WebUI and LiteLLM.
3. Download the current AWS RDS CA bundle to
   `deploy/certs/rds-global-bundle.pem`. Do not commit this file.
4. Copy these examples into `.env`, replacing the endpoint and URL-encoded passwords:

   ```dotenv
   OPENWEBUI_DATABASE_URL=postgresql://openwebui:URL_ENCODED_PASSWORD@RDS_ENDPOINT:5432/openwebui?sslmode=verify-full&sslrootcert=/etc/ssl/certs/rds-global-bundle.pem
   LITELLM_DATABASE_URL=postgresql://litellm:URL_ENCODED_PASSWORD@RDS_ENDPOINT:5432/litellm?sslmode=verify-full&sslrootcert=/etc/ssl/certs/rds-global-bundle.pem
   ```

5. Run `./scripts/start_stack.sh external`. It checks that both services have distinct
   database names and verified TLS configured before starting them.

Use the RDS endpoint hostname (not an IP) so certificate hostname verification works. URL
encode special characters in passwords. The RDS Compose override mounts the CA bundle into
both database clients at the path used by the URLs.

The `services/postgres/init/01-create-databases.sh` script bootstraps only a fresh local
PostgreSQL container; it does not provision RDS. Match the PostgreSQL major version and
extensions to the local setup. Before switching an existing installation, back up both
databases, restore each into its corresponding RDS database, and verify both services before
retiring the local copy. Do not delete the local volume until the restore is confirmed.
External mode stops the local PostgreSQL container but retains its data volume.

### Open WebUI media storage

Open WebUI uploads and generated media currently live in the `openwebui_data` Docker volume.
There is no automatic expiration, so files remain until explicitly removed or the volume is
deleted. That volume survives container replacement and ordinary `docker compose down`, but
it is local to the Docker host and is lost if the volume or host storage is deleted or fails.
It is not a long-term, independently backed-up storage solution. Before relying on these
files, migrate them to durable object storage such as a private AWS S3 bucket using an
Open-WebUI-supported storage integration, and verify backup and restore. Back up the local
volume until migration and restore testing are complete.

LiteLLM is not published to a host port. Future Router requests will reach it at
`http://litellm:4000/v1` on the internal Docker network. Configured model aliases are
`gemini-free` and `claude`.

To try Gemini through Google AI Studio, create an API key at
[aistudio.google.com/api-keys](https://aistudio.google.com/api-keys), set `GEMINI_API_KEY`
in `.env`, then recreate the gateway:

```bash
docker compose up -d --force-recreate litellm
```

The configured Gemini model is `gemini-3.6-flash`, which currently has free-tier token
pricing through Google AI Studio, subject to quota and model availability. Google says
free-tier content may be used to improve its products, so do not send sensitive content
through this key. Check the [current pricing and terms](https://aistudio.google.com/docs/pricing)
before use; free access and limits can change.

To enable Claude later, set `ANTHROPIC_API_KEY` to an Anthropic Console API key (a Claude
web-app subscription or session token is not an API key) and recreate LiteLLM. Keep
`LITELLM_SALT_KEY` backed up and unchanged after storing credentials in LiteLLM.
