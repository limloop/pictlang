"""
OpenAI-compatible API client for pictlang.

Works with any endpoint compatible with the OpenAI API:
OpenAI, OpenRouter, LocalAI, Ollama, vLLM, Together, Groq, etc.

Features:
  - base_url, api_key, model, timeout, max_tokens, temperature
  - proxy: http://, https://, socks5://
  - reasoning: universal format via extra_body
  - retry with exponential backoff and Retry-After support
  - usage statistics
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

@dataclass
class APIConfig:
    """Settings for an OpenAI-compatible API endpoint."""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"

    # Request
    timeout: float = 120.0
    max_tokens: int = 8000
    temperature: float = 0.7

    # Proxy
    proxy: str | None = None

    # Reasoning
    enable_reasoning: bool = False
    # Format of the reasoning field in extra_body. "auto" picks by base_url.
    # "openai"     -> extra_body = {"reasoning_effort": "medium"}
    # "openrouter" -> extra_body = {"reasoning": {"enabled": True}}
    # "none"       -> nothing is sent
    reasoning_format: str = "auto"
    reasoning_effort: str = "medium"  # for the "openai" format

    # Retry
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0


# ─────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────

class APIError(Exception):
    """Base error for the client."""


class APIConnectionError(APIError):
    """Network error, timeout, DNS failure."""


class APIRateLimitError(APIError):
    """HTTP 429."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class APIAuthError(APIError):
    """HTTP 401 / 403."""


class APIResponseError(APIError):
    """Other API errors (5xx, 4xx except the above)."""


# ─────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────

class LLMClient:
    """
    Wrapper around the OpenAI SDK.

    Lazy initialization: the underlying client is created on the first
    request. This allows constructing LLMClient in tests without a key.
    """

    def __init__(self, config: APIConfig):
        self.config = config
        self._client = None

        # Statistics
        self.request_count = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_tokens_used = 0

    # ─── Client initialization ────────────────────────────────

    def _build_http_client(self):
        """Create an httpx.Client with proxy and timeout."""
        try:
            import httpx
        except ImportError as e:
            raise APIError(
                "Package httpx is required: pip install httpx"
            ) from e

        kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(self.config.timeout),
        }

        if self.config.proxy:
            kwargs["proxy"] = self.config.proxy

        return httpx.Client(**kwargs)

    def _make_client(self):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise APIError(
                "Package openai is required: pip install openai"
            ) from e

        if not self.config.api_key:
            raise APIAuthError("api_key is not set")

        http_client = self._build_http_client()

        return OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            max_retries=0,  # we do our own retry
            http_client=http_client,
        )

    @property
    def client(self):
        if self._client is None:
            self._client = self._make_client()
        return self._client

    # ─── Reasoning ────────────────────────────────────────────

    def _resolve_reasoning_format(self) -> str:
        """Determine the reasoning format from base_url if 'auto'."""
        fmt = self.config.reasoning_format
        if fmt != "auto":
            return fmt

        url = self.config.base_url.lower()
        if "openrouter" in url:
            return "openrouter"
        if "openai.com" in url:
            return "openai"
        # Unknown endpoint — do not risk sending anything
        return "none"

    def _build_reasoning_body(self) -> dict[str, Any]:
        """Build extra_body for reasoning. Empty dict if disabled."""
        if not self.config.enable_reasoning:
            return {}

        fmt = self._resolve_reasoning_format()

        if fmt == "openai":
            # OpenAI o-series: reasoning_effort
            return {"reasoning_effort": self.config.reasoning_effort}

        if fmt == "openrouter":
            # OpenRouter: {"reasoning": {"enabled": True}}
            return {"reasoning": {"enabled": True}}

        # "none" or unknown — send nothing
        return {}

    # ─── Main method ──────────────────────────────────────────

    def chat(self, system: str, user: str) -> str:
        """
        Single request to the model. Returns the response text.
        Retry with exponential backoff and Retry-After support.
        """
        self.request_count += 1
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                text = self._call_once(system, user)
                self.successful_requests += 1
                return text

            except APIAuthError:
                # No point retrying — bad key
                self.failed_requests += 1
                raise

            except (APIConnectionError, APIRateLimitError, APIResponseError) as e:
                last_error = e
                self.failed_requests += 1

                if attempt >= self.config.max_retries:
                    break

                delay = self._retry_delay(attempt, e)
                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.1fs",
                    attempt + 1, self.config.max_retries + 1, e, delay,
                )
                time.sleep(delay)

        raise APIError(
            f"Failed to get a response after "
            f"{self.config.max_retries + 1} attempts: {last_error}"
        )

    def _call_once(self, system: str, user: str) -> str:
        """Single call, no retry. Converts exceptions to our types."""
        import httpx
        import openai

        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        # Reasoning models (o1, o3, o4) do not accept temperature/max_tokens.
        # Detect by model prefix.
        model_lower = self.config.model.lower()
        is_reasoning_model = (
            model_lower.startswith("o1")
            or model_lower.startswith("o3")
            or model_lower.startswith("o4")
        )

        if is_reasoning_model:
            # max_completion_tokens instead of max_tokens
            if self.config.max_tokens:
                params["max_completion_tokens"] = self.config.max_tokens
        else:
            params["temperature"] = self.config.temperature
            if self.config.max_tokens:
                params["max_tokens"] = self.config.max_tokens

        extra = self._build_reasoning_body()
        if extra:
            params["extra_body"] = extra

        try:
            response = self.client.chat.completions.create(**params)

        except openai.AuthenticationError as e:
            raise APIAuthError(f"Authentication error: {e}") from e

        except openai.PermissionDeniedError as e:
            raise APIAuthError(f"Permission denied: {e}") from e

        except openai.RateLimitError as e:
            # Extract Retry-After from headers if present
            retry_after = None
            if hasattr(e, "response") and e.response is not None:
                raw = e.response.headers.get("retry-after")
                if raw:
                    try:
                        retry_after = float(raw)
                    except (TypeError, ValueError):
                        retry_after = None
            raise APIRateLimitError(
                f"Rate limit exceeded: {e}", retry_after=retry_after
            ) from e

        except openai.APITimeoutError as e:
            raise APIConnectionError(f"Request timeout: {e}") from e

        except openai.APIConnectionError as e:
            raise APIConnectionError(f"Connection error: {e}") from e

        except openai.APIStatusError as e:
            code = getattr(e, "status_code", "?")
            raise APIResponseError(f"HTTP {code}: {e}") from e

        except httpx.HTTPError as e:
            raise APIConnectionError(f"HTTP error: {e}") from e

        # Successful response
        if not response.choices:
            raise APIResponseError("Empty choices list in the response")

        content = response.choices[0].message.content
        if not content:
            raise APIResponseError("Empty content in the response")

        # Tokens
        if response.usage:
            self.total_tokens_used += response.usage.total_tokens

        return content

    # ─── Retry ────────────────────────────────────────────────

    def _retry_delay(self, attempt: int, error: Exception) -> float:
        """Exponential backoff + jitter. Honors Retry-After."""
        retry_after = getattr(error, "retry_after", None)
        if retry_after is not None:
            return min(float(retry_after), self.config.max_delay)

        delay = self.config.base_delay * (2 ** attempt)
        jitter = random.uniform(0.1, 0.3) * delay
        return min(delay + jitter, self.config.max_delay)

    # ─── Utilities ────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Check connectivity. True if models are reachable."""
        try:
            self.client.models.list()
            return True
        except Exception as e:
            logger.error("Connection error: %s", e)
            return False

    def get_usage_stats(self) -> dict[str, Any]:
        total = self.request_count
        rate = (self.successful_requests / total * 100) if total else 0.0
        return {
            "total_requests": total,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(rate, 1),
            "total_tokens_used": self.total_tokens_used,
        }

    # ─── Context manager ──────────────────────────────────────

    def close(self) -> None:
        if self._client is not None:
            try:
                # httpx.Client lives inside the OpenAI client
                http = getattr(self._client, "_client", None)
                if http is not None and hasattr(http, "close"):
                    http.close()
            except Exception as e:
                logger.debug("Error while closing client: %s", e)
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
