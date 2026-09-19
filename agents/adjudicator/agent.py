"""Turns the LLM's verdicts into Decisions; the core validates and applies them."""
from forensic_agent.models import Decision


def to_severity(value):
    try:
        return max(0, min(4, int(value)))
    except (TypeError, ValueError):
        return None


def run(ctx):
    if not ctx.findings:
        ctx.notes.append("no findings to adjudicate")
        return []
    decisions = []
    for item in ctx.llm_json(ctx.render(), "decisions"):
        if not item.get("finding_id"):
            continue
        decisions.append(Decision(
            finding_id=str(item["finding_id"]),
            disposition=str(item.get("disposition", "")).strip().lower(),
            rationale=str(item.get("rationale") or ""),
            severity=to_severity(item.get("severity")),
            duplicate_of=str(item["duplicate_of"]) if item.get("duplicate_of") else None))
    ctx.notes.append(f"{len(decisions)} decision(s) for {len(ctx.findings)} finding(s)")
    return decisions
