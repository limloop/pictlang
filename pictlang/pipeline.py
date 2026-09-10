"""
End-to-end pipeline for pictlang.

Ties together:
  config   → prompt   → LLM API
           → sandbox  → optimizer → storage

Entry point: generate(theme, style, config) -> GenerateResult
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .api import APIError, LLMClient
from .config import Config
from .optimizer import OptimizeResult, optimize
from .prompt import PromptError, render_prompt
from .sandbox import SandboxError, run_render
from .storage import Meta, Storage, make_meta
from .validator import ValidationError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────

@dataclass
class GenerateResult:
    """Everything a caller needs to know about a run."""

    uuid: str
    status: str                       # "valid" | "invalid"
    theme: str
    style: str
    reason: str | None = None

    code: str | None = None
    svg: str | None = None
    svg_original: str | None = None

    optimizer: str | None = None
    files: dict[str, Path] = field(default_factory=dict)
    meta: Meta | None = None
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "valid"


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def generate(
    theme: str,
    style: str,
    config: Config,
    *,
    client: LLMClient | None = None,
) -> GenerateResult:
    """
    Run one generation cycle.

    If `client` is provided, it is used as-is (useful for tests).
    Otherwise a fresh LLMClient is built from the config.

    Never raises on model/validation errors — returns a GenerateResult
    with status="invalid" and a reason. Raises only on programmer errors
    (bad config, missing files).
    """
    config.validate()

    started = time.monotonic()

    storage = Storage(config)
    storage.ensure_dirs()
    uuid = storage.new_uuid()

    meta = make_meta(
        uuid=uuid,
        theme=theme,
        style=style,
        model=config.api.model,
        status="pending",
    )

    owns_client = client is None
    if client is None:
        client = LLMClient(config.api)

    try:
        return _run(
            theme=theme,
            style=style,
            config=config,
            client=client,
            storage=storage,
            meta=meta,
            started=started,
        )
    finally:
        if owns_client:
            client.close()


# ─────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────

def _run(
    *,
    theme: str,
    style: str,
    config: Config,
    client: LLMClient,
    storage: Storage,
    meta: Meta,
    started: float,
) -> GenerateResult:
    # ─── 1. Prompt ─────────────────────────────────────────────
    try:
        prompt = render_prompt(theme, style, config.prompt_file)
    except PromptError as e:
        return _fail(
            storage, meta, theme, style,
            reason=f"prompt: {e}",
            started=started,
        )

    # ─── 2. API call ───────────────────────────────────────────
    t0 = time.monotonic()
    try:
        raw = client.chat(prompt.system, prompt.user)
    except APIError as e:
        return _fail(
            storage, meta, theme, style,
            reason=f"api: {e}",
            started=started,
        )
    meta.duration_api_ms = int((time.monotonic() - t0) * 1000)

    # ─── 3. Clean markdown fences ──────────────────────────────
    code = _strip_code_fences(raw)
    if not code.strip():
        return _fail(
            storage, meta, theme, style,
            reason="empty code after cleaning",
            started=started,
            code=code,
        )

    # ─── 4. Write to a temp .py so the sandbox can read it ────
    # We always write it, because the sandbox executes from a file.
    # Whether it's *persisted* is decided later by Storage.
    tmp_path = storage.root / ".tmp" / f"{meta.uuid}.py"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(code, encoding="utf-8")

    # ─── 5. Sandbox render ─────────────────────────────────────
    t0 = time.monotonic()
    try:
        svg = run_render(
            tmp_path,
            timeout=config.render_timeout,
            mem_mb=config.render_mem_mb,
        )
    except (SandboxError, ValidationError) as e:
        _cleanup_tmp(tmp_path)
        return _fail(
            storage, meta, theme, style,
            reason=f"render: {e}",
            started=started,
            code=code,
        )
    meta.duration_render_ms = int((time.monotonic() - t0) * 1000)

    svg_original = svg

    # ─── 6. Optimization (optional) ────────────────────────────
    opt: OptimizeResult | None = None
    if config.runs_optimizer:
        t0 = time.monotonic()
        opt = optimize(svg, config.optimizer)
        meta.duration_optimize_ms = int((time.monotonic() - t0) * 1000)
        if opt.optimizer is not None:
            svg = opt.svg
            meta.optimizer = opt.optimizer

    # ─── 7. Persist ────────────────────────────────────────────
    meta.status = "valid"
    written = storage.save_valid(
        uuid=meta.uuid,
        code=code,
        svg=svg,
        meta=meta,
        svg_original=svg_original if config.keep_original else None,
    )

    _cleanup_tmp(tmp_path)

    duration = int((time.monotonic() - started) * 1000)

    return GenerateResult(
        uuid=meta.uuid,
        status="valid",
        theme=theme,
        style=style,
        code=code if config.saves_py else None,
        svg=svg if config.saves_svg else None,
        svg_original=svg_original if config.keep_original else None,
        optimizer=meta.optimizer,
        files=written,
        meta=meta,
        duration_ms=duration,
    )


def _fail(
    storage: Storage,
    meta: Meta,
    theme: str,
    style: str,
    *,
    reason: str,
    started: float,
    code: str | None = None,
) -> GenerateResult:
    """
    Handle an invalid run: persist if configured, otherwise discard.
    Always returns a GenerateResult.
    """
    meta.status = "invalid"
    meta.reason = reason

    written: dict[str, Path] = {}
    if storage.config.saves_invalid and code is not None:
        written = storage.save_invalid(
            uuid=meta.uuid,
            code=code,
            meta=meta,
        )

    duration = int((time.monotonic() - started) * 1000)

    return GenerateResult(
        uuid=meta.uuid,
        status="invalid",
        theme=theme,
        style=style,
        reason=reason,
        code=code,
        files=written,
        meta=meta,
        duration_ms=duration,
    )


# ─────────────────────────────────────────────────────────────
# Code cleanup
# ─────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(
    r"^\s*```(?:python|py)?\s*\n(.*?)\n```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _strip_code_fences(text: str) -> str:
    """
    Remove a single surrounding Markdown code fence if present.

    Handles:
        ```python
        ...
        ```
        ```py
        ...
        ```
        ```
        ...
        ```

    If there is no fence, returns the input unchanged.
    """
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _cleanup_tmp(path: Path) -> None:
    """Best-effort removal of the temporary .py file."""
    try:
        path.unlink(missing_ok=True)
        # Remove the .tmp directory if it's now empty.
        parent = path.parent
        if parent.name == ".tmp" and not any(parent.iterdir()):
            parent.rmdir()
    except OSError as e:
        logger.debug("Could not clean up %s: %s", path, e)