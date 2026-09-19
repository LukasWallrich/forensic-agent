"""OpenRouter chat completions over HTTPS (stdlib only)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ..models import LLMResult
from .base import Backend, BackendError

URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterBackend(Backend):
    name = "openrouter"

    def complete(self, prompt, system=None):
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise BackendError("OPENROUTER_API_KEY is not set")
        if not self.model:
            raise BackendError("openrouter needs an explicit model (--model or YAML `model:`)")
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}]
        req = urllib.request.Request(
            URL, data=json.dumps({"model": self.model, "messages": messages}).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            raise BackendError(f"openrouter HTTP {e.code}: {e.read().decode()[:300]}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise BackendError(f"openrouter request failed: {e}") from e
        if "error" in data or not data.get("choices"):
            raise BackendError(f"openrouter error: {str(data.get('error', data))[:300]}")
        usage = dict(data.get("usage") or {}, provider=data.get("provider"))
        return LLMResult(text=data["choices"][0]["message"]["content"] or "",
                         backend=self.name, model=data.get("model", self.model), usage=usage)
