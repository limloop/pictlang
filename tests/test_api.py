"""
Tests for pictlang.api.

Uses httpx.MockTransport to intercept HTTP calls inside the OpenAI SDK.
No network access is required.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pictlang.api import (
    APIAuthError,
    APIConfig,
    APIConnectionError,
    APIError,
    APIRateLimitError,
    APIResponseError,
    LLMClient,
)

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _openai_response(
    content: str = "hello",
    *,
    total_tokens: int = 10,
    model: str = "test-model",
) -> dict[str, Any]:
    """Build a minimal OpenAI-compatible chat.completions response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 5,
            "completion_tokens": total_tokens - 5,
            "total_tokens": total_tokens,
        },
    }


def _error_response(status: int, message: str = "error",
                    headers: dict[str, str] | None = None) -> httpx.Response:
    """Build an OpenAI-style error response."""
    body = {
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": None,
            "param": None,
        }
    }
    return httpx.Response(
        status_code=status,
        headers=headers or {},
        json=body,
    )


class TransportRecorder:
    """
    A MockTransport handler that records every request and
    returns responses from a queue.
    """

    def __init__(self, responses: list[httpx.Response]):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.request_bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        try:
            self.request_bodies.append(json.loads(request.content))
        except (json.JSONDecodeError, ValueError):
            self.request_bodies.append({})

        if not self.responses:
            raise AssertionError("no more responses queued")
        return self.responses.pop(0)


def _make_client(
    config: APIConfig,
    responses: list[httpx.Response],
) -> tuple[LLMClient, TransportRecorder]:
    """
    Build an LLMClient whose HTTP layer goes through a recorder.
    Returns (client, recorder).
    """
    recorder = TransportRecorder(responses)

    def factory():
        from openai import OpenAI
        transport = httpx.MockTransport(recorder)
        http_client = httpx.Client(transport=transport, timeout=config.timeout)
        return OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=0,
            http_client=http_client,
        )

    client = LLMClient(config)
    client._client = factory()
    return client, recorder


@pytest.fixture
def config() -> APIConfig:
    return APIConfig(
        base_url="https://example.invalid/v1",
        api_key="test-key",
        model="test-model",
        timeout=5.0,
        max_tokens=1000,
        temperature=0.5,
        max_retries=2,
        base_delay=0.01,
        max_delay=0.05,
    )


def _fake_openai_response(choices, usage=None):
    """Build a fake object mimicking openai's ChatCompletion."""
    return SimpleNamespace(choices=choices, usage=usage)


def _fake_client(response_obj):
    """
    Build a fake client where .chat.completions.create(**kw)
    returns response_obj.
    """
    def create(**kwargs):
        return response_obj

    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create),
        ),
    )

# ─────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────

def test_chat_returns_content(config: APIConfig):
    client, _ = _make_client(config, [
        httpx.Response(200, json=_openai_response("hello world")),
    ])
    result = client.chat("system", "user")
    assert result == "hello world"


def test_chat_records_usage(config: APIConfig):
    client, _ = _make_client(config, [
        httpx.Response(200, json=_openai_response(total_tokens=42)),
    ])
    client.chat("s", "u")
    assert client.total_tokens_used == 42


def test_chat_stats(config: APIConfig):
    client, _ = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")
    client.chat("s", "u")
    stats = client.get_usage_stats()
    assert stats["total_requests"] == 2
    assert stats["successful_requests"] == 2
    assert stats["failed_requests"] == 0
    assert stats["success_rate"] == 100.0


# ─────────────────────────────────────────────────────────────
# Request body
# ─────────────────────────────────────────────────────────────

def test_request_sends_system_and_user(config: APIConfig):
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("SYS", "USR")

    body = rec.request_bodies[0]
    assert body["model"] == "test-model"
    messages = body["messages"]
    assert {"role": "system", "content": "SYS"} in messages
    assert {"role": "user", "content": "USR"} in messages


def test_request_sends_temperature_and_max_tokens(config: APIConfig):
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")

    body = rec.request_bodies[0]
    assert body["temperature"] == 0.5
    assert body["max_tokens"] == 1000


def test_reasoning_model_uses_max_completion_tokens(config: APIConfig):
    config.model = "o1-mini"
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")

    body = rec.request_bodies[0]
    assert "max_completion_tokens" in body
    assert "max_tokens" not in body
    assert "temperature" not in body


# ─────────────────────────────────────────────────────────────
# Reasoning extra_body
# ─────────────────────────────────────────────────────────────

def test_reasoning_disabled_sends_no_extra_body(config: APIConfig):
    config.enable_reasoning = False
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")
    assert "reasoning_effort" not in rec.request_bodies[0]
    assert "reasoning" not in rec.request_bodies[0]


def test_reasoning_openai_format(config: APIConfig):
    config.enable_reasoning = True
    config.reasoning_format = "openai"
    config.reasoning_effort = "high"
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")
    assert rec.request_bodies[0]["reasoning_effort"] == "high"


def test_reasoning_openrouter_format(config: APIConfig):
    config.enable_reasoning = True
    config.reasoning_format = "openrouter"
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")
    assert rec.request_bodies[0]["reasoning"] == {"enabled": True}


def test_reasoning_auto_detects_openai(config: APIConfig):
    config.enable_reasoning = True
    config.base_url = "https://api.openai.com/v1"
    config.reasoning_format = "auto"
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")
    assert "reasoning_effort" in rec.request_bodies[0]


def test_reasoning_auto_detects_openrouter(config: APIConfig):
    config.enable_reasoning = True
    config.base_url = "https://openrouter.ai/api/v1"
    config.reasoning_format = "auto"
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")
    assert rec.request_bodies[0].get("reasoning") == {"enabled": True}


def test_reasoning_auto_unknown_endpoint_sends_nothing(config: APIConfig):
    config.enable_reasoning = True
    config.base_url = "http://localhost:11434/v1"  # ollama
    config.reasoning_format = "auto"
    client, rec = _make_client(config, [
        httpx.Response(200, json=_openai_response()),
    ])
    client.chat("s", "u")
    assert "reasoning_effort" not in rec.request_bodies[0]
    assert "reasoning" not in rec.request_bodies[0]


# ─────────────────────────────────────────────────────────────
# Auth errors (no retry)
# ─────────────────────────────────────────────────────────────

def test_auth_error_401(config: APIConfig):
    client, rec = _make_client(config, [
        _error_response(401, "invalid key"),
    ])
    with pytest.raises(APIAuthError):
        client.chat("s", "u")
    assert len(rec.requests) == 1  # no retry


def test_auth_error_403(config: APIConfig):
    client, rec = _make_client(config, [
        _error_response(403, "forbidden"),
    ])
    with pytest.raises(APIAuthError):
        client.chat("s", "u")
    assert len(rec.requests) == 1


# ─────────────────────────────────────────────────────────────
# Rate limit (retry with Retry-After)
# ─────────────────────────────────────────────────────────────

def test_rate_limit_retries_then_succeeds(config: APIConfig):
    client, rec = _make_client(config, [
        _error_response(429, "slow down"),
        httpx.Response(200, json=_openai_response("ok")),
    ])
    result = client.chat("s", "u")
    assert result == "ok"
    assert len(rec.requests) == 2


def test_rate_limit_gives_up_after_max_retries(config: APIConfig):
    config.max_retries = 2
    client, rec = _make_client(config, [
        _error_response(429, "slow"),
        _error_response(429, "slow"),
        _error_response(429, "slow"),
    ])
    with pytest.raises(APIError):
        client.chat("s", "u")
    assert len(rec.requests) == 3  # initial + 2 retries


def test_retry_after_honored(config: APIConfig):
    """The Retry-After header value must be used as the delay."""
    config.max_retries = 1
    client, rec = _make_client(config, [
        _error_response(429, "slow", headers={"retry-after": "0"}),
        httpx.Response(200, json=_openai_response("ok")),
    ])
    result = client.chat("s", "u")
    assert result == "ok"


# ─────────────────────────────────────────────────────────────
# Server errors (retry)
# ─────────────────────────────────────────────────────────────

def test_500_retries_then_succeeds(config: APIConfig):
    client, rec = _make_client(config, [
        _error_response(500, "internal"),
        httpx.Response(200, json=_openai_response("ok")),
    ])
    result = client.chat("s", "u")
    assert result == "ok"
    assert len(rec.requests) == 2


def test_500_gives_up(config: APIConfig):
    config.max_retries = 1
    client, rec = _make_client(config, [
        _error_response(500, "internal"),
        _error_response(500, "internal"),
    ])
    with pytest.raises(APIError):
        client.chat("s", "u")
    assert len(rec.requests) == 2


# ─────────────────────────────────────────────────────────────
# Connection errors
# ─────────────────────────────────────────────────────────────

def test_connection_error_wrapped(config: APIConfig):
    def failing(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = LLMClient(config)
    from openai import OpenAI
    client._client = OpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout=config.timeout,
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(failing)),
    )

    with pytest.raises(APIError):
        client.chat("s", "u")


# ─────────────────────────────────────────────────────────────
# Response shape issues
# ─────────────────────────────────────────────────────────────

def test_empty_choices_raises(config: APIConfig):
    """Empty choices list is rejected by our code."""
    config.max_retries = 0
    client = LLMClient(config)
    client._client = _fake_client(_fake_openai_response(choices=[]))

    with pytest.raises(APIResponseError, match="choices"):
        client._call_once("system", "user")


def test_empty_content_raises(config: APIConfig):
    """Null content is rejected by our code."""
    config.max_retries = 0
    client = LLMClient(config)
    choice = SimpleNamespace(message=SimpleNamespace(content=None))
    client._client = _fake_client(_fake_openai_response(choices=[choice]))

    with pytest.raises(APIResponseError, match="content"):
        client._call_once("system", "user")


# ─────────────────────────────────────────────────────────────
# Config validation
# ─────────────────────────────────────────────────────────────

def test_missing_api_key_raises():
    config = APIConfig(api_key="")
    client = LLMClient(config)
    with pytest.raises(APIAuthError, match="api_key"):
        client.chat("s", "u")


# ─────────────────────────────────────────────────────────────
# close()
# ─────────────────────────────────────────────────────────────

def test_close_without_client_does_not_crash():
    client = LLMClient(APIConfig(api_key="x"))
    client.close()  # no-op, must not raise


def test_close_closes_http_client(config: APIConfig):
    client, _ = _make_client(config, [])
    # Force client creation
    _ = client.client
    client.close()
    assert client._client is None


def test_context_manager(config: APIConfig):
    with LLMClient(config) as c:
        assert c is not None
    # After exit, client must be closed
    assert c._client is None


# ─────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────

def test_stats_after_failure(config: APIConfig):
    config.max_retries = 0
    client, _ = _make_client(config, [
        _error_response(500, "boom"),
    ])
    with pytest.raises(APIError):
        client.chat("s", "u")

    stats = client.get_usage_stats()
    assert stats["total_requests"] == 1
    assert stats["failed_requests"] == 1
    assert stats["successful_requests"] == 0


# ─────────────────────────────────────────────────────────────
# Retry delay computation
# ─────────────────────────────────────────────────────────────

def test_retry_delay_uses_retry_after():
    client = LLMClient(APIConfig(api_key="x", max_delay=100))
    err = APIRateLimitError("slow", retry_after=7.5)
    delay = client._retry_delay(attempt=5, error=err)
    assert delay == 7.5


def test_retry_delay_capped_by_max_delay():
    client = LLMClient(APIConfig(api_key="x", max_delay=5.0))
    err = APIRateLimitError("slow", retry_after=999)
    delay = client._retry_delay(attempt=0, error=err)
    assert delay == 5.0


def test_retry_delay_without_retry_after():
    """Exponential backoff, capped by max_delay, positive."""
    cfg = APIConfig(api_key="x", base_delay=1.0, max_delay=10.0)
    client = LLMClient(cfg)
    err = APIConnectionError("net")
    for attempt in range(5):
        d = client._retry_delay(attempt, err)
        assert 0 < d <= 10.0
