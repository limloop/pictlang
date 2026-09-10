"""
Persistence for pictlang.

Layout (under output_dir):

    generated/
    ├── valid/
    │   ├── py/
    │   │   └── <uuid>.py
    │   ├── svg/
    │   │   ├── <uuid>.svg
    │   │   └── <uuid>.original.svg      (if keep_original)
    │   └── meta/
    │       └── <uuid>.json
    ├── invalid/
    │   ├── <uuid>.py
    │   └── <uuid>.json
    └── manifest.jsonl

A single UUID ties together the .py, .svg and .json of one run.
The same UUID is printed to stdout so the user can find the files.

Save modes (Config.save):
    "valid" — valid .py + .svg + .json          (default)
    "all"   — valid and invalid, both saved
    "py"    — only valid .py
    "svg"   — only valid .svg
"""

from __future__ import annotations

import json
import logging
import uuid as uuid_mod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────

@dataclass
class Meta:
    """Metadata for a single run."""

    uuid: str
    theme: str
    style: str
    model: str
    timestamp: str
    status: str                    # "valid" | "invalid"
    reason: str | None = None

    # Sizes in bytes
    bytes_py: int | None = None
    bytes_svg: int | None = None
    bytes_svg_before_optimize: int | None = None

    # Optimizer
    optimizer: str | None = None

    # Durations in milliseconds
    duration_api_ms: int | None = None
    duration_render_ms: int | None = None
    duration_optimize_ms: int | None = None


# ─────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────

class Storage:
    """
    Handles all filesystem writes.

    Instantiate once per run with a Config. Call `new_uuid()` to
    get an ID, then `save_valid` / `save_invalid` to persist.
    """

    def __init__(self, config: Config):
        self.config = config
        self.root = Path(config.output_dir)

        self.valid_dir = self.root / "valid"
        self.valid_py_dir = self.valid_dir / "py"
        self.valid_svg_dir = self.valid_dir / "svg"
        self.valid_meta_dir = self.valid_dir / "meta"

        self.invalid_dir = self.root / "invalid"
        self.manifest_path = self.root / "manifest.jsonl"

    # ─── Lifecycle ────────────────────────────────────────────

    def ensure_dirs(self) -> None:
        """Create directories that will be used in this run."""
        self.root.mkdir(parents=True, exist_ok=True)

        if self.config.save in ("valid", "all", "py", "svg"):
            if self.config.saves_py or self.config.saves_svg:
                # Only create valid/ subdirs we actually need
                self.valid_dir.mkdir(exist_ok=True)

            if self.config.saves_py:
                self.valid_py_dir.mkdir(exist_ok=True)
            if self.config.saves_svg:
                self.valid_svg_dir.mkdir(exist_ok=True)
            if self.config.save in ("valid", "all"):
                self.valid_meta_dir.mkdir(exist_ok=True)

        if self.config.saves_invalid:
            self.invalid_dir.mkdir(exist_ok=True)

    # ─── UUID ─────────────────────────────────────────────────

    def new_uuid(self) -> str:
        """
        Generate a fresh UUID4 string.

        On the astronomically unlikely collision with an existing
        file, retries until a free one is found.
        """
        for _ in range(100):
            candidate = str(uuid_mod.uuid4())
            if not self._uuid_exists(candidate):
                return candidate
        raise RuntimeError("Could not generate a unique UUID")

    def _uuid_exists(self, u: str) -> bool:
        checks = [
            self.valid_py_dir / f"{u}.py",
            self.valid_svg_dir / f"{u}.svg",
            self.valid_meta_dir / f"{u}.json",
            self.invalid_dir / f"{u}.py",
        ]
        return any(p.exists() for p in checks)

    # ─── Saving valid ─────────────────────────────────────────

    def save_valid(
        self,
        *,
        uuid: str,
        code: str,
        svg: str,
        meta: Meta,
        svg_original: str | None = None,
    ) -> dict[str, Path]:
        """
        Persist a valid run. Returns a dict of what was written.

        Respects Config.save:
          "valid" / "all" — .py + .svg + .json
          "py"            — .py only
          "svg"           — .svg only
        """
        self.ensure_dirs()
        written: dict[str, Path] = {}

        if self.config.saves_py:
            p = self.valid_py_dir / f"{uuid}.py"
            p.write_text(code, encoding="utf-8")
            written["py"] = p
            meta.bytes_py = len(code.encode("utf-8"))

        if self.config.saves_svg:
            p = self.valid_svg_dir / f"{uuid}.svg"
            p.write_text(svg, encoding="utf-8")
            written["svg"] = p
            meta.bytes_svg = len(svg.encode("utf-8"))

            if self.config.keep_original and svg_original is not None:
                op = self.valid_svg_dir / f"{uuid}.original.svg"
                op.write_text(svg_original, encoding="utf-8")
                written["svg_original"] = op
                meta.bytes_svg_before_optimize = len(
                    svg_original.encode("utf-8")
                )

        if self.config.save in ("valid", "all"):
            p = self.valid_meta_dir / f"{uuid}.json"
            p.write_text(_to_json(meta), encoding="utf-8")
            written["meta"] = p

        self._append_manifest(meta)
        return written

    # ─── Saving invalid ───────────────────────────────────────

    def save_invalid(
        self,
        *,
        uuid: str,
        code: str,
        meta: Meta,
    ) -> dict[str, Path]:
        """
        Persist an invalid run. Only used when Config.saves_invalid
        is True (save mode == "all").
        """
        if not self.config.saves_invalid:
            # Nothing to do — caller should not even call us.
            return {}

        self.ensure_dirs()
        written: dict[str, Path] = {}

        p = self.invalid_dir / f"{uuid}.py"
        p.write_text(code, encoding="utf-8")
        written["py"] = p
        meta.bytes_py = len(code.encode("utf-8"))

        j = self.invalid_dir / f"{uuid}.json"
        j.write_text(_to_json(meta), encoding="utf-8")
        written["meta"] = j

        self._append_manifest(meta)
        return written

    # ─── Manifest ─────────────────────────────────────────────

    def _append_manifest(self, meta: Meta) -> None:
        """
        Append a compact record to manifest.jsonl.

        One JSON object per line, suitable for grep/jq.
        """
        self.root.mkdir(parents=True, exist_ok=True)

        record: dict[str, Any] = {
            "uuid": meta.uuid,
            "ts": meta.timestamp,
            "status": meta.status,
            "theme": meta.theme,
            "style": meta.style,
            "model": meta.model,
        }

        if meta.status == "invalid" and meta.reason:
            record["reason"] = meta.reason
        if meta.bytes_svg is not None:
            record["bytes_svg"] = meta.bytes_svg
        if meta.optimizer:
            record["optimizer"] = meta.optimizer

        with self.manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _to_json(meta: Meta) -> str:
    """Serialize Meta to a pretty JSON string."""
    return json.dumps(asdict(meta), indent=2, ensure_ascii=False) + "\n"


def utc_timestamp() -> str:
    """Current UTC time in ISO 8601, seconds precision, with Z."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def make_meta(
    *,
    uuid: str,
    theme: str,
    style: str,
    model: str,
    status: str,
    reason: str | None = None,
) -> Meta:
    """Convenience constructor for Meta with a UTC timestamp."""
    return Meta(
        uuid=uuid,
        theme=theme,
        style=style,
        model=model,
        timestamp=utc_timestamp(),
        status=status,
        reason=reason,
    )
