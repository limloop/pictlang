"""
Command-line interface for pictlang.

Thin wrapper around pipeline.generate(). Parses arguments, applies
overrides on top of the config file, calls generate(), prints the
result UUID, and exits.

Exit codes:
    0 — success (valid SVG produced)
    1 — usage error / bad config
    2 — generation failed (invalid result, API error, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._version import __version__
from .config import DEFAULT_CONFIG_NAME, SAVE_MODES, USER_CONFIG_PATH, Config, example_config
from .logging_setup import setup_logging
from .pipeline import generate

# ─────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pictlang",
        description=(
            "Generate an SVG image from a theme and style via an LLM. "
            "The model writes a Python render() function; pictlang runs it "
            "in a sandbox and saves the resulting SVG."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  pictlang \"lighthouse in the fog\" --style \"minimalism, 3 colors\"\n"
            "  pictlang \"cyberpunk city\" --style \"neon, glow\" --optimize\n"
            "  pictlang init                       # write a template config\n"
            "  pictlang init --path ./my.json      # write it elsewhere\n"
        ),
    )

    p.add_argument(
        "theme",
        nargs="?",
        help="What to draw (positional). Omit when running subcommands.",
    )

    p.add_argument(
        "--style",
        help="How to draw it (required for generation).",
    )

    # ── Output ──────────────────────────────────────────────
    out = p.add_argument_group("output")
    out.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (overrides config.output_dir).",
    )
    out.add_argument(
        "--save",
        choices=SAVE_MODES,
        default=None,
        help=(
            "What to persist: valid (default) | all | py | svg. "
            "'all' keeps invalid runs too."
        ),
    )
    out.add_argument(
        "--keep-original",
        action="store_true",
        default=None,
        help="Also save the SVG before optimization as <uuid>.original.svg.",
    )

    # ── Optimization ────────────────────────────────────────
    opt = p.add_argument_group("optimization")
    opt.add_argument(
        "--optimize",
        dest="optimize",
        action="store_true",
        default=None,
        help="Enable SVG optimization (ignored in --save py).",
    )
    opt.add_argument(
        "--no-optimize",
        dest="optimize",
        action="store_false",
        help="Disable SVG optimization.",
    )
    opt.add_argument(
        "--optimizer",
        choices=("auto", "scour", "svgo"),
        default=None,
        help="Which optimizer to use (default: auto).",
    )

    # ── API ─────────────────────────────────────────────────
    api = p.add_argument_group("api")
    api.add_argument("--config", type=Path, default=None,
                     help="Path to a config file.")
    api.add_argument("--base-url", default=None,
                     help="OpenAI-compatible base URL.")
    api.add_argument("--api-key", default=None,
                     help="API key.")
    api.add_argument("--model", default=None,
                     help="Model name.")
    api.add_argument("--temperature", type=float, default=None,
                     help="Sampling temperature.")
    api.add_argument("--max-tokens", type=int, default=None,
                     help="Max tokens in the response.")
    api.add_argument("--timeout", type=float, default=None,
                     help="HTTP timeout, seconds.")
    api.add_argument("--proxy", default=None,
                     help="Proxy URL (http/https/socks5).")
    api.add_argument("--reasoning", dest="enable_reasoning",
                     action="store_true", default=None,
                     help="Explicitly enable reasoning (default: provider default).")
    api.add_argument("--no-reasoning", dest="enable_reasoning",
                     action="store_false",
                     help="Explicitly disable reasoning.")

    # ── Prompt ──────────────────────────────────────────────
    pr = p.add_argument_group("prompt")
    pr.add_argument("--prompt-file", default=None,
                    help="Path to a custom prompt template.")

    # ── Sandbox ─────────────────────────────────────────────
    sb = p.add_argument_group("sandbox")
    sb.add_argument("--render-timeout", type=int, default=None,
                    help="Wall-clock timeout for render(), seconds.")
    sb.add_argument("--render-mem-mb", type=int, default=None,
                    help="Memory limit for the render subprocess, MB.")

    # ── Misc ────────────────────────────────────────────────
    p.add_argument("--verbose", action="store_true", default=None,
                   help="Enable debug logging on stderr.")
    p.add_argument("--version", action="version",
                   version=f"pictlang {__version__}")
    p.add_argument("--check", action="store_true",
                   help="Validate config and test API connection, then exit.")

    return p


# ─────────────────────────────────────────────────────────────
# Subcommands
# ─────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> int:
    """Write a template config file."""
    # If `pictlang init --path ...` — write there.
    # Otherwise write to ./pictlang.json.
    target = getattr(args, "init_path", None) or Path("pictlang.json")
    target = Path(target)

    if target.exists():
        print(f"refusing to overwrite: {target}", file=sys.stderr)
        return 1

    target.write_text(
        json.dumps(example_config(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target}")
    print("edit it to set your api_key, then run:")
    print("  pictlang \"a cat\" --style \"flat icon\"")
    return 0


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def _config_exists() -> bool:
    return (
        (Path.cwd() / DEFAULT_CONFIG_NAME).exists()
        or USER_CONFIG_PATH.exists()
    )

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # `init` is a subcommand but we implement it manually to keep
    # the parser flat. If the first token is "init", route to it.
    if argv and argv[0] == "init":
        return _main_init(argv[1:])

    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(verbose=bool(args.verbose))

    # Load config
    try:
        config = Config.load(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    # Warn once, at most, if no config was found anywhere.
    if args.config is None and not _config_exists():
        print(
            "warning: no config file found (using defaults).\n"
            f"  project: {Path.cwd() / DEFAULT_CONFIG_NAME}\n"
            f"  user:    {USER_CONFIG_PATH}\n"
            "  run `pictlang init` to create a project config,\n"
            "  or  `pictlang init --global` for a user config.",
            file=sys.stderr,
        )

    # Apply CLI overrides
    overrides = {
        "output_dir": args.out,
        "save": args.save,
        "keep_original": args.keep_original,
        "optimize": args.optimize,
        "optimizer": args.optimizer,
        "prompt_file": args.prompt_file,
        "render_timeout": args.render_timeout,
        "render_mem_mb": args.render_mem_mb,
        "verbose": args.verbose,
        "api.base_url": args.base_url,
        "api.api_key": args.api_key,
        "api.model": args.model,
        "api.temperature": args.temperature,
        "api.max_tokens": args.max_tokens,
        "api.timeout": args.timeout,
        "api.proxy": args.proxy,
        "api.enable_reasoning": args.enable_reasoning,
    }

    try:
        config.apply_overrides(overrides)
    except ValueError as e:
        print(f"argument error: {e}", file=sys.stderr)
        return 1

    # --check: validate config, test connection, exit.
    if args.check:
        return _cmd_check(config)

    # Generation requires theme and style.
    if not args.theme:
        parser.print_usage(sys.stderr)
        print("error: theme is required for generation", file=sys.stderr)
        return 1
    if not args.style:
        parser.print_usage(sys.stderr)
        print("error: --style is required for generation", file=sys.stderr)
        return 1

    # Run the pipeline.
    try:
        result = generate(args.theme, args.style, config)
    except Exception as e:
        # Unexpected errors (programmer bugs, missing files, etc.)
        print(f"unexpected error: {e}", file=sys.stderr)
        return 2

    return _print_result(result)


# ─────────────────────────────────────────────────────────────
# `init` handling
# ─────────────────────────────────────────────────────────────

def _main_init(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="pictlang init")
    p.add_argument("--global", dest="use_global", action="store_true",
                   help="Write to the user config directory "
                     "(~/.config/pictlang/ on Linux, "
                     "~/Library/Application Support/pictlang/ on macOS, "
                     "%%APPDATA%%\\limloop\\pictlang\\ on Windows).")
    p.add_argument("--path", default=None,
                   help="Write the config to an explicit path.")
    args = p.parse_args(argv)

    if args.path:
        target = Path(args.path)
    elif args.use_global:
        target = USER_CONFIG_PATH
    else:
        target = Path("pictlang.json")

    if target.exists():
        print(f"refusing to overwrite: {target}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(example_config(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {target}")
    print("edit it to set your api_key, then run:")
    print('  pictlang "a cat" --style "flat icon"')
    return 0


# ─────────────────────────────────────────────────────────────
# `--check`
# ─────────────────────────────────────────────────────────────

def _cmd_check(config: Config) -> int:
    """Validate config and test API connectivity."""
    try:
        config.validate()
    except ValueError as e:
        print(f"config invalid: {e}", file=sys.stderr)
        return 1

    print("config:  ok")
    print(f"model:   {config.api.model}")
    print(f"base:    {config.api.base_url}")
    print(f"output:  {config.output_dir}")
    print(f"save:    {config.save}")
    print(f"optimize:{'on' if config.runs_optimizer else 'off'}"
          + (f" ({config.optimizer})" if config.runs_optimizer else ""))

    from .api import LLMClient
    from .optimizer import available_optimizers

    print(f"optimizers available: {', '.join(available_optimizers()) or 'none'}")

    print("testing API connection...")
    client = LLMClient(config.api)
    try:
        ok = client.test_connection()
    finally:
        client.close()

    if ok:
        print("api:     ok")
        return 0
    print("api:     failed", file=sys.stderr)
    return 1


# ─────────────────────────────────────────────────────────────
# Result output
# ─────────────────────────────────────────────────────────────

def _print_result(result) -> int:
    """
    Print result to stdout in a clean, parseable way.

    Format:
        UUID: <uuid>
        SVG:  <path>       (if saved)
        PY:   <path>       (if saved)
        META: <path>       (if saved)
        REASON: <text>     (if invalid)
    """
    if result.status == "valid":
        print(f"UUID: {result.uuid}")

        if "svg" in result.files:
            print(f"SVG:  {result.files['svg']}")
        if "svg_original" in result.files:
            print(f"ORIG: {result.files['svg_original']}")
        if "py" in result.files:
            print(f"PY:   {result.files['py']}")
        if "meta" in result.files:
            print(f"META: {result.files['meta']}")

        if result.optimizer:
            meta = result.meta
            if meta and meta.bytes_svg_before_optimize and meta.bytes_svg:
                saved = meta.bytes_svg_before_optimize - meta.bytes_svg
                print(f"OPT:  {result.optimizer} (-{saved} bytes)")

        return 0

    # Invalid
    print(f"UUID: {result.uuid}")
    print("STATUS: invalid")
    print(f"REASON: {result.reason or 'unknown'}")
    if result.files:
        for kind, path in result.files.items():
            print(f"{kind.upper()}: {path}")
    return 2
