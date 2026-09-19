"""Discover skill-style agent and tool folders (markdown + optional code)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

from .models import AgentDef, ToolDef

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"
TOOLS_DIR = ROOT / "tools"


def parse_markdown(path: Path) -> tuple[dict, str]:
    """Split `---` YAML frontmatter from the markdown body."""
    text = path.read_text()
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing frontmatter")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front) or {}, body.strip()


def _load_function(path: Path, func: str):
    spec = importlib.util.spec_from_file_location(f"_fa_{path.parent.name}_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, func):
        raise ValueError(f"{path}: must define {func}()")
    return getattr(module, func)


def load_agents(root: Path = AGENTS_DIR) -> dict[str, AgentDef]:
    agents = {}
    for md in sorted(root.glob("*/AGENT.md")):
        meta, body = parse_markdown(md)
        code = md.parent / "agent.py"
        agents[meta.get("name", md.parent.name)] = AgentDef(
            name=meta.get("name", md.parent.name),
            description=meta.get("description", ""),
            prompt=body, dir=md.parent,
            needs_llm=bool(meta.get("needs_llm", True)),
            run=_load_function(code, "run") if code.exists() else None)
    return agents


def load_tools(root: Path = TOOLS_DIR) -> dict[str, ToolDef]:
    tools = {}
    for md in sorted(root.glob("*/TOOL.md")):
        meta, body = parse_markdown(md)
        name = meta.get("name", md.parent.name)
        tools[name] = ToolDef(
            name=name, claim_type=meta.get("claim_type", name),
            fields=list(meta.get("fields", [])), doc=body,
            check=_load_function(md.parent / "tool.py", "check"))
    return tools
