"""Claude Code in headless mode, with all tools disabled."""
from __future__ import annotations

import json

from ..models import LLMResult
from .base import Backend, BackendError, run_cli


class ClaudeBackend(Backend):
    name = "claude"

    def complete(self, prompt, system=None):
        cmd = ["claude", "-p", "--output-format", "json", "--tools", ""]
        if self.model:
            cmd += ["--model", self.model]
        if system:
            cmd += ["--system-prompt", system]
        out = run_cli(cmd, prompt, self.timeout)
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            raise BackendError(f"claude returned non-JSON output: {out[:200]}") from e
        if data.get("is_error"):
            raise BackendError(f"claude error: {data.get('result')}")
        return LLMResult(text=data.get("result", ""), backend=self.name,
                         model=self.model, usage=data.get("usage") or {})
