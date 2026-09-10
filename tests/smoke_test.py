"""
Smoke test for pictlang.

Runs a quick end-to-end check without pytest and without a real API.
Run from the repository root:

    python tests/smoke_test.py

Exits 0 on success, 1 on first failure.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory

# Make the package importable when running from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def section(name: str) -> None:
    print(f"\n=== {name} ===")


def check(name: str, fn) -> None:
    """Run fn(), print PASS or FAIL. Re-raise on failure."""
    try:
        fn()
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        traceback.print_exc()
        sys.exit(1)
    else:
        print(f"{PASS}  {name}")


# ─────────────────────────────────────────────────────────────
# 1. Imports
# ─────────────────────────────────────────────────────────────

def test_imports():
    import pictlang
    from pictlang import Config, LLMClient, generate  # noqa
    from pictlang.api import APIConfig
    from pictlang.config import example_config
    from pictlang.prompt import render_prompt
    from pictlang.validator import check_code_structure, validate_svg
    from pictlang.sandbox import run_render
    from pictlang.optimizer import optimize, available_optimizers
    from pictlang.storage import Storage, make_meta
    from pictlang.pipeline import GenerateResult
    from pictlang.dsl import DSL_EXPORTS
    assert pictlang.__version__


# ─────────────────────────────────────────────────────────────
# 2. Config
# ─────────────────────────────────────────────────────────────

def test_config_defaults():
    from pictlang import Config
    cfg = Config()
    assert cfg.api.base_url.startswith("http")
    assert cfg.save == "valid"
    assert cfg.saves_py and cfg.saves_svg
    assert not cfg.saves_invalid
    assert not cfg.runs_optimizer


def test_config_modes():
    from pictlang import Config
    for save, py, svg, inv in [
        ("valid", True, True, False),
        ("all", True, True, True),
        ("py", True, False, False),
        ("svg", False, True, False),
    ]:
        cfg = Config(save=save)
        assert cfg.saves_py == py, save
        assert cfg.saves_svg == svg, save
        assert cfg.saves_invalid == inv, save

    # Optimization never runs in "py" mode.
    cfg = Config(save="py", optimize=True)
    assert cfg.runs_optimizer is False
    cfg = Config(save="svg", optimize=True)
    assert cfg.runs_optimizer is True


def test_config_validate():
    from pictlang import Config
    cfg = Config()
    cfg.api.api_key = "x"
    cfg.validate()

    try:
        Config(save="bogus").validate()
    except ValueError:
        pass
    else:
        raise AssertionError("bad save mode should fail validation")


def test_config_roundtrip():
    import json
    from pictlang import Config
    from pictlang.config import example_config

    example = example_config()
    assert "api" in example
    assert "save" in example

    # Build from dict
    cfg = Config._from_dict(example)
    assert cfg.save == "valid"


# ─────────────────────────────────────────────────────────────
# 3. Prompt
# ─────────────────────────────────────────────────────────────

def test_prompt_default():
    from pictlang.prompt import render_prompt

    p = render_prompt("a cat", "flat icon")
    assert "a cat" in p.user
    assert "flat icon" in p.user
    assert p.system  # default has a system section


def test_prompt_missing_placeholder():
    from pictlang.prompt import render_prompt, PromptError
    from pathlib import Path
    from tempfile import NamedTemporaryFile

    with NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("No placeholders here.\n")
        path = Path(f.name)

    try:
        try:
            render_prompt("x", "y", str(path))
        except PromptError:
            pass
        else:
            raise AssertionError("expected PromptError")
    finally:
        path.unlink()


# ─────────────────────────────────────────────────────────────
# 4. DSL
# ─────────────────────────────────────────────────────────────

def test_dsl_exports():
    from pictlang.dsl import DSL_EXPORTS
    required = {
        "new_canvas", "add", "to_svg", "bg",
        "rect", "circle", "ellipse", "line", "polygon", "polyline",
        "path", "arc", "star", "ring", "grid",
        "smooth", "blob", "wave",
        "grad_lin", "grad_rad",
        "glow", "shadow", "blur",
        "group", "rotate", "scale", "opacity",
        "PALETTE", "math", "random", "polar",
    }
    missing = required - set(DSL_EXPORTS)
    assert not missing, f"missing DSL exports: {missing}"


def test_dsl_simple_svg():
    from pictlang.dsl import DSL_EXPORTS
    ns = dict(DSL_EXPORTS)
    exec(
        "def render():\n"
        "    c = new_canvas(64, 64)\n"
        "    add(c, rect(0, 0, 64, 64, fill='#fff'))\n"
        "    add(c, circle(32, 32, 10, fill='#f00'))\n"
        "    return to_svg(c)\n",
        ns,
    )
    svg = ns["render"]()
    assert svg.startswith("<svg")
    assert "circle" in svg


# ─────────────────────────────────────────────────────────────
# 5. Validator
# ─────────────────────────────────────────────────────────────

def test_validate_code_ok():
    from pictlang.validator import check_code_structure
    check_code_structure(
        "def render():\n"
        "    return '<svg/>'\n"
    )


def test_validate_code_rejects_import():
    from pictlang.validator import check_code_structure, ValidationError
    try:
        check_code_structure(
            "def render():\n"
            "    import math\n"
            "    return '<svg/>'\n"
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("import inside render should be rejected")


def test_validate_code_rejects_toplevel():
    from pictlang.validator import check_code_structure, ValidationError
    try:
        check_code_structure(
            "x = 1\n"
            "def render():\n"
            "    return '<svg/>'\n"
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("top-level assignment should be rejected")


def test_validate_svg_ok():
    from pictlang.validator import validate_svg
    validate_svg('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')


def test_validate_svg_rejects_garbage():
    from pictlang.validator import validate_svg, ValidationError
    for bad in ["", "hello", "<html></html>", "<svg>"]:
        try:
            validate_svg(bad)
        except ValidationError:
            continue
        raise AssertionError(f"should reject: {bad!r}")


# ─────────────────────────────────────────────────────────────
# 6. Sandbox
# ─────────────────────────────────────────────────────────────

def test_sandbox_simple():
    from pictlang.sandbox import run_render
    with TemporaryDirectory() as td:
        p = Path(td) / "gen.py"
        p.write_text(
            "def render():\n"
            "    c = new_canvas(32, 32)\n"
            "    add(c, rect(0, 0, 32, 32, fill='#000'))\n"
            "    return to_svg(c)\n",
            encoding="utf-8",
        )
        svg = run_render(p, timeout=5, mem_mb=256)
        assert svg.startswith("<svg")
        assert "rect" in svg


def test_sandbox_timeout():
    from pictlang.sandbox import run_render, SandboxError
    with TemporaryDirectory() as td:
        p = Path(td) / "gen.py"
        p.write_text(
            "def render():\n"
            "    while True:\n"
            "        pass\n",
            encoding="utf-8",
        )
        try:
            run_render(p, timeout=2, mem_mb=256)
        except SandboxError as e:
            assert "did not finish" in str(e)
        else:
            raise AssertionError("timeout should raise SandboxError")


def test_sandbox_rejects_bad_code():
    from pictlang.sandbox import run_render, SandboxError
    with TemporaryDirectory() as td:
        p = Path(td) / "gen.py"
        p.write_text("def render():\n    return 42\n", encoding="utf-8")
        try:
            run_render(p, timeout=5)
        except SandboxError:
            pass
        else:
            raise AssertionError("non-str return should fail")


# ─────────────────────────────────────────────────────────────
# 7. Optimizer
# ─────────────────────────────────────────────────────────────

def test_optimizer_no_crash():
    from pictlang.optimizer import optimize
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="1" height="1"/></svg>'
    result = optimize(svg, "auto")
    # Either it optimized, or it returned the original. Both are OK.
    assert result.svg.startswith("<svg")
    assert result.bytes_before > 0
    assert result.bytes_after > 0


def test_optimizer_available():
    from pictlang.optimizer import available_optimizers
    names = available_optimizers()
    assert isinstance(names, list)


# ─────────────────────────────────────────────────────────────
# 8. Storage
# ─────────────────────────────────────────────────────────────

def test_storage_valid():
    from pictlang import Config
    from pictlang.storage import Storage, make_meta

    with TemporaryDirectory() as td:
        cfg = Config(output_dir=Path(td), save="valid")
        cfg.api.api_key = "x"
        st = Storage(cfg)
        st.ensure_dirs()
        u = st.new_uuid()

        meta = make_meta(
            uuid=u, theme="cat", style="flat",
            model="m", status="valid",
        )
        files = st.save_valid(
            uuid=u,
            code="def render():\n    return '<svg/>'\n",
            svg='<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
            meta=meta,
        )

        assert "py" in files and files["py"].exists()
        assert "svg" in files and files["svg"].exists()
        assert "meta" in files and files["meta"].exists()
        assert st.manifest_path.exists()

        content = st.manifest_path.read_text(encoding="utf-8")
        assert u in content


def test_storage_py_only():
    from pictlang import Config
    from pictlang.storage import Storage, make_meta

    with TemporaryDirectory() as td:
        cfg = Config(output_dir=Path(td), save="py")
        cfg.api.api_key = "x"
        st = Storage(cfg)
        st.ensure_dirs()
        u = st.new_uuid()

        meta = make_meta(
            uuid=u, theme="cat", style="flat",
            model="m", status="valid",
        )
        files = st.save_valid(
            uuid=u,
            code="def render(): ...\n",
            svg="<svg/>",
            meta=meta,
        )
        assert "py" in files
        assert "svg" not in files
        # meta is not saved in "py" mode either
        assert "meta" not in files


# ─────────────────────────────────────────────────────────────
# 9. Pipeline (mocked client)
# ─────────────────────────────────────────────────────────────

class _MockClient:
    """Duck-typed LLMClient for testing."""

    def __init__(self, response: str):
        self._response = response

    def chat(self, system: str, user: str) -> str:
        return self._response

    def close(self) -> None:
        pass


def test_pipeline_end_to_end():
    from pictlang import Config
    from pictlang.pipeline import generate

    code = (
        "def render():\n"
        "    c = new_canvas(32, 32)\n"
        "    add(c, rect(0, 0, 32, 32, fill='#123456'))\n"
        "    return to_svg(c)\n"
    )
    # Model wraps it in markdown to test the cleanup.
    raw = f"```python\n{code}```\n"

    with TemporaryDirectory() as td:
        cfg = Config(output_dir=Path(td), save="valid")
        cfg.api.api_key = "x"
        cfg.optimize = False

        result = generate("cat", "flat", cfg, client=_MockClient(raw))

        assert result.ok, result.reason
        assert result.uuid
        assert result.svg and result.svg.startswith("<svg")
        assert "py" in result.files
        assert result.files["py"].exists()
        assert result.files["svg"].exists()


def test_pipeline_invalid_svg():
    from pictlang import Config
    from pictlang.pipeline import generate

    # render() returns garbage — pipeline should mark as invalid.
    code = "def render():\n    return 'not svg'\n"

    with TemporaryDirectory() as td:
        cfg = Config(output_dir=Path(td), save="valid")
        cfg.api.api_key = "x"

        result = generate("x", "y", cfg, client=_MockClient(code))

        assert result.status == "invalid"
        assert result.reason
        assert "svg" not in result.files


def test_pipeline_invalid_kept():
    from pictlang import Config
    from pictlang.pipeline import generate

    code = "def render():\n    return 'not svg'\n"

    with TemporaryDirectory() as td:
        cfg = Config(output_dir=Path(td), save="all")
        cfg.api.api_key = "x"

        result = generate("x", "y", cfg, client=_MockClient(code))

        assert result.status == "invalid"
        assert "py" in result.files
        assert result.files["py"].exists()


# ─────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────

def main() -> int:
    print("pictlang smoke test")

    section("imports")
    check("import all modules", test_imports)

    section("config")
    check("defaults", test_config_defaults)
    check("save modes", test_config_modes)
    check("validation", test_config_validate)
    check("roundtrip via example", test_config_roundtrip)

    section("prompt")
    check("default template", test_prompt_default)
    check("missing placeholder rejected", test_prompt_missing_placeholder)

    section("dsl")
    check("exports present", test_dsl_exports)
    check("simple svg", test_dsl_simple_svg)

    section("validator")
    check("code ok", test_validate_code_ok)
    check("code rejects import", test_validate_code_rejects_import)
    check("code rejects top-level", test_validate_code_rejects_toplevel)
    check("svg ok", test_validate_svg_ok)
    check("svg rejects garbage", test_validate_svg_rejects_garbage)

    section("sandbox")
    check("simple render", test_sandbox_simple)
    check("timeout", test_sandbox_timeout)
    check("rejects bad return", test_sandbox_rejects_bad_code)

    section("optimizer")
    check("no crash without scour/svgo", test_optimizer_no_crash)
    check("available_optimizers", test_optimizer_available)

    section("storage")
    check("save valid", test_storage_valid)
    check("save py only", test_storage_py_only)

    section("pipeline")
    check("end-to-end with mock", test_pipeline_end_to_end)
    check("invalid svg", test_pipeline_invalid_svg)
    check("invalid kept when save=all", test_pipeline_invalid_kept)

    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())