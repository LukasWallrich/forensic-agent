"""Dictionary lookup of known tortured phrases. No LLM."""
import re

from forensic_agent.models import Finding


def load_phrases(path):
    """phrases.tsv -> [(phrase, expected term)]; '#' comments and blanks ignored."""
    pairs = []
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "\t" in line:
            phrase, expected = line.split("\t", 1)
            pairs.append((phrase.strip(), expected.strip()))
    return pairs


def sentence_around(text, start, end, window=150):
    """The sentence containing text[start:end], verbatim; capped to a window."""
    left = max((m.end() for m in re.finditer(r"[.!?]\s+|\n\s*\n", text[:start])), default=0)
    stop = re.search(r"[.!?](\s|$)|\n\s*\n", text[end:])
    right = end + stop.start() + 1 if stop else len(text)
    if right - left > 2 * window:
        left, right = max(left, start - window // 2), min(right, end + window // 2)
    return text[left:right].strip()


def run(ctx):
    text, findings = ctx.paper.text, []
    for phrase, expected in load_phrases(ctx.dir / "phrases.tsv"):
        pattern = r"(?<!\w)" + r"[\s-]+".join(map(re.escape, re.split(r"[\s-]+", phrase))) + r"(?!\w)"
        hits = list(re.finditer(pattern, text, re.I))
        if not hits:
            continue
        findings.append(Finding(
            check="tortured_phrase", kind="computed", severity=2,
            title=f'Tortured phrase: "{phrase}"',
            detail=(f'"{phrase}" is a known paraphrasing-tool substitute for "{expected}" '
                    f"({len(hits)} occurrence(s))."),
            evidence=sentence_around(text, hits[0].start(), hits[0].end())))
    ctx.notes.append(f"{len(findings)} tortured phrase(s) found")
    return findings
