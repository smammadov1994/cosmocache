#!/usr/bin/env python3
"""Haiku-backed proposer for creature distillation (Phase 3).

Given a creature markdown file, return a distilled version that:
- preserves the YAML frontmatter (name, abilities) verbatim
- collapses repetitive journal entries into one Distilled Wisdom block
- keeps every distinct factual claim or technique
- targets <=50% of the original word count

The caller validates the result against score_planet — if the distilled
version loses a fact, the gate rejects it and we keep the original.
"""
from __future__ import annotations


PROMPT_TEMPLATE = """\
You are distilling a creature's journal in the cosmocache universe.

Rules — follow exactly:
1. Preserve the YAML frontmatter block (between the two --- lines) verbatim.
   Do not change the name, abilities, or any other frontmatter field.
2. Replace repetitive Journal entries with a tight `## Distilled Wisdom`
   section: bullet points of every distinct fact, technique, gotcha, or
   pattern that appears in the journal.
3. Keep ALL distinct factual claims, code snippets, command names, and
   library/API names. Only collapse repetition, not content.
4. After the Distilled Wisdom section, you MAY keep a short `## Journal`
   section with the most recent 1-2 entries verbatim — but only if they
   describe events not yet captured in the wisdom block.
5. Target output: <=50% of the input word count.

Output rules — follow exactly:
- Output ONLY the rewritten markdown. No preamble, no explanation, no
  code fences around the whole thing.
- The output MUST start with `---` (the opening of the YAML frontmatter).

Original creature file:

{creature_text}
"""


def _strip_outer_code_fence(text: str) -> str:
    """If the whole response is wrapped in ```...``` fences, strip them."""
    s = text.strip()
    if s.startswith("```") and s.endswith("```"):
        # drop first and last fence lines
        lines = s.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return s


def propose_distillation(
    *,
    creature_text: str,
    client,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 2000,
) -> str:
    """Ask the LLM for a distilled version of the creature file.

    Returns the raw distilled markdown string. Raises ValueError if the
    response is malformed (e.g. missing frontmatter).
    """
    prompt = PROMPT_TEMPLATE.format(creature_text=creature_text)
    resp = client.complete(
        system="",
        user=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    body = _strip_outer_code_fence(resp.text)
    if not body.lstrip().startswith("---"):
        raise ValueError(
            "proposer response missing YAML frontmatter "
            f"(starts with: {body[:60]!r})"
        )
    return body
