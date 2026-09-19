"""Run stages sequentially, agents within a stage in parallel."""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .backends import Backend, make_backend
from .config import resolve_backend
from .llm import complete_json
from .models import (DISPOSITIONS, AgentDef, AgentRun, AgentSpec, BackendSpec, Decision,
                     Finding, Paper, PipelineSpec, RunResult, ToolDef)

FINDINGS_FORMAT = """Reply with only a JSON object:
{"findings": [{"check": "<short slug>", "title": "...", "detail": "...",
  "evidence": "<verbatim quote from the paper>", "severity": <0-4>}]}
Severity: 0 note, 1 minor, 2 moderate, 3 major, 4 critical. Use an empty list if nothing is wrong."""


@dataclass
class Context:
    """Everything an agent may use. Earlier-stage results are a read-only snapshot."""

    paper: Paper
    findings: tuple[Finding, ...]
    coverage: tuple[AgentRun, ...]
    spec: AgentSpec
    agent: AgentDef
    tools: dict[str, ToolDef]
    backend: Backend | None
    notes: list[str] = field(default_factory=list)

    @property
    def options(self) -> dict[str, Any]:
        return self.spec.options

    @property
    def prompt(self) -> str:
        return self.agent.prompt

    @property
    def dir(self) -> Path:
        return self.agent.dir

    def render(self, template: str | None = None, **extra: str) -> str:
        """Fill {{paper}}, {{findings}}, {{coverage}}, {{options.x}} and extras."""
        values = {
            "paper": self.paper.text,
            "findings": json.dumps([f.to_dict() for f in self.findings], indent=1),
            "coverage": json.dumps([{"agent": c.agent, "status": c.status, "error": c.error}
                                    for c in self.coverage]),
            **{f"options.{k}": str(v) for k, v in self.options.items()}, **extra}
        return re.sub(r"\{\{\s*([\w.]+)\s*\}\}",
                      lambda m: values.get(m.group(1), ""), template or self.prompt)

    def llm_json(self, prompt: str, key: str) -> list[dict]:
        if self.backend is None:
            raise RuntimeError(f"agent '{self.spec.id}' needs an LLM but no backend is configured")
        return complete_json(self.backend, prompt, key)


def default_run(ctx: Context) -> list[Finding]:
    """Behaviour of a prompt-only agent (AGENT.md without agent.py)."""
    items = ctx.llm_json(ctx.render() + "\n\n" + FINDINGS_FORMAT, "findings")
    return [finding_from_dict(i) for i in items]


def finding_from_dict(d: dict, kind: str = "judgment") -> Finding:
    try:
        severity = max(0, min(4, int(d.get("severity", 1))))
    except (TypeError, ValueError):
        severity = 1
    return Finding(check=str(d.get("check", "unspecified")), title=str(d.get("title", "")),
                   detail=str(d.get("detail", "")), evidence=str(d.get("evidence", "")),
                   severity=severity, kind=kind)


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def apply_decisions(findings: list[Finding], decisions: list[Decision]) -> list[str]:
    """Apply adjudication centrally; invalid decisions are reported, not applied."""
    by_id, problems = {f.id: f for f in findings}, []
    for d in decisions:
        f = by_id.get(d.finding_id)
        if f is None or d.disposition not in DISPOSITIONS:
            problems.append(f"ignored decision on '{d.finding_id}' ({d.disposition})")
            continue
        if d.disposition == "duplicate" and (d.duplicate_of not in by_id or d.duplicate_of == f.id):
            problems.append(f"ignored duplicate decision on '{f.id}': bad target")
            continue
        f.status, f.rationale = d.disposition, d.rationale
        f.duplicate_of = d.duplicate_of if d.disposition == "duplicate" else None
        if d.severity is not None:
            f.severity = max(0, min(4, int(d.severity)))
    return problems


def run_pipeline(pipeline: PipelineSpec, paper: Paper, agents: dict[str, AgentDef],
                 tools: dict[str, ToolDef], cli_backend: BackendSpec | None = None,
                 log: Callable[[str], None] = lambda s: None) -> RunResult:
    findings: list[Finding] = []
    coverage: list[AgentRun] = []
    paper_norm = _normalise(paper.text)

    def run_agent(stage: str, spec: AgentSpec):
        agent = agents[spec.use]
        bspec = resolve_backend(spec, pipeline, cli_backend) if agent.needs_llm else None
        record = AgentRun(agent=spec.id, stage=stage, status="ok",
                          backend=bspec.name if bspec else None,
                          model=bspec.model if bspec else None)
        start, out = time.time(), []
        try:
            ctx = Context(paper=paper, findings=tuple(findings), coverage=tuple(coverage),
                          spec=spec, agent=agent, backend=make_backend(bspec) if bspec else None,
                          tools={t: tools[t] for t in spec.tools})
            out = list((agent.run or default_run)(ctx))
            record.notes = ctx.notes
        except Exception as e:  # one agent failing must not sink the run
            record.status, record.error = "error", f"{type(e).__name__}: {e}"
        record.seconds = round(time.time() - start, 1)
        return record, out

    for stage in pipeline.stages:
        log(f"stage '{stage.name}': {', '.join(a.id for a in stage.agents)}")
        with ThreadPoolExecutor(max_workers=min(8, len(stage.agents))) as pool:
            results = list(pool.map(lambda s: run_agent(stage.name, s), stage.agents))
        decisions = []
        for record, out in results:  # deterministic merge order = YAML order
            new = [o for o in out if isinstance(o, Finding)]
            decisions += [o for o in out if isinstance(o, Decision)]
            for n, f in enumerate(new, 1):
                f.id, f.agent = f"{record.agent}-{n}", record.agent
                f.evidence_found = _normalise(f.evidence) in paper_norm if f.evidence else None
            record.n_findings = len(new)
            findings += new
            coverage.append(record)
            log(f"  {record.agent}: {record.status}, {len(new)} finding(s), {record.seconds}s"
                + (f" — {record.error}" if record.error else ""))
        for problem in apply_decisions(findings, decisions):
            log(f"  {problem}")

    errors = sum(c.status == "error" for c in coverage)
    status = "complete" if not errors else "failed" if errors == len(coverage) else "partial"
    return RunResult(pipeline=pipeline.name, paper=paper.source, status=status,
                     findings=findings, coverage=coverage, warnings=list(paper.warnings),
                     mock=any(c.backend == "mock" for c in coverage))
