"""Codex in non-interactive mode, read-only sandbox, empty working dir."""
from __future__ import annotations

import tempfile
from pathlib import Path

from ..models import LLMResult
from .base import Backend, BackendError, run_cli

PREAMBLE = ("Answer using only the text below. Do not run commands or read files. "
            "Reply with the requested output only.\n\n")


class CodexBackend(Backend):
    name = "codex"

    def complete(self, prompt, system=None):
        # codex exec has no system-prompt flag: system text is prepended.
        full = PREAMBLE + (f"{system}\n\n" if system else "") + prompt
        with tempfile.TemporaryDirectory(prefix="forensic-agent-codex-") as tmp:
            last = Path(tmp) / "last_message.txt"
            cmd = ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
                   "-o", str(last)]
            if self.model:
                cmd += ["-m", self.model]
            cmd.append("-")  # prompt from stdin
            run_cli(cmd, full, self.timeout, cwd=tmp)
            if not last.exists():
                raise BackendError("codex produced no final message")
            return LLMResult(text=last.read_text(), backend=self.name, model=self.model)
