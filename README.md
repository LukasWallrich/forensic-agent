# forensic-agent

> ⚠️ **Vibe-coded prototype.** This repository was written almost entirely by
> AI coding agents (Claude Code, with a design review by Codex) in a single
> session, as an architecture sketch. The code has had little human review, the
> agents and checks are deliberately simplistic, and it has only been run on a
> fictional sample paper. **Do not rely on its output to assess real papers.**

**Credit:** the approach — parallel forensic agents (tortured phrases,
LLM-extracted claims verified by deterministic statistical tools such as GRIM
and p-value recomputation, a peer-review agent) followed by an adjudication
agent and human review — is that of the
[Forensic Metascience Agent](https://metascienceobservatory.org/forensic-metascience-agent)
by **Dan Elton / [The Metascience Observatory](https://metascienceobservatory.org)**.
This is an independent, unaffiliated re-sketch of that idea to explore a modular
code structure; it contains none of the original's code, its 44 tools, image
forensics or review app. Errors here are ours, not theirs.

A small, modular showcase: paper in → parallel analysis agents → adjudication →
report for human review.
See [DESIGN.md](DESIGN.md) for the architecture and its rationale.

```
uv venv && uv pip install -e '.[dev]'

forensic-agent list
forensic-agent validate pipelines/default.yaml --backend codex
forensic-agent run pipelines/default.yaml examples/sample_paper.md --backend claude
forensic-agent run pipelines/default.yaml examples/sample_paper.md --backend codex --model gpt-5.6-luna
forensic-agent run pipelines/default.yaml examples/sample_paper.md --backend openrouter --model anthropic/claude-sonnet-5
forensic-agent run pipelines/default.yaml examples/sample_paper.md --mock     # offline
```

Output goes to `runs/<timestamp>/report.md` and `report.json`.
Exit code: 0 complete · 2 partial (some agent failed) · 1 failed.

## The three things you can change

| To… | do this |
|---|---|
| choose which agents run, on which model | edit an orchestration YAML in `pipelines/` |
| adapt an agent | edit the prompt in `agents/<name>/AGENT.md` |
| add an agent | new folder `agents/<name>/` with `AGENT.md` (+ optional `agent.py` with `run(ctx)`) |
| add a statistical check | new folder `tools/<name>/` with `TOOL.md` + `tool.py` with `check(claim)`; list it under an agent's `tools:`. The TOOL.md body is injected into the extraction prompt, so the extractor learns about it automatically |
| add an LLM backend | one class in `forensic_agent/backends/` + one line in its `__init__.py` |

The core (`forensic_agent/`) knows nothing about specific agents or tools.

## Backends

- `claude` – Claude Code headless (`claude -p`), tools disabled
- `codex` – `codex exec`, read-only sandbox, empty working directory
- `openrouter` – HTTPS API; needs `OPENROUTER_API_KEY` and an explicit `--model`

Precedence: per-agent `backend:` in the YAML > `--backend/--model` > YAML default.

## Tests

```
pytest
```

## Licence

MIT — see [LICENSE](LICENSE).
