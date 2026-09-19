"""Data contracts shared by the core, agents and tools."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SEVERITY = {0: "note", 1: "minor", 2: "moderate", 3: "major", 4: "critical"}
DISPOSITIONS = ("confirmed", "dismissed", "duplicate")
TOOL_STATUSES = ("pass", "fail", "not_applicable", "insufficient")


@dataclass
class Paper:
    source: str
    text: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class Finding:
    check: str
    title: str
    detail: str = ""
    evidence: str = ""  # verbatim quote from the paper
    severity: int = 1
    kind: str = "judgment"  # "computed" (deterministic tool) | "judgment" (LLM)
    # assigned by the core:
    id: str = ""
    agent: str = ""
    status: str = "open"  # open | confirmed | dismissed | duplicate
    duplicate_of: str | None = None
    rationale: str = ""
    evidence_found: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Decision:
    """An adjudicator's verdict on an existing finding."""

    finding_id: str
    disposition: str
    rationale: str = ""
    severity: int | None = None
    duplicate_of: str | None = None


@dataclass
class LLMResult:
    text: str
    backend: str
    model: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendSpec:
    name: str
    model: str | None = None


@dataclass
class AgentSpec:
    use: str
    id: str
    backend: BackendSpec | None = None
    tools: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageSpec:
    name: str
    agents: list[AgentSpec]


@dataclass
class PipelineSpec:
    name: str
    backend: BackendSpec | None
    stages: list[StageSpec]


@dataclass
class AgentDef:
    """A loaded agent folder: AGENT.md (+ optional agent.py)."""

    name: str
    description: str
    prompt: str
    dir: Path
    needs_llm: bool = True
    run: Any = None  # callable(ctx) from agent.py, or None for prompt-only


@dataclass
class ToolDef:
    """A loaded tool folder: TOOL.md + tool.py."""

    name: str
    claim_type: str
    fields: list[str]
    doc: str
    check: Any  # callable(claim: dict) -> dict


@dataclass
class AgentRun:
    """Coverage record: what happened when an agent ran."""

    agent: str
    stage: str
    status: str  # ok | error
    backend: str | None = None
    model: str | None = None
    n_findings: int = 0
    seconds: float = 0.0
    error: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    pipeline: str
    paper: str
    status: str  # complete | partial | failed
    findings: list[Finding]
    coverage: list[AgentRun]
    mock: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
