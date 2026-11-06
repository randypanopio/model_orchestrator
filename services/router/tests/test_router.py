from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from router.config import RouterSettings
from router.main import create_app
from router.strategy import StaticStrategy


class ByteStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self.content

    async def aclose(self) -> None:
        return None


class RecordingTestClient(TestClient):
    upstream_requests: list[httpx.Request]


@pytest.fixture
def settings() -> RouterSettings:
    return RouterSettings(
        api_key="router-test-key",
        litellm_master_key="litellm-test-key",
        litellm_base_url="http://litellm:4000/v1",
        static_model="gemini-free",
        model_tiers={"gemini-free": "cheap", "claude": "premium"},
        strategy="static",
    )


@pytest.fixture
def client(
    settings: RouterSettings,
) -> Iterator[RecordingTestClient]:
    upstream_requests: list[httpx.Request] = []

    def upstream_handler(request: httpx.Request) -> httpx.Response:
        upstream_requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=ByteStream(
                json.dumps(
                    {
                        "choices": [
                            {"message": {"role": "assistant", "content": "test response"}}
                        ]
                    }
                ).encode(),
            ),
        )

    transport = httpx.MockTransport(upstream_handler)
    app = create_app(settings, upstream_transport=transport)
    with RecordingTestClient(app) as test_client:
        test_client.upstream_requests = upstream_requests
        yield test_client


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer router-test-key"}


def test_static_strategy_always_selects_configured_model() -> None:
    strategy = StaticStrategy(model="gemini-free", tier="cheap")

    first = strategy.choose_model({"model": "auto", "messages": []})
    second = strategy.choose_model({"model": "claude", "messages": [{"role": "user"}]})

    assert first == second
    assert first.model == "gemini-free"
    assert first.tier == "cheap"


def test_models_endpoint_requires_router_key(client: TestClient) -> None:
    response = client.get("/v1/models")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_models_endpoint_lists_auto(client: TestClient) -> None:
    response = client.get("/v1/models", headers=auth_headers())

    assert response.status_code == 200
    assert [model["id"] for model in response.json()["data"]] == ["auto"]


def test_chat_rewrites_model_and_authenticates_to_litellm(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers=auth_headers(),
        json={
            "model": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.2,
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "test response"
    upstream = client.upstream_requests[0]
    assert str(upstream.url) == "http://litellm:4000/v1/chat/completions"
    assert upstream.headers["authorization"] == "Bearer litellm-test-key"
    forwarded_body = json.loads(upstream.content)
    assert forwarded_body["model"] == "gemini-free"
    assert forwarded_body["temperature"] == 0.2


def test_user_id_is_forwarded_to_litellm(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers={**auth_headers(), "x-user-id": "user-123"},
        json={"model": "auto", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert json.loads(client.upstream_requests[0].content)["user"] == "user-123"


def test_streaming_response_is_passed_through(settings: RouterSettings) -> None:
    sse_body = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
    content_type = "text/event-stream"

    def upstream_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": content_type},
            stream=ByteStream(sse_body),
        )

    app = create_app(settings, upstream_transport=httpx.MockTransport(upstream_handler))
    with RecordingTestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers=auth_headers(),
            json={
                "model": "auto",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == content_type
    assert response.content == sse_body


def test_chat_rejects_non_object_request(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        headers={**auth_headers(), "content-type": "application/json"},
        content="[]",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Request body must be a JSON object"
