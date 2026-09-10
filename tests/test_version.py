def test_version_matches_pyproject():
    """pyproject.toml and _version.py must agree."""
    import re
    from pathlib import Path

    from pictlang._version import __version__

    root = Path(__file__).resolve().parent.parent
    pyproject = root / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml not found"

    text = pyproject.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "version not found in pyproject.toml"

    assert m.group(1) == __version__, (
        f"version mismatch: pyproject={m.group(1)!r}, "
        f"_version={__version__!r}"
    )