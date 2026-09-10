"""
Validation for pictlang.

Two checks:
  1. check_code_structure — AST-level check of the generated code.
  2. validate_svg        — structural check of the produced SVG.

Both raise ValidationError on failure.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET

# ─────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────

class ValidationError(Exception):
    """Raised when code or SVG fails validation."""


# ─────────────────────────────────────────────────────────────
# Code structure
# ─────────────────────────────────────────────────────────────

def check_code_structure(source: str) -> None:
    """
    Ensure the generated code is exactly one top-level def render().

    Allowed at the top level:
      - a single module docstring (optional)
      - exactly one def render()

    Not allowed:
      - imports
      - other function or class definitions
      - assignments
      - any executable code
    """
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as e:
        raise ValidationError(f"syntax error: {e}") from e

    top: list[ast.stmt] = []
    for node in tree.body:
        # Skip a module-level docstring
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        top.append(node)

    if len(top) != 1:
        kinds = ", ".join(type(n).__name__ for n in top) or "nothing"
        raise ValidationError(
            f"expected exactly one top-level def render(), found: {kinds}"
        )

    node = top[0]

    if not isinstance(node, ast.FunctionDef):
        raise ValidationError(
            f"top-level statement must be a function, got {type(node).__name__}"
        )

    if node.name != "render":
        raise ValidationError(
            f"top-level function must be named 'render', got '{node.name}'"
        )

    args = node.args
    if args.args or args.kwonlyargs or args.vararg or args.kwarg:
        raise ValidationError("render() must not take any arguments")

    # Defensive: reject any import anywhere in the tree.
    # The DSL is injected, so imports are never needed.
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Import, ast.ImportFrom)):
            raise ValidationError(
                "imports are not allowed inside render() "
                "(all DSL functions are already in scope)"
            )


# ─────────────────────────────────────────────────────────────
# SVG
# ─────────────────────────────────────────────────────────────

def validate_svg(svg: str, max_bytes: int = 500_000) -> None:
    """
    Ensure the string is a non-empty, well-formed SVG document.
    """
    if not isinstance(svg, str):
        raise ValidationError(f"render() must return str, got {type(svg).__name__}")

    if not svg.strip():
        raise ValidationError("render() returned an empty string")

    size = len(svg.encode("utf-8"))
    if size > max_bytes:
        raise ValidationError(
            f"SVG is too large: {size} > {max_bytes} bytes"
        )

    head = svg.lstrip()
    if not head.startswith("<svg"):
        raise ValidationError("output does not start with <svg")

    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        raise ValidationError(f"malformed XML: {e}") from e

    if not root.tag.endswith("svg"):
        raise ValidationError(f"root tag is not <svg>: {root.tag}")

    if len(list(root)) == 0:
        raise ValidationError("SVG has no child elements")
