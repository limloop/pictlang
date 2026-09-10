"""
Configuration for pictlang.

Load priority (first match wins):
  1. Path passed explicitly to Config.load()
  2. ./pictlang.json
  3. ~/.pictlang/config.json
  4. Built-in defaults

The config is a plain JSON file. API settings live under the "api" key
and map to APIConfig. Everything else maps to Config fields.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

from .api import APIConfig

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Paths (cross-platform)
# ─────────────────────────────────────────────────────────────

# The "appauthor" argument is only used on Windows.
APP_NAME = "pictlang"
APP_AUTHOR = "limloop"

# Platform-specific config directory:
#   Linux:   ~/.config/pictlang
#   macOS:   ~/Library/Application Support/pictlang
#   Windows: %APPDATA%\limloop\pictlang
USER_CONFIG_DIR = Path(user_config_dir(APP_NAME, APP_AUTHOR))
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.json"

# Project-local config (looked up first).
DEFAULT_CONFIG_NAME = "pictlang.json"

DEFAULT_OUTPUT_DIR = Path("generated")
DEFAULT_PROMPT_FILE = "prompts/default.md"


# ─────────────────────────────────────────────────────────────
# Save modes
# ─────────────────────────────────────────────────────────────

SAVE_MODES = ("valid", "all", "py", "svg")
DEFAULT_SAVE_MODE = "valid"


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

@dataclass
class Config:
    """Top-level configuration for pictlang."""

    # ── API ───────────────────────────────────────────────────
    api: APIConfig = field(default_factory=APIConfig)

    # ── Prompt ────────────────────────────────────────────────
    # Path to the prompt template. Relative paths are resolved
    # against the package directory first, then CWD.
    prompt_file: str | None = None

    # ── Output ────────────────────────────────────────────────
    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)

    # What to persist after a run:
    #   "valid" — only valid .py + .svg + .json (default)
    #   "all"   — valid and invalid, including debug info
    #   "py"    — only .py files (no SVG, no optimization)
    #   "svg"   — only .svg files (no .py)
    save: str = DEFAULT_SAVE_MODE

    # Keep the pre-optimization SVG as <uuid>.original.svg.
    # Ignored in "py" mode (nothing is saved).
    keep_original: bool = False

    # ── Optimization ──────────────────────────────────────────
    # Optimization runs only in modes where SVG is saved:
    # "valid", "all", "svg". Ignored in "py" mode.
    optimize: bool = False
    optimizer: str = "auto"  # "auto" | "scour" | "svgo"

    # ── Sandbox ───────────────────────────────────────────────
    # Wall-clock timeout for render() in seconds.
    render_timeout: int = 10
    # Memory limit for the render subprocess, in megabytes.
    render_mem_mb: int = 512

    # ── Misc ──────────────────────────────────────────────────
    # Overwrite existing files if a UUID collision occurs.
    # Practically never happens, but keep the knob here.
    overwrite_on_collision: bool = False

    verbose: bool = False

    # ─── Validation ───────────────────────────────────────────

    def validate(self) -> None:
        """Sanity-check the configuration. Raises ValueError on problems."""
        if self.save not in SAVE_MODES:
            raise ValueError(
                f"Invalid save mode: {self.save!r}. "
                f"Expected one of: {', '.join(SAVE_MODES)}"
            )

        if self.optimizer not in ("auto", "scour", "svgo"):
            raise ValueError(
                f"Invalid optimizer: {self.optimizer!r}. "
                f"Expected: auto, scour, svgo"
            )

        if self.render_timeout <= 0:
            raise ValueError("render_timeout must be positive")

        if self.render_mem_mb <= 0:
            raise ValueError("render_mem_mb must be positive")

        if not self.api.api_key:
            logger.warning("api.api_key is empty — requests will fail")

        if not self.api.base_url:
            raise ValueError("api.base_url must not be empty")

        if not self.api.model:
            raise ValueError("api.model must not be empty")

    # ─── Derived properties ───────────────────────────────────

    @property
    def saves_py(self) -> bool:
        """Whether .py files should be persisted."""
        return self.save in ("valid", "all", "py")

    @property
    def saves_svg(self) -> bool:
        """Whether .svg files should be persisted."""
        return self.save in ("valid", "all", "svg")

    @property
    def saves_invalid(self) -> bool:
        """Whether invalid results should be kept."""
        return self.save == "all"

    @property
    def runs_optimizer(self) -> bool:
        """Whether the optimizer should run at all."""
        return self.optimize and self.saves_svg

    # ─── Loading ──────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """
        Load configuration.

        Order:
          1. explicit path (raises if missing)
          2. ./pictlang.json
          3. ~/.pictlang/config.json
          4. defaults
        """
        candidates: list[Path | None] = [path]

        if path is None:
            candidates.append(Path.cwd() / DEFAULT_CONFIG_NAME)
            candidates.append(USER_CONFIG_PATH)

        for candidate in candidates:
            if candidate is None:
                continue
            if candidate.exists():
                logger.debug("Loading config from %s", candidate)
                return cls._from_file(candidate)

        if path is not None:
            raise FileNotFoundError(f"Config file not found: {path}")

        logger.debug("No config file found, using defaults")
        return cls()

    @classmethod
    def _from_file(cls, path: Path) -> Config:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e

        return cls._from_dict(raw, base_dir=path.parent)

    @classmethod
    def _from_dict(cls, data: dict[str, Any], base_dir: Path | None = None) -> Config:
        """Build a Config from a dict, mapping known fields only."""
        data = dict(data)

        # API subobject
        api_raw = data.pop("api", {}) or {}
        api = _build_dataclass(APIConfig, api_raw)

        # Remaining top-level fields
        cfg = _build_dataclass(cls, data)

        # Resolve relative paths against the config file's directory
        if base_dir is not None and "output_dir" in data:
            out = Path(cfg.output_dir)
            if not out.is_absolute():
                cfg.output_dir = (base_dir / out).resolve()

        if base_dir is not None and cfg.prompt_file:
            pf = Path(cfg.prompt_file)
            if not pf.is_absolute():
                cfg.prompt_file = str((base_dir / pf).resolve())

        cfg.api = api
        return cfg

    # ─── Saving ───────────────────────────────────────────────

    def save_to(self, path: Path) -> None:
        """Write the current configuration to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.debug("Config saved to %s", path)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        result = asdict(self)

        # Path -> str
        result["output_dir"] = str(self.output_dir)

        # api is already a dict from asdict(self)
        return result

    # ─── CLI overrides ────────────────────────────────────────

    def apply_overrides(self, overrides: dict[str, Any]) -> None:
        """
        Apply CLI overrides in place.

        Only keys present in the dataclass schema are accepted.
        Keys with value None are skipped (meaning "not provided").
        Nested API keys must use the "api." prefix, e.g. "api.model".
        """
        for key, value in overrides.items():
            if value is None:
                continue

            if key.startswith("api."):
                api_key = key[4:]
                if not hasattr(self.api, api_key):
                    raise ValueError(f"Unknown API field: {api_key}")
                setattr(self.api, api_key, value)
                continue

            if not hasattr(self, key):
                raise ValueError(f"Unknown config field: {key}")

            if key == "output_dir":
                value = Path(value)

            setattr(self, key, value)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _build_dataclass(cls, data: dict[str, Any]):
    """
    Construct a dataclass from a dict, ignoring unknown keys
    and converting Path-typed fields.
    """
    valid_names = {f.name for f in fields(cls)}
    kwargs: dict[str, Any] = {}

    for key, value in data.items():
        if key not in valid_names:
            logger.warning("Unknown config key: %s (ignored)", key)
            continue

        # Convert Path fields
        field_type = next(f.type for f in fields(cls) if f.name == key)
        if field_type in (Path, "Path") and value is not None:
            value = Path(value)

        kwargs[key] = value

    return cls(**kwargs)


# ─────────────────────────────────────────────────────────────
# Example config (for pictlang init)
# ─────────────────────────────────────────────────────────────

def example_config() -> dict[str, Any]:
    """Return a template configuration as a plain dict."""
    return {
        "api": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-...",
            "model": "gpt-4o-mini",
            "timeout": 120.0,
            "max_tokens": 8000,
            "temperature": 0.7,
            "proxy": None,
            "enable_reasoning": False,
            "reasoning_format": "auto",
            "reasoning_effort": "medium",
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 30.0,
        },
        "prompt_file": None,
        "output_dir": "generated",
        "save": "valid",
        "keep_original": False,
        "optimize": False,
        "optimizer": "auto",
        "render_timeout": 10,
        "render_mem_mb": 512,
        "overwrite_on_collision": False,
        "verbose": False,
    }
