"""Tests for pictlang.prompt."""

from __future__ import annotations

from pathlib import Path

import pytest
from pictlang.prompt import (
    Prompt,
    PromptError,
    load_template,
    render_prompt,
)

# ─────────────────────────────────────────────────────────────
# Built-in template
# ─────────────────────────────────────────────────────────────

def test_builtin_template_loads():
    system, user = load_template(None)
    assert "{THEME}" in user
    assert "{STYLE}" in user
    # The default has a system section
    assert system


def test_render_builtin():
    prompt = render_prompt("a cat", "flat icon")
    assert "a cat" in prompt.user
    assert "flat icon" in prompt.user
    assert "{THEME}" not in prompt.user
    assert "{STYLE}" not in prompt.user


def test_prompt_messages_format():
    prompt = Prompt(system="sys", user="usr")
    msgs = prompt.messages()
    assert msgs == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]


def test_prompt_messages_without_system():
    prompt = Prompt(system="", user="usr")
    msgs = prompt.messages()
    assert msgs == [{"role": "user", "content": "usr"}]


# ─────────────────────────────────────────────────────────────
# Custom templates
# ─────────────────────────────────────────────────────────────

def test_custom_template_with_separator(tmp_path: Path):
    path = tmp_path / "custom.md"
    path.write_text(
        "SYSTEM LINE\n"
        "---\n"
        "Theme: {THEME}\n"
        "Style: {STYLE}\n",
        encoding="utf-8",
    )
    system, user = load_template(str(path))
    assert system == "SYSTEM LINE"
    assert "{THEME}" in user


def test_custom_template_without_separator(tmp_path: Path):
    path = tmp_path / "plain.md"
    path.write_text("Just {THEME} and {STYLE}", encoding="utf-8")
    system, user = load_template(str(path))
    assert system == ""
    assert "{THEME}" in user


def test_missing_placeholder_raises(tmp_path: Path):
    path = tmp_path / "bad.md"
    path.write_text("No placeholders at all", encoding="utf-8")
    with pytest.raises(PromptError, match="placeholder"):
        load_template(str(path))


def test_empty_user_section_raises(tmp_path: Path):
    path = tmp_path / "empty.md"
    path.write_text("System only\n---\n", encoding="utf-8")
    with pytest.raises(PromptError, match="empty user"):
        load_template(str(path))


def test_missing_file_raises():
    with pytest.raises(PromptError, match="not found"):
        load_template("/no/such/file.md")


# ─────────────────────────────────────────────────────────────
# Braces in template
# ─────────────────────────────────────────────────────────────

def test_stray_braces_are_tolerated(tmp_path: Path):
    """JSON examples in the prompt must not break formatting."""
    path = tmp_path / "with_json.md"
    path.write_text(
        'Example: {{"key": "value"}}\n'
        "Theme: {THEME}\n"
        "Style: {STYLE}\n",
        encoding="utf-8",
    )
    # The template has both doubled braces and required placeholders.
    # Doubled braces become single after format_map.
    prompt = render_prompt("x", "y", str(path))
    assert "x" in prompt.user
    assert "y" in prompt.user
