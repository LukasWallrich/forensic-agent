"""Structured output: extract JSON, validate, retry once with the error."""
from __future__ import annotations

import json
import re

from .backends import Backend, BackendError


class InvalidOutput(BackendError):
    pass


def extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    data = json.loads(candidate)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def complete_json(backend: Backend, prompt: str, key: str, system: str | None = None) -> list[dict]:
    """Return `data[key]`, a list of objects. One retry carrying the error."""
    attempt = prompt
    for _ in range(2):
        text = backend.complete(attempt, system=system).text
        try:
            items = extract_json(text)[key]
            if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
                raise ValueError(f'"{key}" must be a list of objects')
            return items
        except (ValueError, KeyError) as e:
            error = f"{type(e).__name__}: {e}"
            attempt = (f"{prompt}\n\nYour previous reply was invalid ({error}). Reply with "
                       f'only a JSON object of the form {{"{key}": [...]}}.')
    raise InvalidOutput(f"no valid JSON with key '{key}' after retry ({error})")
