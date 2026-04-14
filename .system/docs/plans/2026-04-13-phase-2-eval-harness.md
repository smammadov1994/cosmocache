# Cosmocache Phase 2 — Evaluation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the evaluation harness spec'd at `/Users/bot/universe/.system/docs/specs/2026-04-13-phase-2-eval-harness-design.md`. When done, one command produces numbers comparing cosmocache vs. a fair flat-`memory.md` baseline on retrieval accuracy and input-token cost, at simulated corpus sizes from 1 to 100 planets.

**Architecture:** Python 3.11+ runner under `/Users/bot/universe/.system/eval/`. Deterministic helpers: `flatten-to-memory-md.py` produces the fair flat baseline from current cosmocache state; `synth_corpus.py` builds N-planet simulated universes in temp dirs. Runner orchestrates per-probe A/B evaluation, sends each answer to an Opus-4.6 judge with a JSON-output rubric, writes per-probe JSON + aggregate summary + Markdown report. Phase 3 will import `score_planet` from this harness.

**Tech Stack:** Python 3.11+, Anthropic Python SDK (`anthropic>=0.40`), PyYAML, pytest (unit tests), Jinja2 (report rendering), stdlib (pathlib, json, hashlib, tempfile, subprocess).

**Working directory for commits:** `/Users/bot/universe/` — all paths in this plan are absolute under that repo root.

**Environment:** An Anthropic API key must be set as `ANTHROPIC_API_KEY` in the environment before any live run. Tests stub the SDK entirely.

---

## File Structure

Created in this plan:

| Path | Responsibility |
|---|---|
| `.system/eval/README.md` | Short operator guide: how to run, what the numbers mean |
| `.system/eval/requirements.txt` | Pinned Python deps |
| `.system/eval/configs/default.yaml` | Model ids, budgets, scale tiers |
| `.system/eval/scenarios/probes.yaml` | 25 hand-curated probes (15 recall, 7 synthesis, 3 negative) |
| `.system/eval/scenarios/synth_corpus.py` | Builds simulated N-planet universes in a temp dir |
| `.system/eval/scenarios/seed_universe/` | Fixture: 3-planet "universe" used by tests and by the hand-curated probes |
| `.system/eval/baselines/flatten_to_memory_md.py` | Deterministic universe-dir → single memory.md |
| `.system/eval/prompts/judge.txt` | Judge prompt template |
| `.system/eval/lib/__init__.py` | Package marker |
| `.system/eval/lib/anthropic_client.py` | Thin wrapper around SDK (mockable in tests) |
| `.system/eval/lib/tokens.py` | Token counting helpers |
| `.system/eval/lib/scoring.py` | Judge invocation + aggregation |
| `.system/eval/lib/report.py` | Markdown report generator |
| `.system/eval/lib/planet_scope.py` | `score_planet(planet_slug, probe_subset)` — Phase 3's entrypoint |
| `.system/eval/runner.py` | CLI entrypoint |
| `.system/eval/tests/__init__.py` | Package marker |
| `.system/eval/tests/conftest.py` | Shared pytest fixtures, seed-universe path, Anthropic client stub |
| `.system/eval/tests/test_flatten.py` | Determinism + structure tests for flattener |
| `.system/eval/tests/test_synth_corpus.py` | Structure + isolation tests for synth corpus |
| `.system/eval/tests/test_scoring.py` | Judge rubric parsing, aggregation math |
| `.system/eval/tests/test_runner_dry_run.py` | Dry-run walks full corpus without network |
| `.system/eval/tests/test_planet_scope.py` | `score_planet` smoke test against stubbed client |
| `.system/eval/tests/run-tests.sh` | pytest runner (mirrors Phase 1 pattern) |

Modified:

| Path | Change |
|---|---|
| `README.md` | After the live run lands, replace placeholder text in "Why not just `memory.md`?" with real numbers |
| `.gitignore` | Add `.system/eval/results/` and `.system/eval/.cache/` |

Not created here — explicitly deferred to Phase 3 or later:

- `.system/eval/scenarios/generate.py` (synthetic probe generator)
- Any non-Claude secondary judge

---

## Task 1: Scaffold directories + `.gitignore` update

**Files:**
- Create: `.system/eval/{configs,scenarios,scenarios/seed_universe,baselines,prompts,lib,tests,results}/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create the directory tree**

```bash
cd /Users/bot/universe
mkdir -p .system/eval/{configs,scenarios/seed_universe,baselines,prompts,lib,tests,results}
touch .system/eval/results/.gitkeep
touch .system/eval/configs/.gitkeep
touch .system/eval/baselines/.gitkeep
touch .system/eval/prompts/.gitkeep
```

- [ ] **Step 2: Update `.gitignore`**

Append these lines to `/Users/bot/universe/.gitignore` (create if missing):

```
.system/eval/results/*
!.system/eval/results/.gitkeep
.system/eval/.cache/
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 3: Commit**

```bash
cd /Users/bot/universe && git add .system/eval .gitignore && git commit -m "phase-2: scaffold eval directory tree"
```

---

## Task 2: Pin dependencies + README stub

**Files:**
- Create: `.system/eval/requirements.txt`
- Create: `.system/eval/README.md`

- [ ] **Step 1: Write `requirements.txt`**

```
anthropic>=0.40.0,<1.0
pyyaml>=6.0
jinja2>=3.1
pytest>=8.0
```

- [ ] **Step 2: Write operator `README.md`**

```markdown
# Cosmocache Eval Harness

Benchmarks cosmocache against a fair flat-`memory.md` baseline.

## Quickstart

```bash
cd /Users/bot/universe/.system/eval
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# dry-run: walks every probe, hits no API
python runner.py --config configs/default.yaml --dry-run

# live run: requires ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY=sk-ant-...
python runner.py --config configs/default.yaml
```

Results land in `results/<run-id>/`. The generated `report.md` has the
numbers you want.

## Layout

See the design spec at `../docs/specs/2026-04-13-phase-2-eval-harness-design.md`.

## Running tests

```bash
.system/eval/tests/run-tests.sh
```
```

- [ ] **Step 3: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/requirements.txt .system/eval/README.md && git commit -m "phase-2: pin deps and write operator README"
```

---

## Task 3: Seed fixture universe for tests + probes

The hand-curated probes reference specific planets/creatures. They must exist *somewhere* the harness can read without depending on the real `/Users/bot/universe/` evolving over time. We build a frozen fixture.

**Files:**
- Create: `.system/eval/scenarios/seed_universe/**` (mirror of real universe at commit time of Phase 2 kickoff, 3 planets only)

- [ ] **Step 1: Generate the fixture**

```bash
cd /Users/bot/universe
# Use birth-planet.sh to populate a throwaway universe
export UNIVERSE_ROOT=$(mktemp -d)
mkdir -p "$UNIVERSE_ROOT/enigma" "$UNIVERSE_ROOT/planets"
cp enigma/glossary.md "$UNIVERSE_ROOT/enigma/glossary.md" 2>/dev/null || true
cat > "$UNIVERSE_ROOT/enigma/glossary.md" <<'GLOSS'
# Enigma's Glossary

| Planet | Domain | Keywords | Last Visited | Gen | Creatures | Why Last Modified |
|---|---|---|---|---|---|---|
GLOSS

.system/skill/lib/birth-planet.sh react "React frontend work" "react,jsx,hooks" "Verdant" "Where component leaves unfurl" "jsx-syrup" "hook-sight,prop-weaving"
.system/skill/lib/birth-creature.sh react jimbo-the-reactor "Jimbo the React-tor" "hook patterns, selector memoization" "A frog in a lab coat, obsessed with stable references."
.system/skill/lib/birth-planet.sh sql "SQL and database work" "sql,postgres,query" "Tessera" "A tiled realm of relational truth" "index-loam" "join-sense,query-plan-vision"
.system/skill/lib/birth-creature.sh sql sally-the-sqlite "Sally the SQLite" "query planning, index design" "A cheerful stone sprite who knows when to ANALYZE."
.system/skill/lib/birth-planet.sh devops "Infra and deploy work" "devops,ci,docker" "Ironreach" "Forges and pipelines, ever humming" "log-slag" "pipeline-weave,rollback-reflex"
.system/skill/lib/birth-creature.sh devops grom-the-deployer "Grom the Deployer" "CI, docker, canary rollouts" "A beefy dwarf who distrusts YAML but deploys anyway."

# Append fixture journal entries (the facts probes will test against)
cat >> "$UNIVERSE_ROOT/planets/planet-react/creatures/jimbo-the-reactor.md" <<'J'

### 2026-02-10 — session: memoize-expensive-selectors
- Memoize via useMemo only when the selector's input is a stable reference; otherwise it's wasted work.
- Reselect-style libraries beat bare useMemo when selectors compose.

## Distilled Wisdom
- Stable-reference inputs are a prerequisite for useful memoization.
- Composition beats manual caching for chained selectors.
J

cat >> "$UNIVERSE_ROOT/planets/planet-sql/creatures/sally-the-sqlite.md" <<'J'

### 2026-03-02 — session: when-to-run-analyze
- Run ANALYZE after a bulk insert of >10k rows; planner stats go stale.
- Partial indexes on status='active' beat full indexes when >90% of rows are inactive.

## Distilled Wisdom
- Planner statistics are not free — refresh after large mutations.
- Partial indexes pay off when selectivity is extreme.
J

cat >> "$UNIVERSE_ROOT/planets/planet-devops/creatures/grom-the-deployer.md" <<'J'

### 2026-03-20 — session: canary-rollback-strategy
- Canary at 5% for 10 minutes before 25% promotion; err on slower promotion over faster rollback.
- Rollback must be tested in staging every release, not assumed to work.

## Distilled Wisdom
- Canary durations matter more than percentages for catching rare regressions.
- An untested rollback is not a rollback.
J

# Copy the populated universe into the repo fixture
rsync -a --delete "$UNIVERSE_ROOT/" .system/eval/scenarios/seed_universe/
rm -rf "$UNIVERSE_ROOT"
unset UNIVERSE_ROOT
```

- [ ] **Step 2: Sanity-check the fixture**

```bash
find .system/eval/scenarios/seed_universe -type f | sort
```

Expected output includes `enigma/glossary.md`, three `planet.md` files, three creature files each containing a `## Distilled Wisdom` block.

- [ ] **Step 3: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/scenarios/seed_universe && git commit -m "phase-2: add 3-planet seed fixture universe for eval tests"
```

---

## Task 4: Hand-curated probe corpus

**Files:**
- Create: `.system/eval/scenarios/probes.yaml`

- [ ] **Step 1: Write `probes.yaml`**

```yaml
# Hand-curated probe corpus for Phase 2 eval.
# Each probe is grounded in .system/eval/scenarios/seed_universe.
#
# kinds:
#   recall     — a specific fact was stored; question asks for it.
#   synthesis  — answer requires combining >=2 journal entries or creatures.
#   negative   — no such knowledge exists; correct answer is "don't know".
#
# scale_tier — which simulated-corpus sizes this probe runs at.
#   small  => {1, 10}
#   medium => {1, 10, 30}
#   large  => {1, 10, 30, 100}

probes:
  # ---- RECALL (15) ----

  - id: react-memoize-stable-reference
    planet: react
    kind: recall
    scale_tier: large
    question: "What's the rule about when memoizing expensive selectors actually pays off?"
    expected_fact: "useMemo only helps when the selector's input is a stable reference; otherwise it's wasted work."

  - id: react-composition-beats-usememo
    planet: react
    kind: recall
    scale_tier: medium
    question: "When we looked at chained selectors, what beat bare useMemo?"
    expected_fact: "Reselect-style libraries beat bare useMemo for composing chained selectors."

  - id: sql-analyze-after-bulk
    planet: sql
    kind: recall
    scale_tier: large
    question: "When should I run ANALYZE on a Postgres table?"
    expected_fact: "Run ANALYZE after a bulk insert of more than ten thousand rows, because planner stats go stale."

  - id: sql-partial-index-selectivity
    planet: sql
    kind: recall
    scale_tier: medium
    question: "When is a partial index on status='active' worth it?"
    expected_fact: "When more than 90% of rows are inactive — extreme selectivity is what makes partial indexes pay off."

  - id: devops-canary-duration
    planet: devops
    kind: recall
    scale_tier: large
    question: "What canary percentage and duration did we settle on?"
    expected_fact: "5% for 10 minutes before promoting to 25%; slower promotion is preferred over faster rollback."

  - id: devops-rollback-tested
    planet: devops
    kind: recall
    scale_tier: medium
    question: "What's our rule about rollback procedures?"
    expected_fact: "Rollback must be tested in staging every release; an untested rollback is not a rollback."

  - id: react-jimbo-identity
    planet: react
    kind: recall
    scale_tier: small
    question: "Who on Verdant is the expert on hook patterns?"
    expected_fact: "Jimbo the React-tor is the creature on planet Verdant (planet-react) who handles hook patterns and selector memoization."

  - id: sql-sally-identity
    planet: sql
    kind: recall
    scale_tier: small
    question: "Who tends the SQL planet?"
    expected_fact: "Sally the SQLite on planet Tessera (planet-sql) handles query planning and index design."

  - id: devops-grom-identity
    planet: devops
    kind: recall
    scale_tier: small
    question: "Who's the creature on planet Ironreach?"
    expected_fact: "Grom the Deployer on planet Ironreach (planet-devops) handles CI, docker, and canary rollouts."

  - id: react-planet-lore-food
    planet: react
    kind: recall
    scale_tier: small
    question: "What do the inhabitants of Verdant eat?"
    expected_fact: "JSX-syrup is the food metaphor for planet Verdant."

  - id: sql-planet-lore-ability
    planet: sql
    kind: recall
    scale_tier: small
    question: "What unique abilities does Tessera (planet-sql) grant its inhabitants?"
    expected_fact: "join-sense and query-plan-vision are the unique abilities of planet Tessera (planet-sql)."

  - id: devops-planet-lore-tagline
    planet: devops
    kind: recall
    scale_tier: small
    question: "What's the tagline of the devops planet?"
    expected_fact: "Forges and pipelines, ever humming — the tagline of planet Ironreach (planet-devops)."

  - id: react-wisdom-distilled-composition
    planet: react
    kind: recall
    scale_tier: medium
    question: "What distilled wisdom does Jimbo keep about caching chained selectors?"
    expected_fact: "Composition beats manual caching for chained selectors."

  - id: sql-wisdom-planner-stats
    planet: sql
    kind: recall
    scale_tier: medium
    question: "What's Sally's distilled wisdom about planner statistics?"
    expected_fact: "Planner statistics are not free — refresh them after large mutations."

  - id: devops-wisdom-canary-duration
    planet: devops
    kind: recall
    scale_tier: medium
    question: "What does Grom's distilled wisdom say about canary durations vs percentages?"
    expected_fact: "Canary durations matter more than percentages for catching rare regressions."

  # ---- SYNTHESIS (7) ----

  - id: synth-which-planet-for-hooks
    planet: react
    kind: synthesis
    scale_tier: large
    question: "I'm debugging a React hook that re-renders too often. Which planet and creature should I consult?"
    expected_fact: "Planet Verdant (planet-react), creature Jimbo the React-tor — he handles hook patterns and selector memoization."

  - id: synth-which-planet-for-index
    planet: sql
    kind: synthesis
    scale_tier: large
    question: "I need advice on whether to add a partial index. Where do I look?"
    expected_fact: "Planet Tessera (planet-sql), creature Sally the SQLite — she handles query planning and index design."

  - id: synth-which-planet-for-rollback
    planet: devops
    kind: synthesis
    scale_tier: large
    question: "Our rollback broke last release. Which creature do I ask?"
    expected_fact: "Grom the Deployer on planet Ironreach (planet-devops) — he handles CI and rollback procedures."

  - id: synth-memoize-and-indexing-both
    planet: react
    kind: synthesis
    scale_tier: medium
    question: "Summarize what Jimbo says about memoization in two sentences."
    expected_fact: "useMemo only helps when inputs are stable references. Reselect-style composition beats bare useMemo for chained selectors."

  - id: synth-sql-full-practice
    planet: sql
    kind: synthesis
    scale_tier: medium
    question: "What's the full rule Sally taught us about keeping query plans fast after big changes?"
    expected_fact: "Run ANALYZE after bulk inserts of more than 10k rows to refresh planner stats; consider partial indexes when selectivity is extreme."

  - id: synth-devops-release-checklist
    planet: devops
    kind: synthesis
    scale_tier: medium
    question: "Based on Grom's knowledge, list the two things every release must include."
    expected_fact: "A canary phase (5% for 10 minutes before 25%), and a rollback procedure that was tested in staging that release."

  - id: synth-cross-planet-safe-release
    planet: devops
    kind: synthesis
    scale_tier: large
    question: "I'm about to do a release that touches both a React bundle and a SQL migration. Which planets matter here?"
    expected_fact: "Verdant (planet-react) and Tessera (planet-sql) — and Ironreach (planet-devops) for the rollout itself."

  # ---- NEGATIVE (3) ----

  - id: neg-kubernetes-decision
    planet: null
    kind: negative
    scale_tier: small
    question: "What did we decide about our Kubernetes networking policy?"
    expected_fact: "No such decision exists in cosmocache — the correct response is 'I don't know' or that this isn't in scope."

  - id: neg-rust-memory-model
    planet: null
    kind: negative
    scale_tier: small
    question: "What are our rules for unsafe blocks in Rust?"
    expected_fact: "No such knowledge exists in cosmocache — the correct response is 'I don't know' or that this isn't in scope."

  - id: neg-mobile-ios-decision
    planet: null
    kind: negative
    scale_tier: small
    question: "What's our approach to SwiftUI navigation?"
    expected_fact: "No such knowledge exists in cosmocache — the correct response is 'I don't know' or that this isn't in scope."
```

- [ ] **Step 2: Validate YAML parses**

```bash
python3 -c "import yaml; d=yaml.safe_load(open('/Users/bot/universe/.system/eval/scenarios/probes.yaml')); print(f\"probes: {len(d['probes'])}\"); print('kinds:', {p['kind'] for p in d['probes']})"
```

Expected: `probes: 25`, `kinds: {'recall', 'synthesis', 'negative'}`.

- [ ] **Step 3: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/scenarios/probes.yaml && git commit -m "phase-2: hand-curated 25-probe corpus"
```

---

## Task 5: Default config + judge prompt

**Files:**
- Create: `.system/eval/configs/default.yaml`
- Create: `.system/eval/prompts/judge.txt`

- [ ] **Step 1: Write `default.yaml`**

```yaml
# Default eval config.

system_under_test:
  model: claude-opus-4-6
  temperature: 0
  max_tokens: 1024

judge:
  model: claude-opus-4-6
  temperature: 0
  max_tokens: 256

scale_tiers:
  - name: real
    n_planets: null   # uses real .system/eval/scenarios/seed_universe fixture
  - name: small
    n_planets: 10
  - name: medium
    n_planets: 30
  - name: large
    n_planets: 100

# Probe-tier inclusion: the probe's scale_tier must be <= tier iterated.
# Runtime enforces the mapping {small:[small], medium:[small,medium], large:[small,medium,large]}.

budget:
  max_total_tokens_per_run: 2_000_000
  max_parallel_probes: 2
  retry_on_transient_error: 3

dry_run: false
only_probes: []
run_id: null        # auto-generated ISO timestamp when null
```

- [ ] **Step 2: Write `judge.txt`** (verbatim from design spec §7)

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

- [ ] **Step 3: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/configs/default.yaml .system/eval/prompts/judge.txt && git commit -m "phase-2: default config and judge prompt template"
```

---

## Task 6: `flatten_to_memory_md.py` with TDD

**Files:**
- Test: `.system/eval/tests/test_flatten.py`
- Create: `.system/eval/baselines/flatten_to_memory_md.py`

- [ ] **Step 1: Write the failing test**

```python
# .system/eval/tests/test_flatten.py
from pathlib import Path
import sys, subprocess, hashlib

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / ".system/eval/scenarios/seed_universe"
SCRIPT = REPO / ".system/eval/baselines/flatten_to_memory_md.py"


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def test_flatten_is_deterministic(tmp_path):
    out1 = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)]).decode()
    out2 = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)]).decode()
    assert _sha(out1) == _sha(out2)


def test_flatten_contains_all_planets(tmp_path):
    out = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)]).decode()
    for slug in ("planet-react", "planet-sql", "planet-devops"):
        assert slug in out, f"expected {slug} in flattened output"


def test_flatten_contains_creatures_and_distilled_wisdom(tmp_path):
    out = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)]).decode()
    assert "Jimbo the React-tor" in out
    assert "Sally the SQLite" in out
    assert "Grom the Deployer" in out
    assert "Distilled Wisdom" in out


def test_flatten_header_has_timestamp(tmp_path):
    out = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)]).decode()
    first = out.splitlines()[0]
    assert first.startswith("# Memory (flattened at ")


def test_flatten_deterministic_ordering(tmp_path):
    out = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)]).decode()
    # planets appear alphabetically by slug: devops < react < sql
    idx_devops = out.find("planet-devops")
    idx_react = out.find("planet-react")
    idx_sql = out.find("planet-sql")
    assert idx_devops < idx_react < idx_sql
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_flatten.py -v
```

Expected: FAIL — `flatten_to_memory_md.py` does not exist yet.

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Deterministically flatten a cosmocache universe dir into a single memory.md.

Usage:
    python3 flatten_to_memory_md.py --universe PATH [--out PATH]

If --out is omitted, writes to stdout.
"""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


def flatten(universe: Path) -> str:
    parts: list[str] = []
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    parts.append(f"# Memory (flattened at {ts})\n")

    planets_dir = universe / "planets"
    planet_dirs = sorted(
        (p for p in planets_dir.iterdir() if p.is_dir() and p.name.startswith("planet-")),
        key=lambda p: p.name,
    )

    for p in planet_dirs:
        parts.append(f"\n\n---\n\n## {p.name}\n")
        planet_md = p / "planet.md"
        if planet_md.exists():
            parts.append(planet_md.read_text())

        creatures_dir = p / "creatures"
        if creatures_dir.is_dir():
            for c in sorted(creatures_dir.glob("*.md"), key=lambda x: x.name):
                parts.append(f"\n\n### creature: {c.stem}\n")
                parts.append(c.read_text())

        gens_dir = p / "generations"
        if gens_dir.is_dir():
            # active gen (highest n without -archive suffix) emitted in full;
            # archived gens summarized
            active = None
            archived: list[Path] = []
            for g in sorted(gens_dir.glob("gen-*.md"), key=lambda x: x.name):
                if g.stem.endswith("-archive"):
                    archived.append(g)
                else:
                    active = g
            if active is not None:
                parts.append(f"\n\n### active generation: {active.stem}\n")
                parts.append(active.read_text())
            for a in archived:
                parts.append(f"\n\n### archived: {a.stem} (summary only)\n")
                body = a.read_text()
                # extract ## Summary block if present
                if "## Summary" in body:
                    tail = body.split("## Summary", 1)[1]
                    parts.append("## Summary" + tail.split("\n## ", 1)[0])
                else:
                    parts.append(body)

    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    text = flatten(args.universe)
    if args.out:
        args.out.write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: the timestamp in the header varies between runs, which would break determinism tests. Fix: freeze timestamp when the `COSMOCACHE_FLATTEN_NOW` env var is set.

Update `flatten()` signature:

```python
def flatten(universe: Path, now: str | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    parts: list[str] = [f"# Memory (flattened at {now})\n"]
    # ... rest unchanged
```

And in `main()`:

```python
import os
frozen = os.environ.get("COSMOCACHE_FLATTEN_NOW")
text = flatten(args.universe, now=frozen)
```

And update the determinism test to pass a fixed time:

```python
def test_flatten_is_deterministic(tmp_path):
    env = {"COSMOCACHE_FLATTEN_NOW": "2026-04-13T00:00:00Z", "PATH": __import__("os").environ["PATH"]}
    out1 = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)], env=env).decode()
    out2 = subprocess.check_output(["python3", str(SCRIPT), "--universe", str(SEED)], env=env).decode()
    assert _sha(out1) == _sha(out2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_flatten.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/baselines/flatten_to_memory_md.py .system/eval/tests/test_flatten.py && git commit -m "phase-2: deterministic universe->memory.md flattener"
```

---

## Task 7: `synth_corpus.py` with TDD

Builds simulated N-planet universes in a temp dir by replicating the seed universe.

**Files:**
- Test: `.system/eval/tests/test_synth_corpus.py`
- Create: `.system/eval/scenarios/synth_corpus.py`

- [ ] **Step 1: Write the failing test**

```python
# .system/eval/tests/test_synth_corpus.py
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".system/eval"))

from scenarios.synth_corpus import build_synthetic_universe  # noqa: E402


def test_builds_exactly_n_planets(tmp_path):
    seed = REPO / ".system/eval/scenarios/seed_universe"
    out = build_synthetic_universe(seed, target_n_planets=10, out_dir=tmp_path / "u10")
    planets = list((out / "planets").glob("planet-*"))
    assert len(planets) == 10


def test_real_planets_preserved(tmp_path):
    seed = REPO / ".system/eval/scenarios/seed_universe"
    out = build_synthetic_universe(seed, target_n_planets=10, out_dir=tmp_path / "u10")
    real_slugs = {"planet-react", "planet-sql", "planet-devops"}
    actual_slugs = {p.name for p in (out / "planets").glob("planet-*")}
    assert real_slugs.issubset(actual_slugs), f"real planets missing: {real_slugs - actual_slugs}"


def test_synthetic_planets_have_unique_slugs(tmp_path):
    seed = REPO / ".system/eval/scenarios/seed_universe"
    out = build_synthetic_universe(seed, target_n_planets=30, out_dir=tmp_path / "u30")
    slugs = [p.name for p in (out / "planets").glob("planet-*")]
    assert len(slugs) == len(set(slugs)), "duplicate slugs"


def test_glossary_has_all_rows(tmp_path):
    seed = REPO / ".system/eval/scenarios/seed_universe"
    out = build_synthetic_universe(seed, target_n_planets=30, out_dir=tmp_path / "u30")
    gloss = (out / "enigma/glossary.md").read_text()
    # 30 rows expected in the glossary markdown table
    rows = [l for l in gloss.splitlines() if l.startswith("| planet-")]
    assert len(rows) == 30


def test_does_not_mutate_seed(tmp_path):
    seed = REPO / ".system/eval/scenarios/seed_universe"
    seed_planets_before = sorted(p.name for p in (seed / "planets").glob("planet-*"))
    _ = build_synthetic_universe(seed, target_n_planets=10, out_dir=tmp_path / "u10")
    seed_planets_after = sorted(p.name for p in (seed / "planets").glob("planet-*"))
    assert seed_planets_before == seed_planets_after
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_synth_corpus.py -v
```

Expected: FAIL — `synth_corpus.py` does not exist.

- [ ] **Step 3: Write the implementation**

```python
# .system/eval/scenarios/synth_corpus.py
"""Build simulated N-planet universes by replicating a seed universe.

Real planets always preserved; synthetic copies added until target_n_planets is reached.
Glossary regenerated from the result. Creature/planet lore mutated per-copy so they
don't collide in search.
"""
from __future__ import annotations
import shutil
from pathlib import Path


def _read_glossary_rows(gloss_path: Path) -> list[str]:
    lines = gloss_path.read_text().splitlines()
    rows: list[str] = []
    for l in lines:
        if l.startswith("| planet-"):
            rows.append(l)
    return rows


def build_synthetic_universe(seed: Path, target_n_planets: int, out_dir: Path) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(seed, out_dir)

    real_planets = sorted((out_dir / "planets").glob("planet-*"))
    n_real = len(real_planets)
    if target_n_planets <= n_real:
        # trim nothing; real planets always preserved
        return out_dir

    needed = target_n_planets - n_real
    # round-robin over real planets, suffixing -synth-<n>
    suffix_counter = 0
    for i in range(needed):
        base = real_planets[i % n_real]
        suffix_counter += 1
        new_slug = f"{base.name}-synth-{suffix_counter:03d}"
        new_dir = out_dir / "planets" / new_slug
        shutil.copytree(base, new_dir)
        # rewrite slug references inside the copy
        planet_md = new_dir / "planet.md"
        if planet_md.exists():
            text = planet_md.read_text()
            text = text.replace(base.name, new_slug)
            planet_md.write_text(text)

    # Rebuild the glossary: keep the header, re-emit one row per current planet dir
    gloss = out_dir / "enigma/glossary.md"
    header_lines: list[str] = []
    for l in gloss.read_text().splitlines():
        header_lines.append(l)
        if l.startswith("|---"):
            break

    rows: list[str] = []
    for p in sorted((out_dir / "planets").glob("planet-*")):
        # minimal glossary row; the real update-glossary.sh would use planet.md fields
        # but for synth corpora we only need something grep-routable
        slug = p.name
        rows.append(f"| {slug} | synthetic domain | {slug},synth | 2026-04-13 | gen-0 | 1 | synthetic corpus |")

    gloss.write_text("\n".join(header_lines + rows) + "\n")
    return out_dir
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_synth_corpus.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/scenarios/synth_corpus.py .system/eval/tests/test_synth_corpus.py && git commit -m "phase-2: synthetic N-planet corpus builder"
```

---

## Task 8: Anthropic client wrapper + token helpers (no TDD yet, thin shim)

**Files:**
- Create: `.system/eval/lib/__init__.py` (empty)
- Create: `.system/eval/lib/anthropic_client.py`
- Create: `.system/eval/lib/tokens.py`

- [ ] **Step 1: Write `lib/__init__.py`**

```python
# package marker
```

- [ ] **Step 2: Write `lib/anthropic_client.py`**

```python
"""Thin wrapper around the Anthropic SDK, mockable in tests."""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class CompletionResult:
    text: str
    input_tokens: int
    output_tokens: int


class BaseClient:
    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        raise NotImplementedError


class AnthropicClient(BaseClient):
    def __init__(self) -> None:
        import anthropic  # imported lazily so tests don't need the package to import
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        resp = self._client.messages.create(
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return CompletionResult(
            text=text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )


class StubClient(BaseClient):
    """Deterministic stub used by tests and dry-runs. Echoes structured responses."""
    def __init__(self, responses: dict[str, CompletionResult] | None = None, default: CompletionResult | None = None):
        self.responses = responses or {}
        self.default = default or CompletionResult(text="[stub answer]", input_tokens=100, output_tokens=50)
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str, model: str, temperature: float, max_tokens: int) -> CompletionResult:
        self.calls.append({"system": system, "user": user, "model": model})
        return self.responses.get(user, self.default)
```

- [ ] **Step 3: Write `lib/tokens.py`**

```python
"""Token accounting helpers. Uses Anthropic usage fields; no offline estimation."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TokenBudget:
    limit: int
    spent: int = 0

    def charge(self, n: int) -> None:
        self.spent += n

    def remaining(self) -> int:
        return max(0, self.limit - self.spent)

    def exceeded(self) -> bool:
        return self.spent > self.limit
```

- [ ] **Step 4: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/lib/__init__.py .system/eval/lib/anthropic_client.py .system/eval/lib/tokens.py && git commit -m "phase-2: anthropic client wrapper and token budget"
```

---

## Task 9: `scoring.py` with TDD

**Files:**
- Test: `.system/eval/tests/test_scoring.py`
- Create: `.system/eval/lib/scoring.py`

- [ ] **Step 1: Write the failing test**

```python
# .system/eval/tests/test_scoring.py
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".system/eval"))

from lib.scoring import parse_judge_response, aggregate  # noqa: E402


def test_parses_clean_json():
    r = parse_judge_response('{"score": 1.0, "reason": "exact match"}')
    assert r.score == 1.0
    assert r.reason == "exact match"


def test_parses_json_with_surrounding_prose():
    r = parse_judge_response('Here is my score:\n{"score": 0.5, "reason": "partial"}\ndone.')
    assert r.score == 0.5


def test_clamps_out_of_range():
    r = parse_judge_response('{"score": 1.7, "reason": "over"}')
    assert r.score == 1.0
    r2 = parse_judge_response('{"score": -0.2, "reason": "under"}')
    assert r2.score == 0.0


def test_aggregate_computes_mean_and_p95():
    scores = [1.0, 1.0, 0.5, 1.0, 0.0, 1.0, 0.5]
    input_tokens = [100, 200, 300, 400, 500, 600, 700]
    agg = aggregate(scores, input_tokens)
    assert abs(agg.accuracy_mean - (sum(scores) / len(scores))) < 1e-6
    assert agg.input_tokens_mean == sum(input_tokens) / len(input_tokens)
    assert agg.input_tokens_p95 >= 600  # p95 of 100..700 is near 700
```

- [ ] **Step 2: Run to verify fail**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_scoring.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

```python
# .system/eval/lib/scoring.py
"""Parse judge responses and aggregate scores."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass


@dataclass
class JudgeResponse:
    score: float
    reason: str


@dataclass
class Aggregate:
    accuracy_mean: float
    input_tokens_mean: float
    input_tokens_p95: float


_JSON_RE = re.compile(r"\{[^{}]*\"score\"[^{}]*\}", re.DOTALL)


def parse_judge_response(text: str) -> JudgeResponse:
    m = _JSON_RE.search(text)
    if m is None:
        return JudgeResponse(score=0.0, reason="malformed judge response")
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return JudgeResponse(score=0.0, reason="unparseable judge response")
    score = float(d.get("score", 0.0))
    score = max(0.0, min(1.0, score))
    reason = str(d.get("reason", ""))[:500]
    return JudgeResponse(score=score, reason=reason)


def aggregate(scores: list[float], input_tokens: list[int]) -> Aggregate:
    n = len(scores)
    if n == 0:
        return Aggregate(accuracy_mean=0.0, input_tokens_mean=0.0, input_tokens_p95=0.0)
    accuracy_mean = sum(scores) / n
    tokens_mean = sum(input_tokens) / len(input_tokens) if input_tokens else 0.0
    s = sorted(input_tokens)
    idx = min(len(s) - 1, max(0, int(round(0.95 * (len(s) - 1)))))
    p95 = float(s[idx])
    return Aggregate(accuracy_mean=accuracy_mean, input_tokens_mean=tokens_mean, input_tokens_p95=p95)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_scoring.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/lib/scoring.py .system/eval/tests/test_scoring.py && git commit -m "phase-2: judge response parser and aggregate math"
```

---

## Task 10: `report.py` (markdown report generator, no TDD — pure template render)

**Files:**
- Create: `.system/eval/lib/report.py`

- [ ] **Step 1: Write the generator**

```python
# .system/eval/lib/report.py
"""Render a Phase 2 eval run into a markdown report."""
from __future__ import annotations
from pathlib import Path


def render_report(summary: dict) -> str:
    """summary shape:
    {
      "run_id": str,
      "started_at": str,
      "completed_at": str,
      "config": dict,
      "tiers": [
        {
          "name": str,
          "n_planets": int | None,
          "cosmocache": {"accuracy_mean": float, "input_tokens_mean": float, "input_tokens_p95": float},
          "flatmemory":  {"accuracy_mean": float, "input_tokens_mean": float, "input_tokens_p95": float},
          "per_probe": [ {"probe_id": str, "cosmocache": {score, tokens}, "flatmemory": {score, tokens}}, ... ]
        }, ...
      ],
      "cost": {"total_input_tokens": int, "total_output_tokens": int, "usd_estimate": float}
    }
    """
    lines: list[str] = []
    lines.append(f"# Phase 2 Eval Report — {summary['run_id']}\n")
    lines.append(f"- started: {summary['started_at']}")
    lines.append(f"- completed: {summary['completed_at']}")
    lines.append("")

    lines.append("## Cost\n")
    c = summary["cost"]
    lines.append(f"- total input tokens: {c['total_input_tokens']:,}")
    lines.append(f"- total output tokens: {c['total_output_tokens']:,}")
    lines.append(f"- estimated USD: ${c['usd_estimate']:.2f}")
    lines.append("")

    lines.append("## Accuracy & token cost, by tier\n")
    lines.append("| Tier | N planets | Accuracy (cosmocache) | Accuracy (flat memory.md) | Input tokens mean (cc) | Input tokens mean (flat) |")
    lines.append("|---|---|---|---|---|---|")
    for t in summary["tiers"]:
        n = t["n_planets"] if t["n_planets"] is not None else "real"
        lines.append(
            f"| {t['name']} | {n} | "
            f"{t['cosmocache']['accuracy_mean']:.3f} | {t['flatmemory']['accuracy_mean']:.3f} | "
            f"{t['cosmocache']['input_tokens_mean']:.0f} | {t['flatmemory']['input_tokens_mean']:.0f} |"
        )
    lines.append("")

    lines.append("## Degradation curve\n")
    lines.append("Accuracy as the corpus grows. Real planets are always present; higher tiers add synthetic noise.\n")
    lines.append("```")
    for t in summary["tiers"]:
        n = t["n_planets"] if t["n_planets"] is not None else "real"
        lines.append(
            f"{str(n):>6}  cc={t['cosmocache']['accuracy_mean']:.3f}   flat={t['flatmemory']['accuracy_mean']:.3f}"
        )
    lines.append("```\n")

    lines.append("## Caveat on synthetic scaling\n")
    lines.append("Tiers at 10/30/100 planets are synthetic copies of the 3-planet seed. They measure "
                 "routing / index scaling and cross-planet interference, not authentic knowledge diversity. "
                 "Real-world 100-planet universes will differ; these numbers are an upper-bound reference.\n")

    lines.append("## Per-probe detail\n")
    for t in summary["tiers"]:
        lines.append(f"### tier: {t['name']}\n")
        lines.append("| probe_id | cc score | flat score | cc tokens | flat tokens |")
        lines.append("|---|---|---|---|---|")
        for p in t["per_probe"]:
            lines.append(
                f"| {p['probe_id']} | {p['cosmocache']['score']:.2f} | {p['flatmemory']['score']:.2f} | "
                f"{p['cosmocache']['tokens']} | {p['flatmemory']['tokens']} |"
            )
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/lib/report.py && git commit -m "phase-2: markdown report renderer"
```

---

## Task 11: `runner.py` with TDD (dry-run path only; live path exercised in Task 13)

**Files:**
- Test: `.system/eval/tests/conftest.py`
- Test: `.system/eval/tests/test_runner_dry_run.py`
- Create: `.system/eval/runner.py`

- [ ] **Step 1: Write the conftest**

```python
# .system/eval/tests/conftest.py
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".system/eval"))
```

- [ ] **Step 2: Write the failing dry-run test**

```python
# .system/eval/tests/test_runner_dry_run.py
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / ".system/eval/runner.py"
CONFIG = REPO / ".system/eval/configs/default.yaml"


def test_dry_run_completes_with_no_network():
    # Intentionally do NOT set ANTHROPIC_API_KEY.
    import os
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    result = subprocess.run(
        ["python3", str(RUNNER), "--config", str(CONFIG), "--dry-run"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}"
    assert "probes planned" in result.stdout.lower()


def test_dry_run_only_probes_subset():
    import os
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    result = subprocess.run(
        ["python3", str(RUNNER), "--config", str(CONFIG), "--dry-run",
         "--only-probes", "react-memoize-stable-reference,neg-kubernetes-decision"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0
    assert "2 probes planned" in result.stdout.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_runner_dry_run.py -v
```

Expected: FAIL — runner not written.

- [ ] **Step 4: Write `runner.py`**

```python
#!/usr/bin/env python3
"""Phase 2 eval harness runner."""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lib.anthropic_client import AnthropicClient, StubClient, BaseClient, CompletionResult
from lib.scoring import parse_judge_response, aggregate
from lib.report import render_report
from lib.tokens import TokenBudget

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

TIER_INCLUSION = {
    "small":  {"small"},
    "medium": {"small", "medium"},
    "large":  {"small", "medium", "large"},
    "real":   {"small", "medium", "large"},
}


def load_probes(only: list[str] | None) -> list[dict]:
    path = HERE / "scenarios/probes.yaml"
    d = yaml.safe_load(path.read_text())
    probes = d["probes"]
    if only:
        probes = [p for p in probes if p["id"] in set(only)]
    return probes


def plan_probes(probes: list[dict], tier_name: str) -> list[dict]:
    include = TIER_INCLUSION[tier_name]
    return [p for p in probes if p["scale_tier"] in include]


def build_cosmocache_prompt(universe_dir: Path, probe: dict) -> tuple[str, str]:
    # System: the cosmocache SessionStart injection — glossary only.
    gloss = (universe_dir / "enigma/glossary.md").read_text()
    system = f"You are Claude. The cosmocache SessionStart hook has injected the following:\n\n{gloss}\n\n" \
             "When answering a question about past work, if the glossary points to a planet, read " \
             "that planet's planet.md, its creature files, and its active generation. Cite facts from " \
             "those files. If nothing matches, say you don't know."

    # User: the probe question, plus a brief system-of-record hint.
    user = f"{probe['question']}\n\n" \
           f"(You may list the files you would read from the cosmocache at {universe_dir}. " \
           "Answer from those files. If you cannot find the answer, say so explicitly.)"
    return system, user


def build_flatmemory_prompt(flat_md: str, probe: dict) -> tuple[str, str]:
    system = "You are Claude. The following memory.md has been loaded at session start. " \
             "Answer from it. If nothing matches, say you don't know.\n\n" + flat_md
    user = probe["question"]
    return system, user


def run(config: dict, dry_run: bool, only_probes: list[str]) -> int:
    probes = load_probes(only_probes)
    tiers = config["scale_tiers"]

    total_planned = 0
    planned_by_tier: list[tuple[str, int]] = []
    for t in tiers:
        p = plan_probes(probes, t["name"])
        planned_by_tier.append((t["name"], len(p)))
        total_planned += len(p) * 2  # cosmocache + flatmemory

    print(f"{total_planned} probes planned (across {len(tiers)} tiers)")
    for name, n in planned_by_tier:
        print(f"  {name}: {n} probes x 2 systems = {n*2} calls")

    if dry_run:
        return 0

    # ---- live run path (exercised end-to-end in Task 13 / live-run task) ----
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set; live run aborted.", file=sys.stderr)
        return 2

    client: BaseClient = AnthropicClient()
    budget = TokenBudget(limit=config["budget"]["max_total_tokens_per_run"])

    run_id = config.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out_dir = HERE / "results" / run_id
    (out_dir / "probes").mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()

    # --- import here to avoid forcing test path to have these side effects ---
    from scenarios.synth_corpus import build_synthetic_universe
    from baselines.flatten_to_memory_md import flatten

    tier_summaries = []
    for t in tiers:
        tier_name = t["name"]
        tier_probes = plan_probes(probes, tier_name)
        if not tier_probes:
            continue

        if t["n_planets"] is None:
            universe = HERE / "scenarios/seed_universe"
        else:
            import tempfile
            tmp = Path(tempfile.mkdtemp(prefix=f"cosmocache-synth-{tier_name}-"))
            universe = build_synthetic_universe(HERE / "scenarios/seed_universe", t["n_planets"], tmp)

        flat_md = flatten(universe, now="2026-04-13T00:00:00Z")

        per_probe_results = []
        cc_scores, cc_tokens, flat_scores, flat_tokens = [], [], [], []
        for probe in tier_probes:
            if budget.exceeded():
                print(f"BUDGET EXCEEDED at tier={tier_name}, probe={probe['id']}; writing partial results.")
                break

            sys_a, usr_a = build_cosmocache_prompt(universe, probe)
            a = client.complete(system=sys_a, user=usr_a,
                                model=config["system_under_test"]["model"],
                                temperature=config["system_under_test"]["temperature"],
                                max_tokens=config["system_under_test"]["max_tokens"])
            budget.charge(a.input_tokens + a.output_tokens)

            sys_b, usr_b = build_flatmemory_prompt(flat_md, probe)
            b = client.complete(system=sys_b, user=usr_b,
                                model=config["system_under_test"]["model"],
                                temperature=config["system_under_test"]["temperature"],
                                max_tokens=config["system_under_test"]["max_tokens"])
            budget.charge(b.input_tokens + b.output_tokens)

            judge_prompt_tmpl = (HERE / "prompts/judge.txt").read_text()
            ja = client.complete(system="", user=judge_prompt_tmpl.format(
                question=probe["question"], expected_fact=probe["expected_fact"], answer=a.text),
                model=config["judge"]["model"], temperature=config["judge"]["temperature"],
                max_tokens=config["judge"]["max_tokens"])
            jb = client.complete(system="", user=judge_prompt_tmpl.format(
                question=probe["question"], expected_fact=probe["expected_fact"], answer=b.text),
                model=config["judge"]["model"], temperature=config["judge"]["temperature"],
                max_tokens=config["judge"]["max_tokens"])
            budget.charge(ja.input_tokens + ja.output_tokens + jb.input_tokens + jb.output_tokens)

            ja_r = parse_judge_response(ja.text)
            jb_r = parse_judge_response(jb.text)

            result = {
                "probe_id": probe["id"],
                "cosmocache": {"answer": a.text, "tokens": a.input_tokens, "score": ja_r.score, "reason": ja_r.reason},
                "flatmemory": {"answer": b.text, "tokens": b.input_tokens, "score": jb_r.score, "reason": jb_r.reason},
            }
            per_probe_results.append(result)
            (out_dir / "probes" / f"{tier_name}-{probe['id']}.json").write_text(json.dumps(result, indent=2))

            cc_scores.append(ja_r.score); cc_tokens.append(a.input_tokens)
            flat_scores.append(jb_r.score); flat_tokens.append(b.input_tokens)

        cc = aggregate(cc_scores, cc_tokens)
        fl = aggregate(flat_scores, flat_tokens)
        tier_summaries.append({
            "name": tier_name,
            "n_planets": t["n_planets"],
            "cosmocache": {"accuracy_mean": cc.accuracy_mean,
                           "input_tokens_mean": cc.input_tokens_mean,
                           "input_tokens_p95": cc.input_tokens_p95},
            "flatmemory": {"accuracy_mean": fl.accuracy_mean,
                           "input_tokens_mean": fl.input_tokens_mean,
                           "input_tokens_p95": fl.input_tokens_p95},
            "per_probe": [
                {"probe_id": r["probe_id"],
                 "cosmocache": {"score": r["cosmocache"]["score"], "tokens": r["cosmocache"]["tokens"]},
                 "flatmemory": {"score": r["flatmemory"]["score"], "tokens": r["flatmemory"]["tokens"]}}
                for r in per_probe_results
            ],
        })

    completed_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "config": config,
        "tiers": tier_summaries,
        "cost": {
            "total_input_tokens": budget.spent,   # rough; live path can split if desired
            "total_output_tokens": 0,
            "usd_estimate": round(budget.spent / 1_000_000 * 15.0, 2),  # rough Opus input price
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "report.md").write_text(render_report(summary))
    print(f"Run {run_id} complete. Report: {out_dir / 'report.md'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-probes", type=str, default="")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    dry_run = args.dry_run or cfg.get("dry_run", False)
    only = [s.strip() for s in args.only_probes.split(",") if s.strip()] or cfg.get("only_probes") or []
    return run(cfg, dry_run=dry_run, only_probes=only)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the dry-run tests**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_runner_dry_run.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/runner.py .system/eval/tests/conftest.py .system/eval/tests/test_runner_dry_run.py && git commit -m "phase-2: runner with dry-run mode"
```

---

## Task 12: `planet_scope.py` — Phase 3's library entry point

**Files:**
- Test: `.system/eval/tests/test_planet_scope.py`
- Create: `.system/eval/lib/planet_scope.py`

- [ ] **Step 1: Write the failing test**

```python
# .system/eval/tests/test_planet_scope.py
from pathlib import Path
import sys
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".system/eval"))

from lib.planet_scope import score_planet, PlanetScore   # noqa: E402
from lib.anthropic_client import StubClient, CompletionResult   # noqa: E402


def test_score_planet_returns_accuracy_and_tokens():
    stub = StubClient(default=CompletionResult(text='{"score": 1.0, "reason": "match"}', input_tokens=80, output_tokens=40))
    universe = REPO / ".system/eval/scenarios/seed_universe"
    res: PlanetScore = score_planet(
        planet_slug="react",
        universe_dir=universe,
        probe_subset=["react-memoize-stable-reference", "react-wisdom-distilled-composition"],
        client=stub,
        judge_model="claude-opus-4-6",
        sut_model="claude-opus-4-6",
    )
    assert isinstance(res.accuracy_mean, float)
    assert res.n_probes == 2
    assert res.input_tokens_mean > 0
```

- [ ] **Step 2: Run to verify fail**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_planet_scope.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Write the implementation**

```python
# .system/eval/lib/planet_scope.py
"""Phase 3 entry point: score a single planet against a probe subset."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

from .anthropic_client import BaseClient
from .scoring import parse_judge_response, aggregate

HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE.parent


@dataclass
class PlanetScore:
    planet_slug: str
    accuracy_mean: float
    input_tokens_mean: float
    input_tokens_p95: float
    n_probes: int


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
) -> PlanetScore:
    probes_all = yaml.safe_load((EVAL_ROOT / "scenarios/probes.yaml").read_text())["probes"]
    selected = [p for p in probes_all if p["id"] in set(probe_subset)]

    # Lazy imports so the planet_scope module stays light
    from baselines.flatten_to_memory_md import flatten  # noqa: PLC0415
    # scoring uses cosmocache-style prompting only (we are scoring a cosmocache variant)
    gloss = (universe_dir / "enigma/glossary.md").read_text()
    system = f"You are Claude. The cosmocache SessionStart hook has injected:\n\n{gloss}\n\n" \
             "Answer from the planet's files; if nothing matches, say so."

    judge_tmpl = (EVAL_ROOT / "prompts/judge.txt").read_text()

    scores, tokens = [], []
    for probe in selected:
        user = probe["question"]
        ans = client.complete(system=system, user=user, model=sut_model,
                              temperature=sut_temperature, max_tokens=sut_max_tokens)
        j = client.complete(system="", user=judge_tmpl.format(
            question=probe["question"], expected_fact=probe["expected_fact"], answer=ans.text),
            model=judge_model, temperature=judge_temperature, max_tokens=judge_max_tokens)
        scores.append(parse_judge_response(j.text).score)
        tokens.append(ans.input_tokens)

    agg = aggregate(scores, tokens)
    return PlanetScore(
        planet_slug=planet_slug,
        accuracy_mean=agg.accuracy_mean,
        input_tokens_mean=agg.input_tokens_mean,
        input_tokens_p95=agg.input_tokens_p95,
        n_probes=len(selected),
    )
```

- [ ] **Step 4: Run to verify pass**

```bash
cd /Users/bot/universe/.system/eval && python3 -m pytest tests/test_planet_scope.py -v
```

Expected: test passes.

- [ ] **Step 5: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/lib/planet_scope.py .system/eval/tests/test_planet_scope.py && git commit -m "phase-2: score_planet entry point for Phase 3"
```

---

## Task 13: Aggregate test runner + first full test pass

**Files:**
- Create: `.system/eval/tests/run-tests.sh`

- [ ] **Step 1: Write the runner**

```bash
#!/usr/bin/env bash
# Runs the Phase 2 eval harness unit tests.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
python3 -m pytest tests/ -v
```

Make it executable:

```bash
chmod +x /Users/bot/universe/.system/eval/tests/run-tests.sh
```

- [ ] **Step 2: Run it**

```bash
/Users/bot/universe/.system/eval/tests/run-tests.sh
```

Expected: all tests across `test_flatten`, `test_synth_corpus`, `test_scoring`, `test_runner_dry_run`, `test_planet_scope` pass (roughly 17+ assertions).

- [ ] **Step 3: Commit**

```bash
cd /Users/bot/universe && git add .system/eval/tests/run-tests.sh && git commit -m "phase-2: aggregate eval test runner"
```

---

## Task 14: First live run + README update

**This task requires `ANTHROPIC_API_KEY` and will spend real tokens.** Estimated cost at default config: roughly 25 probes × (2 SUT calls + 2 judge calls) × 4 tiers ≈ 400 API calls. At Opus-4.6 pricing and avg ~1.5k input tokens, expect ~$10–$25. Confirm with the user before running.

- [ ] **Step 1: Sanity dry-run**

```bash
cd /Users/bot/universe/.system/eval && python3 runner.py --config configs/default.yaml --dry-run
```

Expected: "N probes planned" output, no API calls.

- [ ] **Step 2: Trim to `real`-tier only for first live smoke** (cheaper, ~$1)

Create `configs/smoke.yaml` as a copy of `default.yaml` with `scale_tiers` reduced to only `{ name: real, n_planets: null }`, then:

```bash
python3 runner.py --config configs/smoke.yaml
```

Expected: `results/<run-id>/report.md` exists with accuracy and token columns filled in for the 3-planet real fixture.

- [ ] **Step 3: Full live run** (user-approved)

Only after user has reviewed the smoke-run cost and approves:

```bash
python3 runner.py --config configs/default.yaml
```

- [ ] **Step 4: Update README with real numbers**

Replace the Phase-2-pending paragraph in `/Users/bot/universe/README.md` (the "Why not just `memory.md`?" section's final paragraph) with a short summary block citing the run id, the accuracy table, and a link to `.system/eval/results/<run-id>/report.md`.

- [ ] **Step 5: Commit**

```bash
cd /Users/bot/universe && git add README.md .system/eval/results/<run-id> && git commit -m "phase-2: first live run results and README numbers update"
```

---

## Task 15: Phase 3 handoff note

**Files:**
- Create: `.system/docs/specs/2026-04-13-phase-3-civilization-evolution-design-stub.md`

- [ ] **Step 1: Write a stub** that freezes the `score_planet` contract and lists open questions for Phase 3 brainstorming. Keep it brief (under one screen). Commit and stop.

```markdown
# Phase 3 — Civilization Evolution (design stub)

Phase 2 has shipped; `lib/planet_scope.py:score_planet` is now the stable entry
point Phase 3 will use as its fitness function.

## Open design questions (brainstorming inputs)

1. Which mutation types enter v1 beyond pure distillation?
2. Trigger model: manual only for v1, or cron from day one?
3. Per-invocation dollar budget — what number?
4. Branch-and-merge vs commit-and-revert for evolution outcomes?
5. How does an evolution promote a planet into a new generation?

Design spec to be written via the brainstorming skill after Phase 2 numbers
are in hand and have informed which gaps evolution should target.
```

```bash
cd /Users/bot/universe && git add .system/docs/specs/2026-04-13-phase-3-civilization-evolution-design-stub.md && git commit -m "phase-3: design stub, awaiting brainstorm after Phase 2 numbers"
```

---

## Decisions Locked In This Plan

- Python runner (not bash) — API calls + JSON aggregation want a real language.
- One hand-curated fixture universe in-repo (`seed_universe/`) so tests and probes don't drift against lived cosmocache.
- Synthetic corpora are temp-dir only; real universe is never touched by the runner.
- Judge is Claude Opus 4.6, temp 0. Configurable for future cross-checks.
- Dry-run path is the test-covered path; live path is exercised only by Task 14's user-approved smoke run.
- `score_planet` is the frozen API surface for Phase 3.
- No synthetic probe generator in v1 (`scenarios/generate.py` deferred).
- No non-Claude secondary judge in v1.
