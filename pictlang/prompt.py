"""
Prompt assembly for pictlang.

Loads a prompt template, substitutes variables, and returns
(system, user) messages ready for LLMClient.chat().

The template is a plain Markdown file with placeholders like {THEME}
and {STYLE}. Placeholders are ordinary Python str.format() fields.

If the template contains a `---` line, everything above it is treated
as the system prompt and everything below as the user prompt.
If there is no `---`, the whole file is the user prompt and the
system prompt is empty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────

# Path to the built-in prompt template, relative to the package.
BUILTIN_PROMPT = Path(__file__).parent / "prompts" / "default.md"

# The separator between system and user parts of the template.
SECTION_SEPARATOR = "---"

# Placeholders that must be present in the user section.
REQUIRED_PLACEHOLDERS = ("{THEME}", "{STYLE}")


# ─────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────

class PromptError(Exception):
    """Raised when the prompt template cannot be loaded or filled."""


# ─────────────────────────────────────────────────────────────
# Data
# ─────────────────────────────────────────────────────────────

@dataclass
class Prompt:
    """A ready-to-send pair of messages."""

    system: str
    user: str
    template_path: Path | None = None

    def messages(self) -> list[dict[str, str]]:
        """Format as OpenAI-compatible messages list."""
        out: list[dict[str, str]] = []
        if self.system:
            out.append({"role": "system", "content": self.system})
        out.append({"role": "user", "content": self.user})
        return out


# ─────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────

def resolve_template_path(prompt_file: str | None) -> Path:
    """
    Resolve the prompt template path.

    Order:
      1. explicit path from config (if set)
      2. built-in default template
    """
    if prompt_file:
        path = Path(prompt_file).expanduser()
        if not path.exists():
            raise PromptError(f"Prompt template not found: {path}")
        return path

    if not BUILTIN_PROMPT.exists():
        raise PromptError(
            f"Built-in prompt template is missing: {BUILTIN_PROMPT}. "
            f"This is a packaging error."
        )

    return BUILTIN_PROMPT


def load_template(prompt_file: str | None = None) -> tuple[str, str]:
    """
    Load a template and split it into (system, user) sections.

    The split happens on the first line that consists only of `---`.
    """
    path = resolve_template_path(prompt_file)
    text = path.read_text(encoding="utf-8")

    system, user = _split_sections(text, path)

    _validate_placeholders(user, path)

    return system, user


def _split_sections(text: str, path: Path) -> tuple[str, str]:
    """Split template text into system and user parts."""
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if line.strip() == SECTION_SEPARATOR:
            system = "\n".join(lines[:i]).strip()
            user = "\n".join(lines[i + 1:]).strip()
            if not user:
                raise PromptError(
                    f"Template {path} has an empty user section"
                )
            return system, user

    # No separator: everything is the user prompt.
    user = text.strip()
    if not user:
        raise PromptError(f"Template {path} is empty")
    return "", user


def _validate_placeholders(user: str, path: Path) -> None:
    """Ensure the user section contains the required placeholders."""
    missing = [ph for ph in REQUIRED_PLACEHOLDERS if ph not in user]
    if missing:
        raise PromptError(
            f"Template {path} is missing required placeholder(s): "
            f"{', '.join(missing)}"
        )


# ─────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────

def render_prompt(
    theme: str,
    style: str,
    prompt_file: str | None = None,
) -> Prompt:
    """
    Load the template and fill it with theme and style.

    Uses str.format_map with a custom mapping so that unexpected
    braces in the template do not blow up the call.
    """
    system, user = load_template(prompt_file)

    values = {"THEME": theme, "STYLE": style}

    try:
        system_filled = _safe_format(system, values) if system else ""
        user_filled = _safe_format(user, values)
    except KeyError as e:
        raise PromptError(
            f"Unknown placeholder in template: {e}. "
            f"Supported placeholders: {', '.join(values)}"
        ) from e

    return Prompt(
        system=system_filled,
        user=user_filled,
        template_path=resolve_template_path(prompt_file),
    )


def _safe_format(template: str, values: dict[str, str]) -> str:
    """
    Like str.format_map, but tolerates unknown braces.

    Uses a dict subclass that returns the original placeholder for
    unknown keys. This lets templates contain things like JSON examples
    or code snippets with braces without breaking.
    """
    class _Mapping(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(_Mapping(values))


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────

def preview_prompt(prompt: Prompt, max_chars: int = 400) -> str:
    """Short human-readable preview for logs and --verbose."""
    parts = []
    if prompt.system:
        parts.append("SYSTEM:\n" + _clip(prompt.system, max_chars))
    parts.append("USER:\n" + _clip(prompt.user, max_chars))
    return "\n\n".join(parts)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n... [truncated]"