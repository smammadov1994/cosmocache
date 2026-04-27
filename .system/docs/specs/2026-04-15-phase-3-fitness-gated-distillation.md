---
title: "Phase 3 — Fitness-Gated Distillation"
date: 2026-04-15
status: draft
depends_on: Phase 2 eval harness (shipped), indexing fix (bc2806c)
---

# Phase 3 — Fitness-Gated Distillation

## 1. Problem

Cosmocache only *adds* content. Every autoresearch tick appends a generation
note. Every session appends to a creature's journal. Nothing ever distills,
merges, or prunes. Over months of real use, each planet bloats into the same
thing we said we were fixing — a flat memory.md one directory deeper.

Phase 2 proved the structure saves tokens at scale (2.3x at 100 planets).
Phase 3 makes the structure **self-maintaining** so that advantage doesn't
decay.

## 2. Goal

An autonomous agent proposes a tighter version of a creature's knowledge.
The mutation is kept **only if** `score_planet()` proves accuracy held while
token cost dropped. Otherwise the original file stays untouched. No fact is
ever silently lost.

## 3. V1 Scope: Distillation Only

One mutation type for v1: **creature journal distillation**. The agent
rewrites a creature's verbose journal entries into a compact Distilled
Wisdom block. The harness is mutation-type-agnostic — future mutation types
(creature merges, generation consolidation, planet.md rewrites) plug in as
new proposer classes without redesigning the loop.

### Why start here

- Smallest blast radius: one creature file per mutation attempt.
- Highest signal: creature journals are the main source of bloat.
- Scoring is straightforward: same planet, same probes, just a tighter file.
- Does not touch keywords or routing — no risk of breaking Enigma lookups.

## 4. The Loop

```
evolution_tick fires (existing 6h launchd cron)
  │
  ├─ autoresearch runs as today (writes generation note, merges keywords)
  │
  └─ mutation tick runs (NEW)
       │
       ├─ find_candidate(planet_dir) → creature with longest journal
       │   that has no Distilled Wisdom block yet (or a stale one)
       │
       ├─ if no candidate → exit (nothing to distill)
       │
       ├─ snapshot: run score_planet() on current state → baseline_score
       │
       ├─ propose: Haiku writes a distilled version → temp file
       │
       ├─ stage: swap creature file with temp copy (in a temp dir copy,
       │   NOT in-place — original is never touched until promotion)
       │
       ├─ measure: run score_planet() on staged state → mutant_score
       │
       ├─ gate:
       │   ├─ mutant accuracy_mean >= baseline accuracy_mean
       │   ├─ AND mutant input_tokens_mean < baseline input_tokens_mean
       │   └─ (both conditions must hold)
       │
       ├─ if PASS:
       │   ├─ overwrite original creature file with distilled version
       │   ├─ record in evolutions.db: status=promoted, delta logged
       │   └─ log: "mutation promoted: accuracy {x}→{y}, tokens {a}→{b}"
       │
       └─ if FAIL:
           ├─ discard temp file, original creature untouched
           ├─ record in evolutions.db: status=rejected, reason logged
           └─ log: "mutation rejected: {reason}"
```

## 5. Answers to Open Design Questions

| # | Question | V1 Decision | Rationale |
|---|----------|-------------|-----------|
| 1 | Mutation types | Distillation only | Prove the loop on the safest mutation; others plug in later |
| 2 | Trigger model | Cron from day one | Piggyback on existing 6h launchd tick |
| 3 | Dollar budget | ~$0.05/attempt | Haiku proposes (~$0.005), score_planet runs 2-5 probes (~$0.04) |
| 4 | Branch strategy | Copy-on-write temp dir | No git branches needed; simpler, no git dependency |
| 5 | Promotion rule | Automatic: accuracy >= prior AND tokens < prior | No human gate; fully autonomous |
| 6 | Safety floor | Hard floor: never apply if accuracy drops | By construction — gate rejects |

## 6. New Files

### `scripts/mutation_tick.py`
The orchestrator. Entry point called from evolution_tick.py after
autoresearch succeeds. Responsibilities:
- `find_candidate(planet_dir)` — scan creatures/, pick the one with the
  longest journal that lacks a current Distilled Wisdom block.
- `snapshot_score(planet_slug, universe_dir, probes)` — run score_planet()
  and return the PlanetScore.
- `stage_mutation(planet_dir, creature_path, distilled_content)` — create
  a temp copy of the universe with the creature file replaced.
- `gate(baseline, mutant)` — compare PlanetScores, return pass/fail +
  reason string.
- `promote(creature_path, distilled_content)` — overwrite original.
- `main(slug, planet_dir, probes)` — orchestrate the full loop.

### `scripts/propose_distillation.py`
The proposer. Takes a creature markdown file, calls Haiku with a tightly
constrained prompt, returns the distilled version as a string.

Rules for the proposer prompt:
- Keep ALL factual claims, code snippets, and specific techniques.
- Collapse repetitive "I learned X again" entries into one statement.
- Preserve the creature's name, personality line, and abilities section.
- Output must be valid creature markdown (same frontmatter schema).
- Target: <=50% of original word count while retaining every fact.

### Tests

- `tests/test_propose_distillation.py` — unit test: give it a fixture
  creature with a verbose journal, verify output is shorter, retains
  key facts, valid markdown.
- `tests/test_mutation_tick.py` — integration test: fixture planet with
  one bloated creature, mock score_planet to return known scores, verify
  promote/reject logic and evolutions.db recording.
- `tests/test_gate.py` — unit test: edge cases for the gate function
  (equal accuracy, equal tokens, accuracy drop, token increase).

## 7. Modified Files

### `scripts/evolution_tick.py`
After autoresearch completes successfully, call `mutation_tick.main()`.
Pass the planet slug, planet_dir, and a probe subset (derived from the
planet's keywords matched against probes.yaml).

### `scripts/evolve.py`
Add `mutation_promoted` and `mutation_rejected` event types to
evolutions.db schema (alongside existing start/complete/fail).

### `scripts/cosmo` (CLI)
Add `cosmo evolve mutations` subcommand:
- Lists mutation history from evolutions.db (promoted/rejected, delta,
  creature, timestamp).
- `--planet SLUG` filter.
- `--json` flag for agent consumption.

## 8. What Does NOT Change

- `score_planet()` — frozen contract, untouched.
- `enigma_tick.py` — already watches creature mtimes (bc2806c fix).
- Planet directory structure (planet.md, creatures/, generations/).
- Glossary format, session hooks, /universe skill.

## 9. Observability

After Phase 3 ships, the full loop is observable:

```
cosmo evolve kick <slug>       # trigger tick
cosmo evolve mutations         # see promote/reject history with deltas
cosmo planets                  # see keyword changes
cosmo evolve rebuild-index     # refresh Enigma's index
cosmo index                    # verify Enigma sees new terms
```

## 10. Future Mutation Types (not v1)

These plug into the same harness as new proposer classes:

- **Generation consolidation** — merge N archived generation scrolls into
  one summary. Proposer: summarize; gate: same score_planet check.
- **Creature merges** — detect two creatures covering the same sub-topic,
  merge into one. Proposer: identify overlap + merge; gate: same check.
- **Planet.md rewrites** — rewrite the planet identity card for clarity.
  Highest risk (keywords = routing). Requires additional gate: keywords
  must be a superset of originals (no silent routing breakage).

Each new type is a new file (`propose_<type>.py`) + a registration in
mutation_tick.py's candidate finder. No harness changes needed.

## 11. Success Criteria

Phase 3 is successful when:

1. At least one creature file has been autonomously distilled with
   accuracy >= prior and tokens < prior (a real promoted mutation).
2. At least one mutation attempt has been correctly rejected because
   accuracy would have dropped (the safety floor works).
3. The mutation history is visible via `cosmo evolve mutations`.
4. The site and README reflect Phase 3 as shipped (not a stub).
