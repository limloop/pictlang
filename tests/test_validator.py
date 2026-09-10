"""Tests for pictlang.validator."""

from __future__ import annotations

import pytest

from pictlang.validator import (
    ValidationError,
    check_code_structure,
    validate_svg,
)


# ─────────────────────────────────────────────────────────────
# Code structure
# ─────────────────────────────────────────────────────────────

def test_valid_minimal():
    check_code_structure("def render():\n    return '<svg/>'\n")


def test_valid_with_docstring():
    check_code_structure(
        '"""Module docstring."""\n'
        "def render():\n"
        "    return '<svg/>'\n"
    )


def test_rejects_toplevel_non_function():
    with pytest.raises(ValidationError, match="must be a function"):
        check_code_structure("x = 1\n")


def test_rejects_empty_source():
    with pytest.raises(ValidationError, match="exactly one"):
        check_code_structure("")


def test_rejects_two_functions():
    with pytest.raises(ValidationError):
        check_code_structure(
            "def render():\n    return '<svg/>'\n"
            "def helper():\n    return 1\n"
        )


def test_rejects_wrong_name():
    with pytest.raises(ValidationError, match="named 'render'"):
        check_code_structure("def draw():\n    return '<svg/>'\n")


def test_rejects_arguments():
    with pytest.raises(ValidationError, match="must not take"):
        check_code_structure("def render(x):\n    return '<svg/>'\n")


def test_rejects_toplevel_assignment():
    with pytest.raises(ValidationError):
        check_code_structure(
            "x = 1\n"
            "def render():\n    return '<svg/>'\n"
        )


def test_rejects_import_inside():
    with pytest.raises(ValidationError, match="imports are not allowed"):
        check_code_structure(
            "def render():\n"
            "    import math\n"
            "    return '<svg/>'\n"
        )


def test_rejects_import_at_top():
    with pytest.raises(ValidationError):
        check_code_structure(
            "import math\n"
            "def render():\n    return '<svg/>'\n"
        )


def test_rejects_syntax_error():
    with pytest.raises(ValidationError, match="syntax error"):
        check_code_structure("def render(:\n    pass\n")


# ─────────────────────────────────────────────────────────────
# SVG
# ─────────────────────────────────────────────────────────────

def test_valid_svg():
    validate_svg('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')


@pytest.mark.parametrize("bad", [
    "",
    "   ",
    "hello",
    "<html></html>",
    "<svg>",                                # unclosed
    '<svg xmlns="x"></svg>',                # no children
    "<svg><unclosed></svg>",                # malformed
])
def test_rejects_invalid_svg(bad):
    with pytest.raises(ValidationError):
        validate_svg(bad)


def test_rejects_non_string():
    with pytest.raises(ValidationError, match="must return str"):
        validate_svg(42)  # type: ignore[arg-type]


def test_rejects_too_large():
    big = '<svg xmlns="http://www.w3.org/2000/svg">' + \
          "<rect/>" * 100_000 + "</svg>"
    with pytest.raises(ValidationError, match="too large"):
        validate_svg(big, max_bytes=1000)