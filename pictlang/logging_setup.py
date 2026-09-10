"""
Logging setup for pictlang.

Rules:
  - stdout is reserved for machine-readable output (UUID, paths).
  - all logs go to stderr.
  - default level is WARNING.
  - --verbose switches to DEBUG.
  - logs are always prefixed with the logger name so you can filter.
"""

from __future__ import annotations

import logging
import sys


_CONFIGURED = False


def setup_logging(verbose: bool = False) -> None:
    """
    Configure root logging.

    Idempotent: calling twice does nothing the second time.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = logging.DEBUG if verbose else logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Quiet down noisy third-party loggers
    for noisy in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True