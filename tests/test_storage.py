"""Tests for pictlang.storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pictlang import Config
from pictlang.storage import Storage, make_meta, utc_timestamp


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _storage(tmp_path: Path, save: str = "valid", **kwargs) -> Storage:
    cfg = Config(output_dir=tmp_path / "gen", save=save, **kwargs)
    cfg.api.api_key = "x"
    return Storage(cfg)


def _meta(uuid: str, status: str = "valid", reason: str | None = None):
    return make_meta(
        uuid=uuid, theme="t", style="s", model="m",
        status=status, reason=reason,
    )


# ─────────────────────────────────────────────────────────────
# UUID
# ─────────────────────────────────────────────────────────────

def test_new_uuid_is_unique(tmp_path: Path):
    st = _storage(tmp_path)
    st.ensure_dirs()
    seen = {st.new_uuid() for _ in range(20)}
    assert len(seen) == 20


def test_uuid_is_uuid4_format(tmp_path: Path):
    import uuid as u
    st = _storage(tmp_path)
    st.ensure_dirs()
    value = st.new_uuid()
    parsed = u.UUID(value)
    assert parsed.version == 4


# ─────────────────────────────────────────────────────────────
# Save valid
# ─────────────────────────────────────────────────────────────

def test_save_valid_all_files(tmp_path: Path):
    st = _storage(tmp_path, save="valid")
    st.ensure_dirs()
    u = st.new_uuid()

    files = st.save_valid(
        uuid=u,
        code="def render(): ...\n",
        svg="<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>",
        meta=_meta(u),
    )

    assert "py" in files and files["py"].exists()
    assert "svg" in files and files["svg"].exists()
    assert "meta" in files and files["meta"].exists()
    assert files["py"].name == f"{u}.py"
    assert files["svg"].name == f"{u}.svg"


def test_save_valid_py_only(tmp_path: Path):
    st = _storage(tmp_path, save="py")
    st.ensure_dirs()
    u = st.new_uuid()

    files = st.save_valid(
        uuid=u,
        code="def render(): ...\n",
        svg="<svg/>",
        meta=_meta(u),
    )
    assert "py" in files
    assert "svg" not in files
    assert "meta" not in files


def test_save_valid_svg_only(tmp_path: Path):
    st = _storage(tmp_path, save="svg")
    st.ensure_dirs()
    u = st.new_uuid()

    files = st.save_valid(
        uuid=u,
        code="def render(): ...\n",
        svg="<svg/>",
        meta=_meta(u),
    )
    assert "svg" in files
    assert "py" not in files
    assert "meta" not in files


def test_save_valid_keeps_original(tmp_path: Path):
    st = _storage(tmp_path, save="valid", keep_original=True)
    st.ensure_dirs()
    u = st.new_uuid()

    files = st.save_valid(
        uuid=u,
        code="def render(): ...\n",
        svg="<svg>optimized</svg>",
        meta=_meta(u),
        svg_original="<svg>original</svg>",
    )
    assert "svg_original" in files
    assert files["svg_original"].name == f"{u}.original.svg"
    assert "original" in files["svg_original"].read_text(encoding="utf-8")


def test_meta_has_sizes(tmp_path: Path):
    st = _storage(tmp_path, save="valid")
    st.ensure_dirs()
    u = st.new_uuid()
    meta = _meta(u)

    code = "def render(): ...\n"
    svg = "<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"

    files = st.save_valid(uuid=u, code=code, svg=svg, meta=meta)

    on_disk = json.loads(files["meta"].read_text(encoding="utf-8"))
    assert on_disk["bytes_py"] == len(code.encode("utf-8"))
    assert on_disk["bytes_svg"] == len(svg.encode("utf-8"))


# ─────────────────────────────────────────────────────────────
# Save invalid
# ─────────────────────────────────────────────────────────────

def test_save_invalid_ignored_in_valid_mode(tmp_path: Path):
    st = _storage(tmp_path, save="valid")
    st.ensure_dirs()
    u = st.new_uuid()

    files = st.save_invalid(uuid=u, code="x=1\n", meta=_meta(u, "invalid", "bad"))
    assert files == {}


def test_save_invalid_in_all_mode(tmp_path: Path):
    st = _storage(tmp_path, save="all")
    st.ensure_dirs()
    u = st.new_uuid()

    files = st.save_invalid(
        uuid=u, code="x=1\n",
        meta=_meta(u, status="invalid", reason="bad code"),
    )
    assert "py" in files and files["py"].exists()
    assert "meta" in files

    on_disk = json.loads(files["meta"].read_text(encoding="utf-8"))
    assert on_disk["status"] == "invalid"
    assert on_disk["reason"] == "bad code"


# ─────────────────────────────────────────────────────────────
# Manifest
# ─────────────────────────────────────────────────────────────

def test_manifest_created(tmp_path: Path):
    st = _storage(tmp_path, save="valid")
    st.ensure_dirs()
    u = st.new_uuid()
    st.save_valid(uuid=u, code="c", svg="<svg/>", meta=_meta(u))

    assert st.manifest_path.exists()
    lines = st.manifest_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["uuid"] == u
    assert record["status"] == "valid"


def test_manifest_appends(tmp_path: Path):
    st = _storage(tmp_path, save="valid")
    st.ensure_dirs()
    for _ in range(3):
        u = st.new_uuid()
        st.save_valid(uuid=u, code="c", svg="<svg/>", meta=_meta(u))

    lines = st.manifest_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────

def test_utc_timestamp_format():
    ts = utc_timestamp()
    assert ts.endswith("Z")
    assert "T" in ts