# forensic-agent — modular design (v2, after review by Codex gpt-6-astra)

> Vibe-coded prototype — see the README. Approach credited to Dan Elton / The Metascience Observatory.

A small showcase rebuild of the Metascience Observatory's forensic metascience
agent (paper in → parallel analysis agents → adjudication → report).
Goal: demonstrate a *simple modular architecture*, not feature parity. The
agents themselves are deliberately simple; real ones can be ported in later.

## Principles

1. **Agents and tools are skill-style folders**: a top-level markdown file
   (frontmatter = metadata, body = prompt/documentation) plus optional code.
   Adapting an agent = editing markdown. Adding one = adding a folder.
2. **Backends are the only in-package plug-in axis** (`claude`, `codex`,
   `openrouter`, `mock`): one small class each.
3. **The orchestration YAML is the only wiring**: which agents, which stage,
   which tools / backend / model. Strictly validated.
4. **One data contract**: agents return `Finding`s (and the adjudicator
   returns `Decision`s about findings). The orchestrator applies decisions
   centrally; original findings are preserved.
5. **LLMs extract and judge; code computes.** The model never does the
   statistics; it extracts structured claims that deterministic tools check.

Why folders rather than MCP servers? MCP fits when *the model* decides to call
tools inside an agentic loop. Here the code calls the checks deterministically,
and the OpenRouter backend has no MCP client. A folder tool is a pure function,
so exposing `tools/` as an MCP server later is a thin adapter, not a redesign.

## Layout

```
forensic_agent/            # core: knows nothing about specific agents/tools
  cli.py  config.py  models.py  loader.py  orchestrator.py
  ingest.py  report.py  llm.py (JSON extraction + validation + 1 retry)
  backends/  base.py  claude_cli.py  codex_cli.py  openrouter.py  mock.py
agents/
  peer_review/       AGENT.md                      # prompt-only agent
  tortured_phrases/  AGENT.md  agent.py  phrases.tsv   # code-only agent
  tool_expert/       AGENT.md  agent.py            # LLM extraction + tools
  adjudicator/       AGENT.md  agent.py            # emits Decisions
tools/
  grim/  p_recompute/  percent_check/   each: TOOL.md + tool.py
pipelines/default.yaml
examples/sample_paper.md
tests/
```

## Agent folder

```markdown
---
name: peer_review
description: Reads the paper for contradictions and methodological flaws.
needs_llm: true
---
You are a forensic peer reviewer ... {{paper}} ... {{findings}}
```

- **No `agent.py`** → default behaviour: render the body (`{{paper}}`,
  `{{findings}}`, `{{options.x}}`), call the LLM, validate the JSON against
  the findings schema, return `Finding`s.
- **With `agent.py`** → `def run(ctx) -> list[Finding | Decision]`. `ctx` gives
  `paper`, `findings` (earlier stages), `coverage` (which agents ran/failed),
  `prompt` (the markdown body), `render()`, `llm_json()`, `tools`, `options`,
  `dir` (for data files like `phrases.tsv`).

## Tool folder

`TOOL.md` frontmatter: `name`, `claim_type`, `fields` (required claim fields).
Its body describes what to extract; **it is injected into the tool-expert's
extraction prompt**, so adding a tool folder automatically teaches the
extractor about it. `tool.py`: `def check(claim: dict) -> dict` returning
`status` ∈ `pass | fail | not_applicable | insufficient` plus `detail` and
`computed`. The tool-expert agent validates required fields before calling. Reported
numbers are passed as **strings** so precision (decimals) is preserved.

## Data contracts

```python
Finding:  id (f"{agent_id}-{n}", assigned by core), agent, check, kind
          ("computed" | "judgment"), severity 0-4, title, detail, evidence
          (verbatim quote; core flags quotes not found in the paper),
          status = "open", duplicate_of, rationale
Decision: finding_id, disposition (confirmed|dismissed|duplicate),
          severity?, duplicate_of?, rationale
LLMResult: text, model, backend, usage
```

Severity ladder: 0 note · 1 minor · 2 moderate · 3 major · 4 critical.
A finding is an inconsistency worth human review, never a misconduct verdict.

## Backends

`Backend(model).complete(prompt, system=None) -> LLMResult`, with a deadline.
Used as plain completion engines, not agents: paper text is untrusted.
- `claude`: `claude -p --output-format json --tools ""`, run in an empty temp dir
- `codex`: `codex exec --sandbox read-only --skip-git-repo-check -o file`, empty temp dir; system text is prepended
- `openrouter`: HTTPS chat/completions, `OPENROUTER_API_KEY`, model required, records actual provider
- `mock`: canned responses for offline runs/tests; reports are labelled MOCK

Structured output: local schema validation, one retry carrying the validation
error, then a typed failure. (Native `--json-schema` / `--output-schema` /
`response_format` are a later per-backend optimisation.)

## Orchestration YAML (strict: unknown keys are errors)

```yaml
schema_version: 1
name: default
backend: {name: claude}             # default; CLI --backend/--model override
stages:
  - name: analysis                  # agents within a stage run in parallel
    agents:
      - use: tortured_phrases
      - use: tool_expert
        tools: [grim, p_recompute, percent_check]
      - use: peer_review
        id: reviewer_b              # optional; lets one agent type run twice
        backend: {name: openrouter, model: anthropic/claude-sonnet-5}
        options: {focus: statistics}
  - name: adjudication
    agents:
      - use: adjudicator
```

Backend precedence: per-agent YAML > CLI flags > YAML default. An override
replaces the whole `{name, model}` pair (no model inheritance across providers).

## CLI

```
forensic-agent run PIPELINE.yaml PAPER --backend claude|codex|openrouter [--model M] [--out DIR] [--mock]
forensic-agent validate PIPELINE.yaml [--backend ...]   # print resolved plan, no inference
forensic-agent list                                     # backends / agents / tools
```

## Failure handling

Agent errors are caught, recorded in `coverage`, passed to later stages and
shown in the report ("not run" ≠ "nothing found"). Run status is
`complete | partial | failed`; exit code 0 / 2 / 1. Oversized papers are
rejected rather than silently truncated.

## Out of scope (v0)

DOI fetching, OCR, image forensics, located evidence spans (page/table cell),
database, review web app, YAML-driven third-party plugin imports.
