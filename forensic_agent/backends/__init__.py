"""Backend registry. Adding a backend = one class + one line here."""
from __future__ import annotations

from ..models import BackendSpec
from .base import Backend, BackendError
from .claude_cli import ClaudeBackend
from .codex_cli import CodexBackend
from .mock import MockBackend
from .openrouter import OpenRouterBackend

BACKENDS: dict[str, type[Backend]] = {
    b.name: b for b in (ClaudeBackend, CodexBackend, OpenRouterBackend, MockBackend)}


def make_backend(spec: BackendSpec) -> Backend:
    return BACKENDS[spec.name](model=spec.model)


__all__ = ["BACKENDS", "Backend", "BackendError", "make_backend"]
