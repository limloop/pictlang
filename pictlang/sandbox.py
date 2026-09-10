"""
Isolated execution of generated render() code.

Runs the code in a separate Python process with:
  - isolated mode (-I): no user site-packages, no PYTHONPATH
  - wall-clock timeout (kill on expiry)
  - address space limit via resource.setrlimit
  - the DSL injected into the render() scope

Returns the SVG string produced by render().
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from .validator import check_code_structure, validate_svg, ValidationError


# ─────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────

class SandboxError(Exception):
    """Raised when the sandboxed execution fails."""


# ─────────────────────────────────────────────────────────────
# Child process code
# ─────────────────────────────────────────────────────────────

# This code runs in the child process. It receives the path to the
# generated .py file as argv[1], imports the DSL, executes the file,
# calls render(), and writes the result to stdout.
_CHILD_CODE = textwrap.dedent(r"""
    import importlib.util
    import sys
    import os

    # Make the package importable in isolated mode.
    # sys.argv[2] is the path to the pictlang package directory.
    pkg_dir = sys.argv[2]
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

    from pictlang.dsl import DSL_EXPORTS

    code_path = sys.argv[1]

    # Compile and exec the generated file in a fresh scope.
    with open(code_path, encoding="utf-8") as f:
        source = f.read()

    scope = dict(DSL_EXPORTS)
    code = compile(source, code_path, "exec")
    exec(code, scope)

    render = scope.get("render")
    if not callable(render):
        sys.stderr.write("render() not found or not callable\n")
        sys.exit(2)

    result = render()
    if not isinstance(result, str):
        sys.stderr.write(
            f"render() returned {type(result).__name__}, expected str\n"
        )
        sys.exit(3)

    sys.stdout.write(result)
""").strip()


# ─────────────────────────────────────────────────────────────
# Resource limits
# ─────────────────────────────────────────────────────────────

def _apply_limits(mem_mb: int, cpu_seconds: int):
    """
    Called in the child process before exec (POSIX only).
    Silently ignored on platforms that do not support it.
    """
    try:
        import resource

        mem_bytes = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    except Exception:
        # Windows, macOS restrictions, or missing privilege — ignore.
        pass


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def run_render(
    code_path: Path,
    *,
    timeout: int = 10,
    mem_mb: int = 512,
    max_svg_bytes: int = 500_000,
) -> str:
    """
    Execute the given .py file in a sandbox and return the SVG string.

    Steps:
      1. Read the source and validate its structure (AST).
      2. Run it in a subprocess with limits.
      3. Validate the returned SVG.
      4. Return the SVG string.
    """
    if not code_path.exists():
        raise SandboxError(f"Code file not found: {code_path}")

    source = code_path.read_text(encoding="utf-8")

    # 1. Static structure check (fast, no subprocess).
    try:
        check_code_structure(source)
    except ValidationError as e:
        raise SandboxError(f"invalid code structure: {e}") from e

    # 2. Isolated run.
    svg = _run_subprocess(
        code_path=code_path,
        timeout=timeout,
        mem_mb=mem_mb,
    )

    # 3. SVG validation.
    try:
        validate_svg(svg, max_bytes=max_svg_bytes)
    except ValidationError as e:
        raise SandboxError(f"invalid SVG: {e}") from e

    return svg


def _run_subprocess(*, code_path: Path, timeout: int, mem_mb: int) -> str:
    """Run the child process and return its stdout as text."""
    pkg_dir = str(Path(__file__).resolve().parent.parent)

    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        # Explicitly drop PYTHONPATH to keep isolation.
        # The package dir is injected via argv instead.
    }

    preexec = None
    if os.name == "posix":
        preexec = lambda: _apply_limits(mem_mb, timeout + 2)  # noqa: E731

    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-I",               # isolated mode
                "-c", _CHILD_CODE,
                str(code_path),
                pkg_dir,
            ],
            capture_output=True,
            timeout=timeout,
            env=env,
            preexec_fn=preexec,
        )
    except subprocess.TimeoutExpired:
        raise SandboxError(
            f"render() did not finish within {timeout}s"
        ) from None

    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise SandboxError(
            f"render() failed (exit code {proc.returncode}): {err}"
        )

    return proc.stdout.decode("utf-8", "replace")