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


if __name__ == "__main__":
    raise SystemExit(0)
