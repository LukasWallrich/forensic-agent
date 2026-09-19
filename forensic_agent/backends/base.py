"""Backend interface: a plain completion engine with a deadline."""
from __future__ import annotations

import subprocess
import tempfile
from abc import ABC, abstractmethod

from ..models import LLMResult


class BackendError(RuntimeError):
    pass


class Backend(ABC):
    name = "base"
    default_model: str | None = None

    def __init__(self, model: str | None = None, timeout: int = 900):
        self.model = model or self.default_model
        self.timeout = timeout

    @abstractmethod
    def complete(self, prompt: str, system: str | None = None) -> LLMResult: ...


def run_cli(cmd: list[str], stdin: str, timeout: int, cwd: str | None = None) -> str:
    """Run a CLI agent in an empty temp dir (paper text is untrusted input)."""
    with tempfile.TemporaryDirectory(prefix="forensic-agent-") as tmp:
        try:
            proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                                  timeout=timeout, cwd=cwd or tmp)
        except FileNotFoundError as e:
            raise BackendError(f"{cmd[0]} is not installed or not on PATH") from e
        except subprocess.TimeoutExpired as e:
            raise BackendError(f"{cmd[0]} timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise BackendError(f"{cmd[0]} exited {proc.returncode}: {proc.stderr.strip()[-500:]}")
    return proc.stdout
