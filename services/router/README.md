# Router service

The Router is a stateless FastAPI service on the private Compose network. It exposes the
OpenAI-compatible `/v1/models` and `/v1/chat/completions` endpoints. For now, the `static`
strategy routes every `auto` request to the model alias configured by `static_model` in
[`config/models.yaml`](../../../config/models.yaml).

Open WebUI calls the Router at `http://router:8000/v1`; the Router forwards to LiteLLM at
`http://litellm:4000/v1`. Neither service publishes a host port. Open WebUI and the Router
authenticate to the next internal hop with `ROUTER_API_KEY` and `LITELLM_MASTER_KEY`.

Run focused checks from this directory with `uv sync --all-groups` followed by
`uv run pytest` and `uv run ruff check .`. The container uses Python 3.12.

After starting the stack with `./scripts/start_stack.sh`, run
`bash scripts/smoke_test_router.sh` to send a live prompt through the Router, LiteLLM, and the
configured provider.
