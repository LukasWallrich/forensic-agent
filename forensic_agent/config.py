"""Orchestration YAML -> validated PipelineSpec. Unknown keys are errors."""
from __future__ import annotations

from pathlib import Path

import yaml

from .backends import BACKENDS
from .models import AgentSpec, BackendSpec, PipelineSpec, StageSpec

SCHEMA_VERSION = 1


class ConfigError(ValueError):
    pass


def _keys(d, allowed: set, required: set, where: str) -> None:
    if not isinstance(d, dict):
        raise ConfigError(f"{where}: expected a mapping")
    if extra := set(d) - allowed:
        raise ConfigError(f"{where}: unknown key(s) {sorted(extra)}; allowed: {sorted(allowed)}")
    if missing := required - set(d):
        raise ConfigError(f"{where}: missing key(s) {sorted(missing)}")


def _backend(d, where: str) -> BackendSpec:
    _keys(d, {"name", "model"}, {"name"}, where)
    if d["name"] not in BACKENDS:
        raise ConfigError(f"{where}: unknown backend '{d['name']}'; known: {sorted(BACKENDS)}")
    return BackendSpec(d["name"], d.get("model"))


def load_pipeline(path: str, agents: dict, tools: dict) -> PipelineSpec:
    raw = yaml.safe_load(Path(path).read_text())
    _keys(raw, {"schema_version", "name", "backend", "stages"}, {"schema_version", "stages"}, path)
    if raw["schema_version"] != SCHEMA_VERSION:
        raise ConfigError(f"{path}: schema_version must be {SCHEMA_VERSION}")
    stages, seen = [], set()
    for si, s in enumerate(raw["stages"] or []):
        where = f"stages[{si}]"
        _keys(s, {"name", "agents"}, {"name", "agents"}, where)
        specs = []
        for ai, a in enumerate(s["agents"] or []):
            w = f"{where}.agents[{ai}]"
            _keys(a, {"use", "id", "backend", "tools", "options"}, {"use"}, w)
            if a["use"] not in agents:
                raise ConfigError(f"{w}: unknown agent '{a['use']}'; known: {sorted(agents)}")
            if unknown := [t for t in a.get("tools", []) if t not in tools]:
                raise ConfigError(f"{w}: unknown tool(s) {unknown}; known: {sorted(tools)}")
            agent_id = a.get("id", a["use"])
            if agent_id in seen:
                raise ConfigError(f"{w}: duplicate agent id '{agent_id}' (set a unique `id:`)")
            seen.add(agent_id)
            specs.append(AgentSpec(
                use=a["use"], id=agent_id, tools=list(a.get("tools", [])),
                options=dict(a.get("options") or {}),
                backend=_backend(a["backend"], f"{w}.backend") if "backend" in a else None))
        if not specs:
            raise ConfigError(f"{where}: no agents")
        stages.append(StageSpec(s["name"], specs))
    if not stages:
        raise ConfigError(f"{path}: no stages")
    default = _backend(raw["backend"], "backend") if "backend" in raw else None
    return PipelineSpec(raw.get("name", Path(path).stem), default, stages)


def resolve_backend(agent: AgentSpec, pipeline: PipelineSpec,
                    cli: BackendSpec | None) -> BackendSpec | None:
    """Precedence: per-agent YAML > CLI flags > YAML default."""
    return agent.backend or cli or pipeline.backend
