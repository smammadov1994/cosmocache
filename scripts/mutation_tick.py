#!/usr/bin/env python3
"""mutation_tick — fitness-gated distillation orchestrator (Phase 3).

After autoresearch completes for a planet, this picks a candidate creature,
asks Haiku for a distilled version, stages it in a temp universe copy,
runs score_planet against staged + baseline, and promotes the edit only
if the gate passes.

Original creature files are never modified until the gate passes.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


# Floating-point slop tolerance for the accuracy comparison. Aggregating
# many probe scores can yield 1e-9 drift even when the answer is identical.
ACCURACY_EPSILON = 1e-6


@dataclass
class GateResult:
    passed: bool
    reason: str
    accuracy_delta: float
    tokens_delta: float


def gate(baseline, mutant) -> GateResult:
    """Decide whether to promote a mutation.

    Pass iff: mutant accuracy >= baseline accuracy (within epsilon)
              AND mutant input_tokens_mean strictly less than baseline.

    `baseline` and `mutant` must each have `accuracy_mean` and
    `input_tokens_mean` attributes (PlanetScore-shaped).
    """
    acc_delta = mutant.accuracy_mean - baseline.accuracy_mean
    tok_delta = mutant.input_tokens_mean - baseline.input_tokens_mean

    if acc_delta < -ACCURACY_EPSILON:
        return GateResult(
            passed=False,
            reason=f"accuracy dropped: {baseline.accuracy_mean:.3f} -> "
                   f"{mutant.accuracy_mean:.3f}",
            accuracy_delta=acc_delta,
            tokens_delta=tok_delta,
        )
    if tok_delta >= 0:
        return GateResult(
            passed=False,
            reason=f"no token savings: {baseline.input_tokens_mean:.0f} -> "
                   f"{mutant.input_tokens_mean:.0f}",
            accuracy_delta=acc_delta,
            tokens_delta=tok_delta,
        )
    return GateResult(
        passed=True,
        reason=f"accuracy held ({mutant.accuracy_mean:.3f}), "
               f"tokens {baseline.input_tokens_mean:.0f} -> "
               f"{mutant.input_tokens_mean:.0f} ({tok_delta:.0f})",
        accuracy_delta=acc_delta,
        tokens_delta=tok_delta,
    )


# Don't bother distilling creatures whose journal is already short.
MIN_JOURNAL_CHARS = 1500
# A redistillation is worthwhile when the journal has grown to at least
# this multiple of the existing Distilled Wisdom block.
JOURNAL_OUTGROWTH_RATIO = 2.0


def _split_sections(text: str) -> dict[str, str]:
    """Return {heading_lowered: body} for every '## Heading' section."""
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current.strip().lower()] = "\n".join(buf).strip()
            current = line[3:]
            buf = []
        else:
            buf.append(line)
    if current is not None:
        sections[current.strip().lower()] = "\n".join(buf).strip()
    return sections


def find_candidate(planet_dir: Path) -> Path | None:
    """Return the creature file most worth distilling, or None.

    Selection rule:
      1. Read every creatures/*.md.
      2. Compute (journal_chars, wisdom_chars) per file.
      3. Eligible if:
         - journal_chars >= MIN_JOURNAL_CHARS, AND
         - (no wisdom block) OR (journal_chars >= ratio * wisdom_chars)
      4. Among eligible files, return the one with the longest journal.
    """
    cdir = planet_dir / "creatures"
    if not cdir.is_dir():
        return None

    best: tuple[int, Path] | None = None
    for md in sorted(cdir.glob("*.md")):
        try:
            text = md.read_text(errors="replace")
        except OSError:
            continue
        sections = _split_sections(text)
        journal = sections.get("journal", "")
        wisdom = sections.get("distilled wisdom", "")
        j_len = len(journal)
        w_len = len(wisdom)
        if j_len < MIN_JOURNAL_CHARS:
            continue
        if w_len > 0 and j_len < JOURNAL_OUTGROWTH_RATIO * w_len:
            continue
        if best is None or j_len > best[0]:
            best = (j_len, md)
    return best[1] if best else None


if __name__ == "__main__":
    raise SystemExit(0)
