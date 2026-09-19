import pytest

from forensic_agent.config import ConfigError, load_pipeline, resolve_backend
from forensic_agent.llm import InvalidOutput, complete_json, extract_json
from forensic_agent.models import (AgentDef, AgentSpec, BackendSpec, Decision, Finding,
                                   LLMResult, Paper, PipelineSpec, StageSpec)
from forensic_agent.orchestrator import apply_decisions, run_pipeline

AGENTS = {"a": None, "b": None}
TOOLS = {"grim": None}


def write(tmp_path, text):
    p = tmp_path / "p.yaml"
    p.write_text(text)
    return str(p)


def test_pipeline_loads_and_resolves_backends(tmp_path):
    path = write(tmp_path, """
schema_version: 1
backend: {name: claude}
stages:
  - name: s1
    agents:
      - use: a
        tools: [grim]
      - use: a
        id: a2
        backend: {name: openrouter, model: x/y}
""")
    p = load_pipeline(path, AGENTS, TOOLS)
    first, second = p.stages[0].agents
    cli = BackendSpec("codex", "m")
    assert resolve_backend(first, p, None).name == "claude"
    assert resolve_backend(first, p, cli) == cli
    assert resolve_backend(second, p, cli).model == "x/y"  # per-agent wins


@pytest.mark.parametrize("body, msg", [
    ("schema_version: 1\nstages:\n - name: s\n   agents:\n    - use: a\n      modle: x", "unknown key"),
    ("schema_version: 1\nstages:\n - name: s\n   agents:\n    - use: zzz", "unknown agent"),
    ("schema_version: 1\nstages:\n - name: s\n   agents:\n    - use: a\n      tools: [nope]", "unknown tool"),
    ("schema_version: 1\nstages:\n - name: s\n   agents:\n    - use: a\n    - use: a", "duplicate agent id"),
    ("schema_version: 1\nbackend: {name: gemini}\nstages:\n - name: s\n   agents:\n    - use: a", "unknown backend"),
    ("schema_version: 9\nstages: []", "schema_version"),
])
def test_pipeline_rejects_mistakes(tmp_path, body, msg):
    with pytest.raises(ConfigError, match=msg):
        load_pipeline(write(tmp_path, body), AGENTS, TOOLS)


class Scripted:
    def __init__(self, *replies):
        self.replies = list(replies)

    def complete(self, prompt, system=None):
        return LLMResult(text=self.replies.pop(0), backend="fake")


def test_json_extraction_and_retry():
    assert extract_json('Sure!\n```json\n{"findings": []}\n```') == {"findings": []}
    assert complete_json(Scripted("nonsense", '{"findings": [{"a": 1}]}'), "p", "findings") == [{"a": 1}]
    with pytest.raises(InvalidOutput):
        complete_json(Scripted("x", '{"other": []}'), "p", "findings")


def test_apply_decisions_validates_targets():
    fs = [Finding(check="c", title="1", id="x-1"), Finding(check="c", title="2", id="x-2")]
    problems = apply_decisions(fs, [
        Decision("x-2", "duplicate", duplicate_of="x-1"),
        Decision("x-1", "confirmed", severity=9),
        Decision("nope", "confirmed"),
        Decision("x-1", "duplicate", duplicate_of="x-1")])
    assert fs[1].status == "duplicate" and fs[1].duplicate_of == "x-1"
    assert fs[0].status == "confirmed" and fs[0].severity == 4
    assert len(problems) == 2


def test_failing_agent_is_recorded_and_visible_downstream(tmp_path):
    seen = {}

    def boom(ctx):
        raise ValueError("kaput")

    def good(ctx):
        return [Finding(check="c", title="t", evidence="Hello   world")]

    def late(ctx):
        seen["coverage"] = {c.agent: c.status for c in ctx.coverage}
        seen["ids"] = [f.id for f in ctx.findings]
        return []

    agents = {n: AgentDef(n, "", "", tmp_path, needs_llm=False, run=f)
              for n, f in [("boom", boom), ("good", good), ("late", late)]}
    pipeline = PipelineSpec("t", None, [
        StageSpec("one", [AgentSpec("boom", "boom"), AgentSpec("good", "good")]),
        StageSpec("two", [AgentSpec("late", "late")])])
    result = run_pipeline(pipeline, Paper("x", "hello\nworld"), agents, {})
    assert result.status == "partial"
    assert seen == {"coverage": {"boom": "error", "good": "ok"}, "ids": ["good-1"]}
    assert result.findings[0].evidence_found is True
