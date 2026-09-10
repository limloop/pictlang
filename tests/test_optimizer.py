"""Tests for pictlang.optimizer."""

from __future__ import annotations

import pytest

from pictlang.optimizer import (
    OptimizeResult,
    available_optimizers,
    optimize,
)


SIMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect x="0" y="0" width="10" height="10" fill="#000000"/>'
    "</svg>"
)


# ─────────────────────────────────────────────────────────────
# Never crashes
# ─────────────────────────────────────────────────────────────

def test_optimize_never_crashes_auto():
    result = optimize(SIMPLE_SVG, "auto")
    assert isinstance(result, OptimizeResult)
    assert result.svg.startswith("<svg")


def test_optimize_unknown_name_returns_original():
    result = optimize(SIMPLE_SVG, "bogus")
    assert result.optimizer is None
    assert result.svg == SIMPLE_SVG


def test_optimize_available_returns_list():
    names = available_optimizers()
    assert isinstance(names, list)
    for n in names:
        assert n in ("scour", "svgo")


# ─────────────────────────────────────────────────────────────
# Result fields
# ─────────────────────────────────────────────────────────────

def test_result_size_fields():
    result = optimize(SIMPLE_SVG, "auto")
    assert result.bytes_before == len(SIMPLE_SVG.encode("utf-8"))
    assert result.bytes_after == len(result.svg.encode("utf-8"))


def test_result_ratio_and_saved():
    r = OptimizeResult(svg="x", optimizer=None, bytes_before=100, bytes_after=40)
    assert r.ratio == 0.4
    assert r.saved == 60


def test_result_ratio_zero_before():
    r = OptimizeResult(svg="", optimizer=None, bytes_before=0, bytes_after=0)
    assert r.ratio == 1.0