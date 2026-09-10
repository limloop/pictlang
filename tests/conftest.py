"""
Shared pytest fixtures for pictlang tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pictlang import Config
from pictlang.api import APIConfig


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def api_config() -> APIConfig:
    """A valid APIConfig, no real key needed for most tests."""
    return APIConfig(
        base_url="https://example.invalid/v1",
        api_key="test-key",
        model="test-model",
    )


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """
    A Config pointing output to a temporary directory.

    Uses a fake api_key so Config.validate() passes.
    """
    cfg = Config(output_dir=tmp_path / "generated", save="valid")
    cfg.api.api_key = "test-key"
    cfg.api.model = "test-model"
    cfg.api.base_url = "https://example.invalid/v1"
    return cfg


# ─────────────────────────────────────────────────────────────
# Mock LLM client
# ─────────────────────────────────────────────────────────────

class MockLLMClient:
    """
    Duck-typed replacement for LLMClient.

    Returns a preset response, records calls, and can be told to
    raise an exception.
    """

    def __init__(self, response: str = "", error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return self.response

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def mock_client():
    """Factory fixture: mock_client(response) -> MockLLMClient."""
    def _make(response: str = "", error: Exception | None = None) -> MockLLMClient:
        return MockLLMClient(response=response, error=error)
    return _make


# ─────────────────────────────────────────────────────────────
# Sample code / SVG
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def simple_render_code() -> str:
    """A minimal but valid render() implementation."""
    return (
        "def render():\n"
        "    c = new_canvas(32, 32)\n"
        "    add(c, rect(0, 0, 32, 32, fill='#123456'))\n"
        "    return to_svg(c)\n"
    )


@pytest.fixture
def simple_svg() -> str:
    """A minimal valid SVG document."""
    return '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'