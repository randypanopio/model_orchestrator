# Project: Self-Hosted Multi-LLM Chat Orchestrator

You are helping build a self-hosted, ChatGPT/Claude-style chat web app that routes prompts
across multiple LLM providers to minimize cost while keeping quality high. It is accessed
from anywhere via a cloud deployment. Read this whole file before making changes.

## Goals

1. Polished chat UI with markdown, code, and sandboxed HTML rendering (not code-editor focused).
2. Dynamic model routing: cheap models for easy prompts, expensive ones only when needed.
3. Budget control: per-key / per-model spend limits, usage tracking, fallbacks.
4. Monorepo, one-command cloud deploy, but every component must be swappable.
5. Auth must be addable later without rewriting anything (see "Auth seam").

## Non-goals

- Do NOT build a custom chat UI from scratch. Extend/configure the existing one.
- Do NOT reimplement provider SDKs, budgets, or fallbacks. LiteLLM does that.
- No VS Code extension work. This is a web app.

## Chosen stack (use these; don't substitute without asking)

| Layer | Choice | Why |
|---|---|---|
| Chat UI | **Open WebUI** | Mature UI, markdown + HTML/artifact rendering, built-in users, Python plugin system |
| Gateway / budgets | **LiteLLM Proxy** | OpenAI-compatible, 100+ providers, spend tracking, budgets, fallbacks |
| Router | **Custom FastAPI service (Python)** | Small, ours, exposes a virtual model named `auto` |
| Database | **Postgres** | Used by LiteLLM (keys, spend) and Open WebUI |
| Cache / rate limits | **Redis** (optional, add when needed) | LiteLLM caching and rate limiting |
| Reverse proxy / TLS | **Caddy** | Automatic HTTPS, simple config, forward-auth support |
| Orchestration | **Docker Compose** | One file, one deploy script |

Language: **Python 3.12+** for all our own code (router, scripts, tests). Use `uv` for
dependency management and `ruff` + `pytest`. TypeScript only if a custom frontend is added later.

## Architecture

```
Browser --HTTPS--> Caddy --> Open WebUI --OpenAI API--> Router ("auto") --OpenAI API--> LiteLLM --> Providers
                                |                                                         |
                                +------------------ Postgres <----------------------------+
```

Every hop between our services speaks the **OpenAI-compatible Chat Completions API**
(`POST /v1/chat/completions`, `GET /v1/models`, SSE streaming). That is the swap contract:
any component can be replaced by anything that speaks it.

- Open WebUI is configured with ONE backend: the Router. It sees models `auto` plus
  optionally pass-through names.
- The Router picks a concrete model, rewrites the `model` field, and forwards to LiteLLM
  with streaming preserved end to end.
- LiteLLM owns provider keys, budgets, retries, and fallbacks. Provider keys live ONLY here.

## Data ownership and persistence

- PostgreSQL is the only relational database technology for the project. Self-host it under
  our control by default; changing the PostgreSQL host later is a configuration change, not
  a database-engine migration.
- Use one PostgreSQL server/cluster, with separate databases and credentials for Open WebUI
  and LiteLLM. Never share tables or let one service read or write another service's tables.
- Open WebUI owns chat/session history, user accounts, and its application metadata in its
  own PostgreSQL database. Do not rely on SQLite or Firebase for persistent application data.
- LiteLLM owns its keys, spend/usage records, and gateway metadata in its own PostgreSQL
  database.
- PostgreSQL stores structured data, not every file. Keep Open WebUI uploads and generated
  media in persistent storage we control (initially a Docker volume); back up that storage
  together with PostgreSQL. Do not assume a provider's temporary image URL is a durable copy.
- The `openwebui_data` Docker volume is host-local and not a long-term storage tier. Plan to
  move uploads and generated media to durable object storage (for example, a private AWS S3
  bucket) and verify backup/restore before depending on it for long-term retention.
- Configure Open WebUI and LiteLLM with separate database URLs so the same Compose stack can
  use local PostgreSQL or managed PostgreSQL such as AWS RDS. For managed databases, provision
  the two databases and credentials separately, keep the endpoint private, require verified
  TLS, and back up/restore each service database independently.
- Caddy state such as certificates also uses persistent storage. Document and back up every
  volume containing data needed to restore the deployment.
- Initially, LiteLLM may send requests to external model providers using their API credentials.
  Treat provider-side prompt retention as subject to each provider's policies. Later, connect
  self-hosted inference endpoints through LiteLLM so the Router and Open WebUI keep the same
  API path.

## Terminology (keep these distinct)

- **Caddy** = the reverse proxy / front door. HTTPS, path routing, later auth. Knows nothing about LLMs.
- **Router** = our FastAPI service that picks which LLM handles a prompt. Never exposed to the browser.
- **LiteLLM** = the gateway to providers (keys, budgets, fallbacks).
- The browser talks only to Caddy, which forwards only to Open WebUI. Open WebUI's backend
  (not the browser) calls the Router.
- Only the Router is custom code. Open WebUI, LiteLLM, Postgres, Caddy run as stock containers
  configured via files in this repo.

## Internal networking

- All services share one private Docker network and address each other by service name
  (e.g. `http://router:8000/v1`, `http://litellm:4000/v1`). Never hardcode IPs or localhost.
- Internal hops use plain HTTP; only Caddy terminates TLS. Service URLs come from env vars so
  switching to HTTPS or a private network (Tailscale/WireGuard) later is a config change.
- Router and LiteLLM each require a bearer key (`Authorization: Bearer ...`) from env.
- Streaming is SSE over HTTP. The Router must pass chunks through as they arrive, and the
  Caddy config must not buffer responses (use `flush_interval -1` on the reverse proxy to
  Open WebUI).
- WebSockets exist only between browser and Open WebUI (through Caddy); the Router never sees them.

## Router requirements

- Stateless FastAPI app, OpenAI-compatible, streaming pass-through (SSE), no buffering.
- Pluggable strategy interface: `choose_model(request) -> ModelChoice`. Ship these strategies,
  selectable via config:
  1. `rules`: heuristics (token length, contains code, keywords like "prove"/"step by step",
     attachments, explicit user override like `/model gpt-x`).
  2. `classifier`: a cheap model labels the prompt easy/medium/hard (cache by prompt hash).
  3. `static`: always one model (for debugging).
- Model tiers defined in `config/models.yaml` (cheap / balanced / premium, with aliases that
  map to LiteLLM model names). Never hardcode model names in code.
- Log every decision (chosen tier, reason, latency) as structured JSON.
- Escalation: if a cheap-tier response fails or the user regenerates, bump one tier up.
- Respect an `x-route-hint` header and per-conversation pinning.

## Monorepo layout

```
.
├── AGENTS.md
├── docker-compose.yml          # all services, env-driven
├── .env.example
├── deploy/
│   ├── deploy.sh               # single entry point: build + push + up on target host
│   └── caddy/Caddyfile
├── config/
│   ├── litellm.yaml            # providers, budgets, fallbacks
│   └── models.yaml             # router tiers and aliases
├── services/
│   ├── router/                 # our FastAPI app (src/, tests/, pyproject.toml)
│   └── openwebui/              # config/env overrides, custom Functions if any
├── scripts/                    # dev helpers (seed, smoke-test, cost report)
└── docs/
```

Each service is its own container with its own config. No cross-service imports.
Services communicate only over HTTP.

## Auth seam (build later, design for it now)

- Today: use Open WebUI's built-in login; enable it from day one, never expose the stack
  without it.
- Keep Caddy as the single public entry point. Auth must be addable as a Caddy
  `forward_auth` / OIDC layer (Authelia, Authentik, Cloudflare Access, or Tailscale) with no
  code changes in services.
- Router and LiteLLM are NOT publicly exposed; internal Docker network only. Router accepts
  a shared internal API key from env.
- Router should read an optional `x-user-id` header and pass it through to LiteLLM as the
  `user` field so per-user budgets work once real auth exists.

## Security rules

- Secrets only via env / `.env` (gitignored). Never commit keys. Keep `.env.example` current.
- Model-generated HTML renders only in sandboxed iframes (Open WebUI's default; do not weaken).
- Pin image versions in compose; no `latest` tags.
- Only Caddy publishes ports (80/443).

## Deploy

`deploy/deploy.sh` must be idempotent and work on a fresh Ubuntu VM: install Docker if
missing, sync repo, pull/build images, `docker compose up -d`, run smoke test. Parameterize
via env (`DEPLOY_HOST`, `DOMAIN`). Keep it POSIX-friendly bash with `set -euo pipefail`.

## Working agreements

- Work in small steps; after each, tell me how to run and verify it.
- Before adding a dependency or changing the stack table above, ask.
- Prefer config over code. Prefer deleting code over abstracting prematurely.
- Add a pytest for every router strategy and a smoke test that sends one prompt through
  the full chain.
- Check current docs for Open WebUI and LiteLLM config keys before writing them; these
  projects change quickly. Don't guess option names.

## Build order

1. `docker-compose.yml` with Postgres, LiteLLM, Open WebUI, Caddy; one provider working
   end to end through LiteLLM.
2. Router service with `static` strategy; point Open WebUI at it.
3. `rules` strategy + `models.yaml` tiers + decision logging.
4. `classifier` strategy and escalation.
5. Budgets and spend alerts in LiteLLM; a `scripts/cost_report.py`.
6. `deploy.sh` and cloud deployment.
7. Auth layer (separate task).
