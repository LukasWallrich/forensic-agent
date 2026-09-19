"""Write report.json and a human-readable report.md."""
from __future__ import annotations

import json
from pathlib import Path

from .models import SEVERITY, RunResult


def write_report(result: RunResult, out_dir: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(result.to_dict(), indent=2))
    (out / "report.md").write_text(render_markdown(result))
    return out


def render_markdown(r: RunResult) -> str:
    lines = [f"# Forensic report — {Path(r.paper).name}", ""]
    if r.mock:
        lines += ["> **MOCK RUN** — produced by the mock backend, not a real analysis.", ""]
    lines += [f"Pipeline `{r.pipeline}` · run status **{r.status}**", "",
              "Findings are inconsistencies flagged for human review, not verdicts.", ""]
    lines += [f"> Warning: {w}" for w in r.warnings]

    lines += ["## Coverage", "", "| agent | stage | backend | status | findings | s |",
              "|---|---|---|---|---|---|"]
    for c in r.coverage:
        backend = "/".join(x for x in (c.backend, c.model) if x) or "—"
        status = c.status if not c.error else f"**error**: {c.error}"
        lines.append(f"| {c.agent} | {c.stage} | {backend} | {status} | {c.n_findings} | {c.seconds} |")
    for c in r.coverage:
        lines += [f"- {c.agent}: {n}" for n in c.notes]

    active = sorted((f for f in r.findings if f.status in ("open", "confirmed")),
                    key=lambda f: -f.severity)
    lines += ["", f"## Findings ({len(active)})", ""]
    for f in active:
        lines += [f"### [{f.severity} {SEVERITY[f.severity]}] {f.title}",
                  f"`{f.id}` · {f.check} · {f.kind} · {f.status}", "", f.detail, ""]
        if f.evidence:
            flag = "" if f.evidence_found else " *(quote not found verbatim in paper)*"
            lines += [f"> {f.evidence}{flag}", ""]
        if f.rationale:
            lines += [f"*Adjudicator:* {f.rationale}", ""]
    set_aside = [f for f in r.findings if f.status in ("dismissed", "duplicate")]
    if set_aside:
        lines += ["## Set aside", ""]
        lines += [f"- `{f.id}` {f.title} — {f.status}"
                  + (f" of `{f.duplicate_of}`" if f.duplicate_of else "")
                  + (f": {f.rationale}" if f.rationale else "") for f in set_aside]
    return "\n".join(lines) + "\n"
