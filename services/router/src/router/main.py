from __future__ import annotations

import hmac
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from router.config import RouterSettings
from router.strategy import StaticStrategy

logger = logging.getLogger("router")


def _log_decision(
    *,
    choice_model: str,
    choice_tier: str,
    reason: str,
    decision_latency_ms: float,
    upstream_latency_ms: float | None = None,
    status_code: int | None = None,
) -> None:
    record: dict[str, Any] = {
        "event": "model_route_decision",
        "model": choice_model,
        "tier": choice_tier,
        "reason": reason,
        "decision_latency_ms": round(decision_latency_ms, 3),
    }
    if upstream_latency_ms is not None:
        record["upstream_latency_ms"] = round(upstream_latency_ms, 3)
    if status_code is not None:
        record["upstream_status"] = status_code
    logger.info(json.dumps(record, separators=(",", ":")))


def _response_headers(response: httpx.Response) -> dict[str, str]:
    forwarded = ("content-type", "cache-control", "retry-after", "x-request-id", "content-encoding")
    return {name: response.headers[name] for name in forwarded if name in response.headers}


def create_app(
    settings: RouterSettings | None = None,
    *,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings or RouterSettings.from_env()
        app.state.strategy = StaticStrategy(
            app.state.settings.static_model,
            app.state.settings.model_tiers[app.state.settings.static_model],
        )
        app.state.upstream = httpx.AsyncClient(
            base_url=f"{app.state.settings.litellm_base_url}/",
            timeout=None,
            transport=upstream_transport,
        )
        try:
            yield
        finally:
            await app.state.upstream.aclose()

    app = FastAPI(title="Model Router", lifespan=lifespan)

    async def authenticate(request: Request) -> None:
        settings = request.app.state.settings
        authorization = request.headers.get("authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not hmac.compare_digest(token, settings.api_key)
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    async def readiness() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/v1/models")
    async def list_models(request: Request) -> dict[str, Any]:
        await authenticate(request)
        return {
            "object": "list",
            "data": [
                {
                    "id": "auto",
                    "object": "model",
                    "created": 0,
                    "owned_by": "router",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        await authenticate(request)
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")
        if not isinstance(payload.get("messages"), list):
            raise HTTPException(status_code=400, detail="Request must include a messages array")

        decision_started = time.perf_counter()
        choice = request.app.state.strategy.choose_model(payload)
        decision_latency_ms = (time.perf_counter() - decision_started) * 1000
        payload["model"] = choice.model
        user_id = request.headers.get("x-user-id")
        if user_id is not None:
            if len(user_id) > 256:
                raise HTTPException(status_code=400, detail="x-user-id is too long")
            payload["user"] = user_id

        upstream = request.app.state.upstream
        settings = request.app.state.settings
        upstream_request = upstream.build_request(
            "POST",
            "chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.litellm_master_key}",
                "Accept": request.headers.get("accept", "application/json"),
                "Content-Type": "application/json",
            },
        )
        upstream_started = time.perf_counter()
        try:
            upstream_response = await upstream.send(upstream_request, stream=True)
        except httpx.RequestError as exc:
            _log_decision(
                choice_model=choice.model,
                choice_tier=choice.tier,
                reason=choice.reason,
                decision_latency_ms=decision_latency_ms,
                upstream_latency_ms=(time.perf_counter() - upstream_started) * 1000,
                status_code=502,
            )
            raise HTTPException(
                status_code=502,
                detail="LiteLLM is unavailable",
            ) from exc

        _log_decision(
            choice_model=choice.model,
            choice_tier=choice.tier,
            reason=choice.reason,
            decision_latency_ms=decision_latency_ms,
            upstream_latency_ms=(time.perf_counter() - upstream_started) * 1000,
            status_code=upstream_response.status_code,
        )

        if payload.get("stream") is True:

            async def stream_response() -> AsyncIterator[bytes]:
                try:
                    async for chunk in upstream_response.aiter_raw():
                        yield chunk
                finally:
                    await upstream_response.aclose()

            return StreamingResponse(
                stream_response(),
                status_code=upstream_response.status_code,
                headers=_response_headers(upstream_response),
            )

        try:
            content = b"".join(
                [chunk async for chunk in upstream_response.aiter_raw()]
            )
            return Response(
                content=content,
                status_code=upstream_response.status_code,
                headers=_response_headers(upstream_response),
            )
        finally:
            await upstream_response.aclose()

    return app


app = create_app()
