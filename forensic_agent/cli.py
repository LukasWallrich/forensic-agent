"""forensic-agent CLI: run / validate / list."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .backends import BACKENDS
from .config import ConfigError, load_pipeline, resolve_backend
from .ingest import load_paper
from .loader import load_agents, load_tools
from .models import BackendSpec
from .orchestrator import run_pipeline
from .report import write_report

EXIT = {"complete": 0, "failed": 1, "partial": 2}
USER_BACKENDS = sorted(b for b in BACKENDS if b != "mock")


def _cli_backend(args, pipeline) -> BackendSpec | None:
    if getattr(args, "mock", False):
        return BackendSpec("mock")
    if args.backend:
        return BackendSpec(args.backend, args.model)
    if args.model:  # --model alone applies to the YAML default backend
        if not pipeline.backend:
            raise ConfigError("--model given but no backend in YAML or --backend")
        return BackendSpec(pipeline.backend.name, args.model)
    return None


def _plan(pipeline, agents, cli) -> str:
    lines = [f"pipeline: {pipeline.name}"]
    for stage in pipeline.stages:
        lines.append(f"  stage {stage.name}:")
        for a in stage.agents:
            b = resolve_backend(a, pipeline, cli) if agents[a.use].needs_llm else None
            if agents[a.use].needs_llm and b is None:
                raise ConfigError(f"agent '{a.id}' needs an LLM: set `backend:` or pass --backend")
            backend = f"{b.name}" + (f" ({b.model})" if b.model else "") if b else "no LLM"
            tools = f"  tools={a.tools}" if a.tools else ""
            lines.append(f"    - {a.id} [{a.use}] -> {backend}{tools}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="forensic-agent", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("run", "validate"):
        p = sub.add_parser(name)
        p.add_argument("pipeline", help="orchestration YAML")
        if name == "run":
            p.add_argument("paper", help=".md, .txt or .pdf")
            p.add_argument("--out", help="output directory (default runs/<timestamp>)")
            p.add_argument("--mock", action="store_true", help="offline run with canned LLM output")
        p.add_argument("--backend", choices=USER_BACKENDS, help="overrides the YAML default")
        p.add_argument("--model", help="model for the chosen backend")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    try:
        agents, tools = load_agents(), load_tools()
        if args.cmd == "list":
            print("backends:", ", ".join(USER_BACKENDS), "(+ mock)")
            print("agents:")
            for a in agents.values():
                kind = "code" if a.run else "prompt-only"
                print(f"  {a.name:<18} [{kind}] {a.description}")
            print("tools:")
            for t in tools.values():
                print(f"  {t.name:<18} claim_type={t.claim_type} fields={t.fields}")
            return 0
        pipeline = load_pipeline(args.pipeline, agents, tools)
        cli = _cli_backend(args, pipeline)
        if cli and cli.name == "mock":  # --mock replaces every backend, incl. per-agent ones
            for stage in pipeline.stages:
                for a in stage.agents:
                    a.backend = None
        print(_plan(pipeline, agents, cli))
        if args.cmd == "validate":
            return 0
        paper = load_paper(args.paper)
    except (ConfigError, FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    result = run_pipeline(pipeline, paper, agents, tools, cli, log=print)
    out = write_report(result, args.out or f"runs/{datetime.now():%Y%m%d-%H%M%S}")
    print(f"status: {result.status} · {len(result.findings)} finding(s) · report: {out / 'report.md'}")
    return EXIT[result.status]


if __name__ == "__main__":
    sys.exit(main())
