"""LLM extracts claims; deterministic tools check them. The model never computes."""
from collections import Counter

from forensic_agent.models import Finding


def describe(tool):
    fields = ", ".join(tool.fields) or "(none)"
    return f"### claim type `{tool.claim_type}`\nRequired fields: {fields}\n\n{tool.doc}"


def check_claim(tool, claim):
    """Run one tool on one claim; never raises."""
    missing = [f for f in tool.fields if claim.get(f) in (None, "")]
    if missing:
        return {"status": "insufficient", "detail": f"missing field(s): {', '.join(missing)}"}
    try:
        result = tool.check(claim)
        return result if isinstance(result, dict) else {"status": "insufficient",
                                                        "detail": "tool returned no result"}
    except Exception as e:
        return {"status": "insufficient", "detail": f"{type(e).__name__}: {e}"}


def run(ctx):
    if not ctx.tools:
        ctx.notes.append("no tools configured; nothing to check")
        return []
    tool_docs = "\n\n".join(describe(t) for t in ctx.tools.values())
    claims = ctx.llm_json(ctx.render(tool_docs=tool_docs), "claims")

    findings, statuses = [], Counter()
    for claim in claims:
        tools = [t for t in ctx.tools.values() if t.claim_type == claim.get("type")]
        if not tools:
            statuses["unroutable"] += 1
        for tool in tools:
            result = check_claim(tool, claim)
            status = result.get("status", "insufficient")
            statuses[status] += 1
            if status == "fail":
                computed = result.get("computed") or {}
                findings.append(Finding(
                    check=tool.name, kind="computed",
                    severity=3 if computed.get("decision_error") else 2,
                    title=f"{tool.name}: reported value is inconsistent",
                    detail=str(result.get("detail", "")),
                    evidence=str(claim.get("quote", ""))))
    ctx.notes.append(f"{len(claims)} claims extracted: "
                     + (", ".join(f"{n} {s}" for s, n in statuses.items()) or "nothing checked"))
    return findings
