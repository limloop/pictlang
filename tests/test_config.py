"""Tests for pictlang.config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pictlang import Config
from pictlang.api import APIConfig
from pictlang.config import example_config


# ─────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────

def test_default_config():
    cfg = Config()
    assert cfg.api.base_url.startswith("http")
    assert cfg.save == "valid"
    assert cfg.optimize is False
    assert cfg.optimizer == "auto"
    assert cfg.render_timeout > 0
    assert cfg.render_mem_mb > 0


# ─────────────────────────────────────────────────────────────
# Save modes
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "save, py, svg, invalid, optimizer_runs",
    [
        ("valid", True,  True,  False, True),
        ("all",   True,  True,  True,  True),
        ("py",    True,  False, False, False),
        ("svg",   False, True,  False, True),
    ],
)
def test_save_modes(save, py, svg, invalid, optimizer_runs):
    cfg = Config(save=save, optimize=True)
    assert cfg.saves_py is py
    assert cfg.saves_svg is svg
    assert cfg.saves_invalid is invalid
    assert cfg.runs_optimizer is optimizer_runs


def test_optimizer_does_not_run_without_optimize_flag():
    cfg = Config(save="valid", optimize=False)
    assert cfg.runs_optimizer is False


# ─────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────

def test_validate_accepts_valid_config():
    cfg = Config()
    cfg.api.api_key = "x"
    cfg.validate()  # should not raise


def test_validate_rejects_bad_save_mode():
    cfg = Config(save="bogus")
    with pytest.raises(ValueError, match="save mode"):
        cfg.validate()


def test_validate_rejects_bad_optimizer():
    cfg = Config(optimizer="bogus")
    with pytest.raises(ValueError, match="optimizer"):
        cfg.validate()


def test_validate_rejects_empty_base_url():
    cfg = Config()
    cfg.api.base_url = ""
    with pytest.raises(ValueError, match="base_url"):
        cfg.validate()


def test_validate_rejects_empty_model():
    cfg = Config()
    cfg.api.model = ""
    with pytest.raises(ValueError, match="model"):
        cfg.validate()


def test_validate_rejects_nonpositive_timeout():
    cfg = Config(render_timeout=0)
    with pytest.raises(ValueError, match="timeout"):
        cfg.validate()


# ─────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────

def test_load_explicit_path(tmp_path: Path):
    cfg_file = tmp_path / "pictlang.json"
    cfg_file.write_text(
        json.dumps({
            "api": {"api_key": "from-file", "model": "m1"},
            "save": "py",
        }),
        encoding="utf-8",
    )
    cfg = Config.load(cfg_file)
    assert cfg.api.api_key == "from-file"
    assert cfg.api.model == "m1"
    assert cfg.save == "py"


def test_load_missing_explicit_path_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Config.load(tmp_path / "does-not-exist.json")


def test_load_invalid_json(tmp_path: Path):
    cfg_file = tmp_path / "bad.json"
    cfg_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        Config.load(cfg_file)


def test_load_defaults_when_no_file(monkeypatch, tmp_path: Path):
    # Point CWD to a temp dir with no config and chdir there
    monkeypatch.chdir(tmp_path)
    cfg = Config.load()
    assert cfg.save == "valid"


# ─────────────────────────────────────────────────────────────
# Overrides
# ─────────────────────────────────────────────────────────────

def test_apply_overrides_api():
    cfg = Config()
    cfg.apply_overrides({
        "api.model": "new-model",
        "api.temperature": 0.5,
    })
    assert cfg.api.model == "new-model"
    assert cfg.api.temperature == 0.5


def test_apply_overrides_top_level():
    cfg = Config()
    cfg.apply_overrides({
        "save": "all",
        "optimize": True,
    })
    assert cfg.save == "all"
    assert cfg.optimize is True


def test_apply_overrides_skips_none():
    cfg = Config()
    cfg.api.model = "original"
    cfg.apply_overrides({"api.model": None})
    assert cfg.api.model == "original"


def test_apply_overrides_unknown_key():
    cfg = Config()
    with pytest.raises(ValueError, match="Unknown config field"):
        cfg.apply_overrides({"bogus": 1})


def test_apply_overrides_unknown_api_key():
    cfg = Config()
    with pytest.raises(ValueError, match="Unknown API field"):
        cfg.apply_overrides({"api.bogus": 1})


# ─────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────

def test_example_config_is_serializable():
    example = example_config()
    text = json.dumps(example)
    assert "api" in example
    assert "save" in example


def test_config_roundtrip():
    original = Config()
    original.api.api_key = "roundtrip"
    original.save = "all"
    original.optimize = True

    restored = Config._from_dict(original.to_dict())
    assert restored.api.api_key == "roundtrip"
    assert restored.save == "all"
    assert restored.optimize is True


def test_save_to_writes_json(tmp_path: Path):
    cfg = Config(output_dir=tmp_path)
    cfg.api.api_key = "to-write"
    target = tmp_path / "out.json"
    cfg.save_to(target)

    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["api"]["api_key"] == "to-write"
    assert data["output_dir"] == str(tmp_path)