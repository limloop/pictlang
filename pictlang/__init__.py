"""
pictlang — generate SVG images from a theme and style via an LLM.

Public API:
    from pictlang import Config, LLMClient, generate

CLI:
    pictlang "theme" --style "style"
    python -m pictlang ...
"""

from ._version import __version__
from .api import APIConfig, APIError, LLMClient
from .config import Config
from .pipeline import GenerateResult, generate

__all__ = [
    "__version__",
    "APIConfig",
    "APIError",
    "LLMClient",
    "Config",
    "GenerateResult",
    "generate",
]