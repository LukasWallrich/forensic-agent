"""Offline backend: canned JSON so the pipeline runs without inference."""
from __future__ import annotations

import json
import re

from ..models import LLMResult
from .base import Backend


class MockBackend(Backend):
    name = "mock"

    def complete(self, prompt, system=None):
        if '"decisions"' in prompt:
            ids = list(dict.fromkeys(re.findall(r'"id": "([^"]+)"', prompt)))
            payload = {"decisions": [{"finding_id": i, "disposition": "confirmed",
                                      "rationale": "mock adjudication"} for i in ids]}
        elif '"claims"' in prompt:
            payload = {"claims": []}
        else:
            payload = {"findings": [{"check": "mock", "title": "Mock finding", "severity": 0,
                                     "detail": "Produced by the mock backend.", "evidence": ""}]}
        return LLMResult(text=json.dumps(payload), backend=self.name, model="mock")
