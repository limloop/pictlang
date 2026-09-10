"""
Optional SVG optimization for pictlang.

Two backends:
  - scour: pure Python, installed via `pip install scour`
  - svgo:  Node.js tool, must be on PATH

Both are optional. If a backend is unavailable, it is silently skipped.
Optimization never fails the run: on any error the original SVG is
returned unchanged.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────

@dataclass
class OptimizeResult:
    """Outcome of an optimization attempt."""

    svg: str
    optimizer: str | None   # "scour", "svgo", or None if nothing ran
    bytes_before: int
    bytes_after: int

    @property
    def ratio(self) -> float:
        """Size ratio after / before. 1.0 means no change."""
        if self.bytes_before == 0:
            return 1.0
        return self.bytes_after / self.bytes_before

    @property
    def saved(self) -> int:
        return self.bytes_before - self.bytes_after


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def optimize(svg: str, optimizer: str = "auto") -> OptimizeResult:
    """
    Try to optimize the SVG.

    optimizer:
      - "auto"  — try scour, then svgo
      - "scour" — only scour
      - "svgo"  — only svgo

    Never raises. On any failure returns the original SVG with
    optimizer=None.
    """
    bytes_before = len(svg.encode("utf-8"))

    candidates: list[str]
    if optimizer == "auto":
        candidates = ["scour", "svgo"]
    elif optimizer in ("scour", "svgo"):
        candidates = [optimizer]
    else:
        logger.warning("Unknown optimizer %r, skipping", optimizer)
        return OptimizeResult(svg, None, bytes_before, bytes_before)

    for name in candidates:
        try:
            if name == "scour":
                out = _try_scour(svg)
            elif name == "svgo":
                out = _try_svgo(svg)
            else:
                out = None
        except Exception as e:
            logger.debug("Optimizer %s raised: %s", name, e)
            out = None

        if out is not None:
            bytes_after = len(out.encode("utf-8"))
            logger.debug(
                "Optimized with %s: %d -> %d bytes (%.1f%%)",
                name, bytes_before, bytes_after,
                (bytes_after / bytes_before * 100) if bytes_before else 0,
            )
            return OptimizeResult(out, name, bytes_before, bytes_after)

    logger.debug("No optimizer available, returning original")
    return OptimizeResult(svg, None, bytes_before, bytes_before)


# ─────────────────────────────────────────────────────────────
# Backends
# ─────────────────────────────────────────────────────────────

def _try_scour(svg: str) -> str | None:
    """
    Optimize via scour. Returns None if scour is not installed
    or if optimization fails.
    """
    try:
        from scour.scour import parse_args, scourString
    except ImportError:
        logger.debug("scour is not installed")
        return None

    try:
        # Options that are safe and useful for our DSL output.
        # See `scour --help` for the full list.
        opts = parse_args([
            "--shorten-ids",
            "--remove-metadata",
            "--strip-xml-prolog",
            "--enable-comment-strip",
            "--enable-viewboxing",
            "--indent=none",
            "--no-line-breaks",
        ])
        result = scourString(svg, opts)
        if not result:
            return None
        return result
    except SystemExit:
        # parse_args may call sys.exit on bad flags — treat as failure
        return None
    except Exception as e:
        logger.debug("scour failed: %s", e)
        return None


def _try_svgo(svg: str) -> str | None:
    """
    Optimize via svgo (Node.js). Returns None if svgo is not on PATH
    or if the process fails.
    """
    svgo_path = shutil.which("svgo")
    if not svgo_path:
        logger.debug("svgo is not on PATH")
        return None

    try:
        proc = subprocess.run(
            [svgo_path, "-i", "-", "-o", "-", "--multipass"],
            input=svg.encode("utf-8"),
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        logger.debug("svgo timed out")
        return None
    except OSError as e:
        logger.debug("svgo failed to start: %s", e)
        return None

    if proc.returncode != 0:
        logger.debug(
            "svgo exited with %d: %s",
            proc.returncode,
            proc.stderr.decode("utf-8", "replace")[:200],
        )
        return None

    out = proc.stdout.decode("utf-8", "replace")
    return out or None


# ─────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────

def available_optimizers() -> list[str]:
    """Return names of optimizers that are actually usable now."""
    found: list[str] = []

    try:
        import scour  # noqa: F401
        found.append("scour")
    except ImportError:
        pass

    if shutil.which("svgo"):
        found.append("svgo")

    return found
