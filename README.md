# Self-Hosted Multi-LLM Chat Orchestrator

The local frontend runs Open WebUI behind Caddy, with PostgreSQL for structured data and
LiteLLM as the private model gateway.
See [AGENTS.md](./AGENTS.md) for project goals, stack, architecture, and build order, and
[services/openwebui/README.md](./services/openwebui/README.md) for local setup instructions.

Start all services currently defined in Compose, in dependency order, with:

```bash
./scripts/start_stack.sh
```

The script validates `.env` and the Compose configuration, starts PostgreSQL first and waits
for it to become healthy, then starts all configured services in Compose dependency order.
It waits for services to become healthy or running, then prints their status. It does not
remove containers or data volumes.

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
