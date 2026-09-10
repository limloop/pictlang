"""Tests for pictlang.dsl."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from pictlang.dsl import (
    DSL_EXPORTS,
    add,
    blob,
    circle,
    grad_lin,
    grad_rad,
    group,
    new_canvas,
    path,
    polar,
    rect,
    smooth,
    star,
    to_svg,
)


# ─────────────────────────────────────────────────────────────
# Exports
# ─────────────────────────────────────────────────────────────

REQUIRED_EXPORTS = {
    # canvas
    "new_canvas", "add", "to_svg", "bg",
    # primitives
    "rect", "circle", "ellipse", "line", "polygon", "polyline",
    "path", "arc", "star", "ring", "grid", "text",
    # curves
    "smooth", "blob", "wave", "flame", "PathBuilder",
    # gradients
    "grad_lin", "grad_rad", "grad_conic", "pattern",
    # effects
    "shadow", "glow", "blur", "reflect", "vignette",
    # repeat
    "repeat", "radial_repeat", "scatter",
    # color
    "lighten", "darken", "mix", "hsl", "palette_lerp",
    # transforms
    "group", "transform", "rotate", "scale",
    "mirror_x", "mirror_y", "opacity", "clip",
    # palettes
    "PALETTE", "PALETTE_WARM", "PALETTE_COOL", "PALETTE_MONO",
    # utils
    "lerp", "polar", "math", "random",
}


def test_all_exports_present():
    missing = REQUIRED_EXPORTS - set(DSL_EXPORTS)
    assert not missing, f"missing DSL exports: {sorted(missing)}"


# ─────────────────────────────────────────────────────────────
# Canvas
# ─────────────────────────────────────────────────────────────

def test_empty_canvas():
    svg = to_svg(new_canvas(64, 64))
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert root.attrib["width"] == "64"
    assert root.attrib["height"] == "64"
    assert root.attrib["viewBox"] == "0 0 64 64"


def test_canvas_with_one_rect():
    c = new_canvas(10, 10)
    add(c, rect(0, 0, 10, 10, fill="#000000"))
    svg = to_svg(c)
    root = ET.fromstring(svg)
    children = list(root)
    assert len(children) == 1
    assert children[0].tag.endswith("rect")


# ─────────────────────────────────────────────────────────────
# Primitives return valid SVG
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("element_factory", [
    lambda: rect(1, 2, 3, 4, fill="#123456"),
    lambda: circle(5, 5, 3, fill="#abcdef"),
    lambda: path("M 0 0 L 10 10", stroke="#000000"),
    lambda: star(10, 10, 8, 4, 5, fill="#ff0000"),
    lambda: blob(20, 20, 10, fill="#00ff00", seed=1),
])
def test_element_serializes(element_factory):
    c = new_canvas(64, 64)
    add(c, element_factory())
    svg = to_svg(c)
    ET.fromstring(svg)  # must be valid XML


# ─────────────────────────────────────────────────────────────
# Gradients
# ─────────────────────────────────────────────────────────────

def test_linear_gradient_added_to_defs():
    c = new_canvas(32, 32)
    g = grad_lin([(0, "#000000"), (1, "#ffffff")])
    add(c, g)
    svg = to_svg(c)
    assert "linearGradient" in svg
    assert g.id in svg


def test_radial_gradient_added_to_defs():
    c = new_canvas(32, 32)
    g = grad_rad([(0, "#000000"), (1, "#ffffff")])
    add(c, g)
    add(c, rect(0, 0, 32, 32, fill=g))
    svg = to_svg(c)
    assert "radialGradient" in svg


# ─────────────────────────────────────────────────────────────
# Curves
# ─────────────────────────────────────────────────────────────

def test_smooth_produces_cubic_path():
    d = smooth([(0, 0), (10, 5), (20, 0)])
    assert d.startswith("M")
    assert "C" in d


def test_smooth_closed_ends_with_z():
    d = smooth([(0, 0), (10, 0), (10, 10), (0, 10)], closed=True)
    assert d.rstrip().endswith("Z")


def test_smooth_with_too_few_points_is_empty():
    assert smooth([(0, 0)]) == ""
    assert smooth([]) == ""


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────

def test_polar():
    x, y = polar(0, 0, 10, 0)      # angle 0 → right
    assert pytest.approx(x, abs=1e-6) == 10
    assert pytest.approx(y, abs=1e-6) == 0

    x, y = polar(0, 0, 10, 90)     # 90° → down (SVG y-axis)
    assert pytest.approx(x, abs=1e-6) == 0
    assert pytest.approx(y, abs=1e-6) == 10


# ─────────────────────────────────────────────────────────────
# Groups & transforms
# ─────────────────────────────────────────────────────────────

def test_group_wraps_children():
    inner = rect(0, 0, 5, 5, fill="#000000")
    g = group([inner], translate=(10, 20))
    c = new_canvas(64, 64)
    add(c, g)
    svg = to_svg(c)
    root = ET.fromstring(svg)
    assert root[0].tag.endswith("g")
    assert "translate" in root[0].attrib.get("transform", "")