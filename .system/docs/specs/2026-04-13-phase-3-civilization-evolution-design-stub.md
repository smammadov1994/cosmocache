# Phase 3 — Civilization Evolution (design stub)

Phase 2 has shipped; `lib/planet_scope.py:score_planet` is now the stable entry
point Phase 3 will use as its fitness function.

## Frozen contract (do not change without migration)

```python
def score_planet(
    planet_slug: str,
    universe_dir: Path,
    probe_subset: list[str],
    client: BaseClient,
    judge_model: str,
    sut_model: str,
    sut_temperature: float = 0.0,
    sut_max_tokens: int = 1024,
    judge_temperature: float = 0.0,
    judge_max_tokens: int = 256,
) -> PlanetScore
```

`PlanetScore` fields: `planet_slug`, `accuracy_mean`, `input_tokens_mean`,
`input_tokens_p95`, `n_probes`.

## Open design questions (brainstorming inputs)

1. Which mutation types enter v1 beyond pure distillation (rewriting
   Distilled Wisdom blocks)? Candidates: creature merges, generation
   consolidation, planet.md rewrites, glossary keyword pruning.
2. Trigger model: manual only for v1, or cron from day one?
3. Per-invocation dollar budget — what number?
4. Branch-and-merge vs commit-and-revert for evolution outcomes?
5. How does an evolution promote a planet into a new generation? Score
   delta threshold, or human approval?
6. Safety: an agent that edits its own knowledge base can destabilize
   accuracy. Do we require a floor like "never commit a mutation that
   drops accuracy_mean below the prior generation's score"?

## Dependency on Phase 2 numbers

Evolution is a fitness-optimizer. Without Phase 2's first live-run numbers
we don't know which planets/creatures/generations have the most headroom.
Design should happen after the first live run lands.

Design spec to be written via the brainstorming skill once Phase 2 numbers
are in hand.
