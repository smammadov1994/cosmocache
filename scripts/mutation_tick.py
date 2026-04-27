#!/usr/bin/env python3
"""mutation_tick — fitness-gated distillation orchestrator (Phase 3).

After autoresearch completes for a planet, this picks a candidate creature,
asks Haiku for a distilled version, stages it in a temp universe copy,
runs score_planet against staged + baseline, and promotes the edit only
if the gate passes.

Original creature files are never modified until the gate passes.
"""
from __future__ import annotations
import os
import shutil
import sys
import tempfile
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


def stage_mutation(
    *,
    universe_dir: Path,
    creature_path: Path,
    new_content: str,
) -> tuple[Path, Path]:
    """Copy `universe_dir` to a temp location and swap in `new_content`
    at the creature's relative position.

    Returns (staged_root, staged_creature_path). Caller is responsible
    for shutil.rmtree(staged_root) when done.

    The original creature file is NEVER modified by this function.
    """
    rel = creature_path.resolve().relative_to(universe_dir.resolve())
    staged_root = Path(tempfile.mkdtemp(prefix="cosmocache-mutation-"))
    # copytree into a child dir so we own the whole tree cleanly
    staged_universe = staged_root / "universe"
    shutil.copytree(universe_dir, staged_universe, symlinks=False)
    staged_creature = staged_universe / rel
    staged_creature.write_text(new_content)
    return staged_universe, staged_creature


@dataclass
class MutationResult:
    outcome: str   # "promoted" | "rejected" | "skipped"
    reason: str
    creature: str | None = None
    accuracy_delta: float = 0.0
    tokens_delta: float = 0.0


def _score(*, planet_slug, universe_dir, probe_subset, client, judge_model,
           sut_model):
    """Wrapper around lib.planet_scope.score_planet — separate function so
    tests can monkeypatch it without touching the real eval lib."""
    # Lazy import: avoids paying the eval-lib import cost when find_candidate
    # finds nothing.
    eval_lib = Path(__file__).resolve().parents[1] / ".system" / "eval"
    if str(eval_lib) not in sys.path:
        sys.path.insert(0, str(eval_lib))
    from lib.planet_scope import score_planet  # noqa: E402
    return score_planet(
        planet_slug=planet_slug,
        universe_dir=universe_dir,
        probe_subset=probe_subset,
        client=client,
        judge_model=judge_model,
        sut_model=sut_model,
    )


def _cleanup_staged(tempdir: Path) -> None:
    """Remove the staged tempdir; log on failure rather than silently leaking."""
    try:
        shutil.rmtree(tempdir)
    except OSError as e:
        sys.stderr.write(
            f"warning: failed to clean staged tempdir {tempdir}: {e}\n"
        )


def run(
    *,
    planet_slug: str,
    planet_dir: Path,
    universe_dir: Path,
    probe_subset: list[str],
    client,
    proposer_model: str,
    sut_model: str,
    judge_model: str,
) -> MutationResult:
    """Run one mutation tick for a single planet.

    Steps: find_candidate -> propose -> stage -> score -> gate -> promote/reject.
    Original creature file is only overwritten if the gate passes.
    """
    candidate = find_candidate(planet_dir)
    if candidate is None:
        return MutationResult(outcome="skipped",
                              reason="no creature qualifies for distillation")

    # An empty probe_subset means score_planet would run zero probes and
    # return all-zero metrics — which would falsely fail the gate as
    # "no token savings". Skip cleanly instead, with an honest reason.
    if not probe_subset:
        return MutationResult(
            outcome="skipped",
            reason="no probes match this planet's keywords",
            creature=candidate.name,
        )

    from propose_distillation import propose_distillation
    try:
        distilled = propose_distillation(
            creature_text=candidate.read_text(),
            client=client,
            model=proposer_model,
        )
    except (ValueError, OSError) as e:
        return MutationResult(outcome="rejected",
                              reason=f"proposer error: {e}",
                              creature=candidate.name)

    try:
        baseline = _score(planet_slug=planet_slug, universe_dir=universe_dir,
                          probe_subset=probe_subset, client=client,
                          judge_model=judge_model, sut_model=sut_model)
    except Exception as e:
        return MutationResult(outcome="rejected",
                              reason=f"baseline scoring error: {e}",
                              creature=candidate.name)

    try:
        staged_universe, staged_creature = stage_mutation(
            universe_dir=universe_dir,
            creature_path=candidate,
            new_content=distilled,
        )
    except Exception as e:
        return MutationResult(outcome="rejected",
                              reason=f"stage error: {e}",
                              creature=candidate.name)

    tempdir = staged_universe.parent
    try:
        try:
            mutant = _score(planet_slug=planet_slug,
                            universe_dir=staged_universe,
                            probe_subset=probe_subset, client=client,
                            judge_model=judge_model, sut_model=sut_model)
        except Exception as e:
            return MutationResult(outcome="rejected",
                                  reason=f"mutant scoring error: {e}",
                                  creature=candidate.name)

        g = gate(baseline, mutant)
        if not g.passed:
            return MutationResult(outcome="rejected", reason=g.reason,
                                  creature=candidate.name,
                                  accuracy_delta=g.accuracy_delta,
                                  tokens_delta=g.tokens_delta)

        # promote: atomic write to .tmp sibling then POSIX rename so a
        # mid-write crash can never destroy the original.
        tmp = candidate.with_suffix(candidate.suffix + ".tmp")
        tmp.write_text(distilled)
        tmp.replace(candidate)
        return MutationResult(outcome="promoted", reason=g.reason,
                              creature=candidate.name,
                              accuracy_delta=g.accuracy_delta,
                              tokens_delta=g.tokens_delta)
    finally:
        _cleanup_staged(tempdir)


if __name__ == "__main__":
    raise SystemExit(0)
