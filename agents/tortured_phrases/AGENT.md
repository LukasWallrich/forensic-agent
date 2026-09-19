---
name: tortured_phrases
description: Flags known "tortured phrases" (paraphrasing-tool synonyms of established terms) by simple dictionary lookup.
needs_llm: false
---
# Tortured phrases

Tortured phrases are odd synonyms of established technical terms ("counterfeit
consciousness" for "artificial intelligence"). They typically appear when text
is run through a paraphrasing tool to disguise plagiarism or generated content
(Cabanac, Labbé & Magazinov, 2021).

## Approach

No LLM is involved. `agent.py` reads `phrases.tsv` from this folder and does a
case-insensitive, whitespace-tolerant search of the paper text. It emits one
finding per distinct phrase (check `tortured_phrase`, kind `computed`,
severity 2) with the sentence in which the phrase first occurs as verbatim
evidence; further occurrences are only counted in the detail.

A hit is a signal worth human review, not proof: a phrase can occur
legitimately (e.g. in a paper *about* tortured phrases).

## Extending the list

Add a line to `phrases.tsv`: `tortured phrase<TAB>expected term`. Lines starting
with `#` and blank lines are ignored. Prefer multi-word phrases that are very
unlikely in normal scientific prose; short or ambiguous entries produce false
positives.
