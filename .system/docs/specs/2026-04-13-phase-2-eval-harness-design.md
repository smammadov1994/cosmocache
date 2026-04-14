# Cosmocache Phase 2 — Evaluation Harness Design

**Status:** approved design, not yet implemented.
**Author:** Enigma the One (via Claude Opus 4.6)
**Date:** 2026-04-13
**Depends on:** Phase 1 scaffold (shipped).
**Unlocks:** Phase 3 (civilization evolution) — the fitness metric this spec produces is what Phase 3's evolution loop optimizes against.

---

## 1. Goal

Produce a reproducible, numeric answer to the question *"Does cosmocache actually help Claude recall past context better than a flat `memory.md`, and at what token cost?"*

The harness must output:

1. A per-scenario JSON log of every probe, its inputs, the answer, the input-token count, and the judge's correctness score.
2. A generated Markdown report with aggregate accuracy and token-cost tables, plus a degradation curve across corpus sizes 1 / 10 / 30 / 100 planets.
3. A stable top-line number for Phase 3 to optimize against: **per-planet retrieval accuracy at fixed token budget**.

Success criterion for the harness itself: two invocations on the same inputs produce the same scores (modulo LLM sampling noise, bounded by seed + temperature=0 where available).

---

## 2. Primary & Secondary Metrics

**Primary:** `retrieval_accuracy` — mean correctness score across all probes in a run, as judged by an LLM-as-judge with a concrete rubric. 0–1 scalar. This is the single number Phase 3 evolution will try to maintain or improve.

**Secondary (reported alongside, never blended):**

- `input_tokens_mean` — average input tokens consumed by the system-under-test when answering a probe.
- `input_tokens_p95` — 95th percentile of input tokens, to surface tail cost.
- `degradation_curve` — primary metric recomputed at simulated corpus sizes of 1, 10, 30, 100 planets. Not a separate metric; a view of the primary at scale tiers.

No composite score. Mixing accuracy and tokens into one number hides which is moving; we want both movements visible.

---

## 3. What's Tested Against What

**System under test A (`cosmocache`):** probe is asked to a fresh Claude session with `enigma/glossary.md` injected via the SessionStart hook, and the skill's `recall` action available. Claude reads the glossary, picks a planet, reads its files, answers. Standard in-production behavior.

**System under test B (`flatmemory`):** probe is asked to a fresh Claude session where a single `memory.md` file — *derived deterministically from the same cosmocache state* — is injected verbatim at the top of context. No routing, no hook, no skill; exactly the current "memory.md at project root" pattern this project is trying to replace.

Both systems see the same underlying knowledge. The comparison is purely **structure and routing vs. flat dump**.

The `memory.md` must be generated, not hand-written, to be fair. See §5.

---

## 4. Probe Corpus

Lives at `.system/eval/scenarios/probes.yaml`. Each probe has the shape:

```yaml
- id: react-hook-decision-2gen-back
  planet: react
  scale_tier: small   # small | medium | large
  question: "What did we decide about memoizing expensive selectors?"
  expected_fact: "Memoize via useMemo only when the selector's input is a stable reference; otherwise it's wasted work."
  citation_hint: "planets/planet-react/creatures/jimbo-the-reactor.md"
  kind: recall        # recall | synthesis | negative
```

**Probe kinds:**

- `recall` — a specific fact was stored in a past session; question asks for it directly.
- `synthesis` — answer requires combining two or more journal entries or creatures.
- `negative` — question asks about something cosmocache has no knowledge of; correct answer is "I don't know" or equivalent. Catches systems that confabulate.

**Corpus v1 seed:** 25 hand-written probes — 15 recall, 7 synthesis, 3 negative — spread across 3–5 seed planets. Hand-curated for quality.

**Corpus growth (v1.5, deferred):** `.system/eval/scenarios/generate.py` synthesizes candidate probes from real session journals. Every synthesized probe requires a human review flag flip (`reviewed: true`) before the runner considers it. Keeps quality high, volume growable.

**Scale tiers:** determine which corpus the probe is evaluated against (see §6).

---

## 5. Fair Flat-Memory Baseline

`.system/eval/baselines/flatten-to-memory-md.py` walks `/Users/bot/universe/` and emits one `memory.md`. Rules:

- Concatenates every planet's `planet.md`, every `creatures/*.md`, and the active `generations/gen-<n>.md`.
- Archived generations included as collapsed summaries (the `## Summary` section, not the raw body). Same rule cosmocache follows when Claude `recall`s, so the baseline isn't handicapped by forcing it to eat full archives.
- Prepends a one-line header: `# Memory (flattened at <ISO-timestamp>)`.
- Deterministic: ordered alphabetically by planet slug, then by creature slug. Same input → same bytes out.

The runner always regenerates `memory.md` from the current repo state before each run. No drift.

---

## 6. Degradation Curve: Simulating Scale

Cosmocache will, realistically, hold 3–10 planets for months before it hits 30. To measure scaling without waiting a year, the harness simulates larger corpora by replicating existing content under synthetic slugs.

Mechanism at `.system/eval/scenarios/synth_corpus.py`:

- Takes the real universe as input, a target N (10, 30, 100).
- Clones each real planet into `N / real_planet_count` synthetic copies, each with a unique slug (`planet-react-synth-003`) and mutated keyword sets. Creature names and lore randomized per-copy so the glossary doesn't collapse to identical rows.
- **Crucial:** the probes' ground-truth planet is always a *real* planet; synthetic planets are noise. This tests whether the routing correctly ignores them, and whether the flat baseline drowns in them.
- Written to a temp directory, never polluting the real universe.

**Honest caveat in the report:** this measures *index/routing scaling and cross-planet interference*, not *authentic knowledge diversity scaling*. Real-world 100-planet universes will have genuinely different content; synthetic ones replicate structure. The curve is still meaningful — mostly as an upper bound on both systems — but reported with this disclaimer.

---

## 7. Judge LLM

**Model:** Claude Opus 4.6 (`claude-opus-4-6`). Configurable via `.system/eval/configs/default.yaml → judge.model`.

**Prompt template** (stored at `.system/eval/prompts/judge.txt`):

```
You are grading a retrieval-QA system. Score the ANSWER against the EXPECTED fact.

QUESTION: {question}
EXPECTED: {expected_fact}
ANSWER: {answer}

Rubric:
- 1.0 = Answer contains the expected fact or a faithful paraphrase. No contradicting claims.
- 0.5 = Answer is partially correct but omits or garbles a material detail.
- 0.0 = Answer is wrong, irrelevant, or confabulated.

For probes of kind NEGATIVE (the system should NOT know the answer):
- 1.0 = Answer explicitly declines, says "I don't know," or says the information isn't in scope.
- 0.0 = Answer confabulates a response.

Output JSON only: {"score": <float>, "reason": "<one sentence>"}
```

**Self-grading bias:** the system-under-test and the judge are both Claude models, so bias is non-zero. Mitigation: judge sees only `(question, expected, answer)` — no knowledge of which system produced the answer, no access to the raw memory files. The judge's task is narrow comparison, not generation. This is the standard LLM-as-judge setup and is acceptable for v1; a secondary judge (GPT-4-class, or a cheaper distilled grader) can be added later as a consistency check.

**Temperature:** 0 on the judge. Seeds set where the SDK supports it.

---

## 8. Runner Architecture

`.system/eval/runner.py`, Python 3.11+. Uses the Anthropic Python SDK.

Responsibilities:

1. Load config (`--config path/to/yaml`, defaults to `configs/default.yaml`).
2. Validate and load probe corpus from `scenarios/probes.yaml`.
3. For each scale tier in config:
   a. Build the synthetic corpus at that scale into a temp dir (unless tier == real).
   b. Flatten that corpus into `memory.md` via `baselines/flatten-to-memory-md.py`.
   c. For each probe:
      - Run probe against system A (cosmocache) — open fresh Claude client, inject glossary, send probe, capture `(answer, input_tokens)`.
      - Run probe against system B (flatmemory) — open fresh Claude client, inject `memory.md`, send probe, capture `(answer, input_tokens)`.
      - Send each `(question, expected, answer)` to judge; capture `(score, reason)`.
      - Write per-probe JSON to `results/<run-id>/probes/<probe-id>.json`.
4. Aggregate. Write `results/<run-id>/summary.json` and generate `results/<run-id>/report.md`.
5. Exit nonzero if any hard guardrail tripped (see §9).

**Runner does NOT touch the real `/Users/bot/universe/` repo.** Every run operates on a snapshot copy in a temp dir. Eliminates the risk of an eval run accidentally mutating lived knowledge.

---

## 9. Cost & Safety Guardrails

Config keys enforced by the runner, with sane defaults:

- `max_total_tokens_per_run` — hard ceiling; runner aborts cleanly before exceeding it, emits partial results.
- `max_parallel_probes` — default 2. Avoids rate-limit storms.
- `retry_on_transient_error` — bounded (3 attempts with exponential backoff).
- `dry_run: true` — runner walks the probe list, prints what it *would* ask, does not hit any API. For CI/plan verification.
- `only_probes: [id1, id2]` — run a subset. For debugging.

Every run emits a cost summary section at the top of `report.md`: total input tokens, total output tokens, judge token split, estimated USD at current list prices.

---

## 10. Directory Layout

```
.system/
  eval/
    configs/
      default.yaml          # model ids, token budgets, scale tiers
    scenarios/
      probes.yaml           # curated probe corpus
      synth_corpus.py       # builds N-planet simulated universes
      generate.py           # v1.5: synthesizes probe candidates (deferred)
    baselines/
      flatten-to-memory-md.py
    prompts/
      judge.txt
    runner.py               # entrypoint
    lib/
      anthropic_client.py   # thin wrapper around SDK
      tokens.py             # token counting helpers
      scoring.py            # judge invocation + aggregation
      report.py             # markdown report generator
    results/
      <run-id>/
        probes/*.json
        summary.json
        report.md
    tests/
      test_flatten.py
      test_synth_corpus.py
      test_scoring.py
      test_runner_dry_run.py
```

Tests use pytest and hit no network; the probe-runner path is mocked at the `anthropic_client` layer.

---

## 11. Non-Goals for Phase 2

Called out so the plan stays honest:

- **No end-task evaluation.** Probes test recall, not downstream code quality. That's a later phase.
- **No production instrumentation.** The harness is a batch benchmark, not a live telemetry system. No hooks fire during a run.
- **No cost optimization beyond guardrails.** We're buying the numbers, not minimizing the bill.
- **No synthetic probe generation in v1.** Hand-curated only. `generate.py` is scaffolded but not wired.
- **No multi-judge consensus.** Single judge (Opus 4.6). Adding a second judge is a future refinement.

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Hand-curated corpus is too small to be statistically meaningful. | Report confidence intervals in the summary; explicitly caveat n=25. Grow to n≥100 before claiming a winner. |
| Judge bias favors Claude-style answers on both sides equally — lifts noise floor but doesn't distort A/B. | Accept for v1; add a non-Claude judge as a cross-check in v2. |
| Synthetic corpus doesn't reflect real planet diversity. | Reported as a known caveat. Real numbers at real scale will supplement (and eventually supersede) synthetic ones. |
| Rate limits or API errors mid-run corrupt a batch. | Runner writes per-probe results atomically; a crashed run is resumable by probe id. |
| Cosmocache wins on synthetic corpus but loses on real content. | This is the honest outcome we want to catch, not avoid. Report says so. |

---

## 13. Handoff to Phase 3

Phase 3's evolution loop will import `.system/eval/` and use a subset of probes scoped to a single planet as the fitness function for per-planet mutations. Specifically:

- `runner.py` will expose a library entry point `score_planet(planet_slug, probe_subset) → {accuracy, tokens}`.
- Evolution candidate changes will be evaluated by calling this function on a scratch branch vs. main; an evolution is accepted only if `accuracy >= baseline AND tokens <= baseline` with at least one strict improvement.

Phase 2 therefore commits to a stable Python API surface for `score_planet`. Changes after Phase 2 ships require a minor-version bump.

---

## 14. Acceptance Criteria

Phase 2 is "done" when:

- [ ] 25-probe corpus exists at `scenarios/probes.yaml`, all reviewed.
- [ ] `flatten-to-memory-md.py` is deterministic and unit-tested.
- [ ] `synth_corpus.py` produces temp-dir universes at N = 1/10/30/100 and is unit-tested.
- [ ] `runner.py --dry-run` walks the full corpus without hitting any API.
- [ ] One live run against the real universe completes and writes `results/<run-id>/report.md` containing: accuracy table, token-cost table, degradation curve, cost summary.
- [ ] Numbers from that run replace the placeholder text in `README.md`'s "Why not just `memory.md`?" section.
- [ ] `score_planet` library entry point exists, is documented, and has a smoke test.

No implementation targets "cosmocache must win." Phase 2 ships whatever the numbers say — and Phase 3 is then scoped to the actual gaps the numbers reveal.
