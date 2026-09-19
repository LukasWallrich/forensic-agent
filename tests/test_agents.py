"""Agent folders run end-to-end through the real loader and orchestrator (fake LLM)."""
import json

import pytest

from forensic_agent import orchestrator
from forensic_agent.loader import ROOT, load_agents
from forensic_agent.models import (AgentSpec, BackendSpec, LLMResult, Paper, PipelineSpec,
                                   StageSpec, ToolDef)

GRIM_QUOTE = "the control group (n = 28) reported a mean exam\nstress of 5.19"
CLAIMS = {"claims": [
    {"type": "grim", "mean": "5.19", "n": "28", "quote": GRIM_QUOTE},                  # fail
    {"type": "grim", "mean": "4.53", "n": "32", "quote": "journaling group (n = 32)"},  # pass
    {"type": "grim", "mean": "5.25", "quote": "a mean gratitude of\n5.25"},             # no n
]}
DECISIONS = {"decisions": [
    {"finding_id": "tool_expert-1", "disposition": "confirmed", "severity": 4,
     "duplicate_of": None, "rationale": "Mean is impossible for n = 28."},
    {"finding_id": "second_expert-1", "disposition": "duplicate", "severity": "n/a",
     "duplicate_of": "tool_expert-1", "rationale": "Same mean."},
    {"disposition": "dismissed", "rationale": "no finding_id: skipped"},
]}


class FakeBackend:
    prompts: list[str] = []

    def complete(self, prompt, system=None):
        FakeBackend.prompts.append(prompt)
        canned = CLAIMS if '"claims"' in prompt else DECISIONS if '"decisions"' in prompt else {}
        return LLMResult(text=json.dumps(canned), backend="fake")


def grim_check(claim):
    """Minimal inline GRIM so the test does not depend on the tools/ folders."""
    mean, n = claim["mean"], int(claim["n"])
    decimals = len(mean.split(".")[1]) if "." in mean else 0
    ok = any(f"{k / n:.{decimals}f}" == mean for k in range(round(float(mean) * n) - 1,
                                                            round(float(mean) * n) + 2))
    return {"status": "pass" if ok else "fail", "computed": {},
            "detail": f"mean {mean} is {'possible' if ok else 'impossible'} with n = {n}"}


@pytest.fixture
def paper():
    path = ROOT / "examples" / "sample_paper.md"
    return Paper(source=str(path), text=path.read_text())


@pytest.fixture
def agents():
    return load_agents()


@pytest.fixture
def tools():
    return {"grim": ToolDef(name="grim", claim_type="grim", fields=["mean", "n"],
                            doc="GRIM: means of integer data.", check=grim_check)}


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    FakeBackend.prompts = []
    monkeypatch.setattr(orchestrator, "make_backend", lambda spec: FakeBackend())


def pipeline(*stages):
    return PipelineSpec(name="test", backend=BackendSpec("fake"),
                        stages=[StageSpec(f"stage{i}", list(s)) for i, s in enumerate(stages)])


def test_agents_load(agents):
    assert {"peer_review", "tortured_phrases", "tool_expert", "adjudicator"} <= set(agents)
    assert agents["peer_review"].run is None
    assert agents["tortured_phrases"].needs_llm is False
    assert '"claims"' in agents["tool_expert"].prompt and "{{tool_docs}}" in agents["tool_expert"].prompt
    assert '"decisions"' in agents["adjudicator"].prompt


def test_tortured_phrases_finds_planted_phrase(agents, paper):
    spec = pipeline([AgentSpec(use="tortured_phrases", id="tortured_phrases")])
    result = orchestrator.run_pipeline(spec, paper, agents, {})
    assert result.status == "complete"
    assert not FakeBackend.prompts  # no LLM involved
    [finding] = result.findings
    assert finding.check == "tortured_phrase" and finding.kind == "computed"
    assert "colossal information" in finding.evidence
    assert "big data" in finding.detail
    assert finding.evidence_found is True


def test_tool_expert_routes_claims(agents, tools, paper):
    spec = pipeline([AgentSpec(use="tool_expert", id="tool_expert", tools=["grim"])])
    result = orchestrator.run_pipeline(spec, paper, agents, tools)
    assert result.coverage[0].error is None
    [finding] = result.findings
    assert (finding.check, finding.kind, finding.severity) == ("grim", "computed", 2)
    assert finding.evidence == GRIM_QUOTE and finding.evidence_found is True
    assert result.coverage[0].notes == ["3 claims extracted: 1 fail, 1 pass, 1 insufficient"]
    assert "GRIM: means of integer data." in FakeBackend.prompts[0]  # tool docs injected


def test_tool_expert_without_tools(agents, paper):
    spec = pipeline([AgentSpec(use="tool_expert", id="tool_expert")])
    result = orchestrator.run_pipeline(spec, paper, agents, {})
    assert result.findings == [] and result.coverage[0].notes and not FakeBackend.prompts


def test_adjudicator_decisions_are_applied(agents, tools, paper):
    spec = pipeline([AgentSpec(use="tool_expert", id="tool_expert", tools=["grim"]),
                     AgentSpec(use="tool_expert", id="second_expert", tools=["grim"])],
                    [AgentSpec(use="adjudicator", id="adjudicator")])
    result = orchestrator.run_pipeline(spec, paper, agents, tools)
    assert result.status == "complete", [c.error for c in result.coverage]
    first, second = result.findings
    assert (first.status, first.severity) == ("confirmed", 4)
    assert (second.status, second.duplicate_of, second.severity) == ("duplicate", "tool_expert-1", 2)
    assert "tool_expert-1" in FakeBackend.prompts[-1]  # findings were rendered into the prompt


def test_adjudicator_without_findings(agents, paper):
    spec = pipeline([AgentSpec(use="adjudicator", id="adjudicator")])
    result = orchestrator.run_pipeline(spec, paper, agents, {})
    assert result.status == "complete" and not FakeBackend.prompts
