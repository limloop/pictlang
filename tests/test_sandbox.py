"""Tests for pictlang.sandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from pictlang.sandbox import SandboxError, run_render


def _write(tmp_path: Path, code: str) -> Path:
    p = tmp_path / "gen.py"
    p.write_text(code, encoding="utf-8")
    return p


# ─────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────

def test_simple_render(tmp_path: Path):
    code = (
        "def render():\n"
        "    c = new_canvas(16, 16)\n"
        "    add(c, rect(0, 0, 16, 16, fill='#000000'))\n"
        "    return to_svg(c)\n"
    )
    p = _write(tmp_path, code)
    svg = run_render(p, timeout=10, mem_mb=256)
    assert svg.startswith("<svg")
    assert "rect" in svg


def test_dsl_is_available(tmp_path: Path):
    """The render code must see DSL functions without imports."""
    code = (
        "def render():\n"
        "    assert callable(new_canvas)\n"
        "    assert callable(circle)\n"
        "    assert callable(glow)\n"
        "    c = new_canvas(8, 8)\n"
        "    add(c, circle(4, 4, 2, fill='#ffffff'))\n"
        "    return to_svg(c)\n"
    )
    p = _write(tmp_path, code)
    svg = run_render(p, timeout=10, mem_mb=256)
    assert "circle" in svg


# ─────────────────────────────────────────────────────────────
# Failures
# ─────────────────────────────────────────────────────────────

def test_missing_file():
    with pytest.raises(SandboxError, match="not found"):
        run_render(Path("/no/such/file.py"))


def test_invalid_structure_rejected_before_run(tmp_path: Path):
    p = _write(tmp_path, "x = 1\n")
    with pytest.raises(SandboxError, match="invalid code structure"):
        run_render(p, timeout=5)


def test_non_string_return(tmp_path: Path):
    code = "def render():\n    return 42\n"
    p = _write(tmp_path, code)
    with pytest.raises(SandboxError):
        run_render(p, timeout=5)


def test_render_raises(tmp_path: Path):
    code = "def render():\n    raise RuntimeError('boom')\n"
    p = _write(tmp_path, code)
    with pytest.raises(SandboxError, match="boom"):
        run_render(p, timeout=5)


def test_invalid_svg(tmp_path: Path):
    code = "def render():\n    return 'not svg'\n"
    p = _write(tmp_path, code)
    with pytest.raises(SandboxError, match="invalid SVG"):
        run_render(p, timeout=5)


def test_timeout(tmp_path: Path):
    code = "def render():\n    while True:\n        pass\n"
    p = _write(tmp_path, code)
    with pytest.raises(SandboxError, match="did not finish"):
        run_render(p, timeout=2, mem_mb=256)