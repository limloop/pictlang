"""Tests for pictlang.pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from pictlang import Config
from pictlang.api import APIError
from pictlang.pipeline import generate, _strip_code_fences


# ─────────────────────────────────────────────────────────────
# Code fence cleanup
# ─────────────────────────────────────────────────────────────

def test_strip_python_fence():
    text = "```python\ndef render():\n    pass\n```"
    assert _strip_code_fences(text) == "def render():\n    pass"


def test_strip_py_fence():
    text = "```py\ndef render():\n    pass\n```"
    assert _strip_code_fences(text) == "def render():\n    pass"


def test_strip_bare_fence():
    text = "```\ndef render():\n    pass\n```"
    assert _strip_code_fences(text) == "def render():\n    pass"


def test_no_fence_returns_input_stripped():
    text = "\n\ndef render():\n    pass\n\n"
    assert _strip_code_fences(text) == "def render():\n    pass"


# ─────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────

def test_generate_valid(tmp_path: Path, mock_client):
    code = (
        "def render():\n"
        "    c = new_canvas(16, 16)\n"
        "    add(c, rect(0, 0, 16, 16, fill='#000000'))\n"
        "    return to_svg(c)\n"
    )
    client = mock_client(response=f"```python\n{code}```")

    cfg = Config(output_dir=tmp_path / "gen", save="valid")
    cfg.api.api_key = "x"

    result = generate("a cat", "flat", cfg, client=client)

    assert result.ok
    assert result.status == "valid"
    assert result.theme == "a cat"
    assert result.style == "flat"
    assert result.uuid
    assert result.svg and result.svg.startswith("<svg")
    assert "py" in result.files
    assert "svg" in result.files
    assert "meta" in result.files


def test_generate_saves_files_on_disk(tmp_path: Path, mock_client):
    code = (
        "def render():\n"
        "    c = new_canvas(8, 8)\n"
        "    add(c, rect(0, 0, 8, 8, fill='#ffffff'))\n"
        "    return to_svg(c)\n"
    )
    cfg = Config(output_dir=tmp_path / "gen", save="valid")
    cfg.api.api_key = "x"

    result = generate("t", "s", cfg, client=mock_client(response=code))

    assert result.files["py"].exists()
    assert result.files["svg"].exists()


# ─────────────────────────────────────────────────────────────
# Failures
# ─────────────────────────────────────────────────────────────

def test_generate_invalid_svg(tmp_path: Path, mock_client):
    code = "def render():\n    return 'not svg'\n"
    cfg = Config(output_dir=tmp_path / "gen", save="valid")
    cfg.api.api_key = "x"

    result = generate("t", "s", cfg, client=mock_client(response=code))

    assert result.status == "invalid"
    assert result.reason
    assert "render" in result.reason
    assert "svg" not in result.files


def test_generate_bad_structure(tmp_path: Path, mock_client):
    code = "x = 1\n"  # no render at all
    cfg = Config(output_dir=tmp_path / "gen", save="valid")
    cfg.api.api_key = "x"

    result = generate("t", "s", cfg, client=mock_client(response=code))

    assert result.status == "invalid"
    assert "invalid code structure" in result.reason or "render" in result.reason


def test_generate_api_error(tmp_path: Path, mock_client):
    client = mock_client(error=APIError("network down"))
    cfg = Config(output_dir=tmp_path / "gen", save="valid")
    cfg.api.api_key = "x"

    result = generate("t", "s", cfg, client=client)

    assert result.status == "invalid"
    assert "api" in result.reason
    assert "network down" in result.reason


def test_generate_keeps_invalid_in_all_mode(tmp_path: Path, mock_client):
    code = "def render():\n    return 'garbage'\n"
    cfg = Config(output_dir=tmp_path / "gen", save="all")
    cfg.api.api_key = "x"

    result = generate("t", "s", cfg, client=mock_client(response=code))

    assert result.status == "invalid"
    assert "py" in result.files
    assert result.files["py"].exists()


def test_generate_discards_invalid_in_valid_mode(tmp_path: Path, mock_client):
    code = "def render():\n    return 'garbage'\n"
    cfg = Config(output_dir=tmp_path / "gen", save="valid")
    cfg.api.api_key = "x"

    result = generate("t", "s", cfg, client=mock_client(response=code))

    assert result.status == "invalid"
    assert result.files == {}


# ─────────────────────────────────────────────────────────────
# Client ownership
# ─────────────────────────────────────────────────────────────

def test_injected_client_is_not_closed(tmp_path: Path, mock_client):
    code = (
        "def render():\n"
        "    c = new_canvas(4, 4)\n"
        "    add(c, rect(0, 0, 4, 4, fill='#000000'))\n"
        "    return to_svg(c)\n"
    )
    client = mock_client(response=code)
    cfg = Config(output_dir=tmp_path / "gen", save="valid")
    cfg.api.api_key = "x"

    generate("t", "s", cfg, client=client)
    assert client.closed is False