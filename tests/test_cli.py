"""Tests for pictlang.cli."""

from __future__ import annotations

import json

import pytest
from pictlang.cli import main

# ─────────────────────────────────────────────────────────────
# --version
# ─────────────────────────────────────────────────────────────

def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "pictlang" in out


# ─────────────────────────────────────────────────────────────
# init
# ─────────────────────────────────────────────────────────────

def test_init_writes_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = main(["init"])
    assert rc == 0
    target = tmp_path / "pictlang.json"
    assert target.exists()

    data = json.loads(target.read_text(encoding="utf-8"))
    assert "api" in data


def test_init_refuses_overwrite(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pictlang.json").write_text("{}", encoding="utf-8")
    rc = main(["init"])
    assert rc == 1


def test_init_explicit_path(tmp_path, capsys):
    target = tmp_path / "my-config.json"
    rc = main(["init", "--path", str(target)])
    assert rc == 0
    assert target.exists()


# ─────────────────────────────────────────────────────────────
# Usage errors
# ─────────────────────────────────────────────────────────────

def test_missing_style(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pictlang.json").write_text(
        json.dumps({"api": {"api_key": "x", "model": "m"}}),
        encoding="utf-8",
    )
    rc = main(["a cat"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "--style" in err


def test_missing_theme(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pictlang.json").write_text(
        json.dumps({"api": {"api_key": "x", "model": "m"}}),
        encoding="utf-8",
    )
    rc = main(["--style", "flat"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "theme" in err


# ─────────────────────────────────────────────────────────────
# --check
# ─────────────────────────────────────────────────────────────

def test_check_valid_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pictlang.json").write_text(
        json.dumps({
            "api": {"api_key": "x", "model": "m",
                    "base_url": "https://example.invalid/v1"},
        }),
        encoding="utf-8",
    )
    # --check will fail on API connection, but config part must be printed.
    main(["--check"])
    out = capsys.readouterr().out
    assert "config:" in out
    assert "model:" in out
