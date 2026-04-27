import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / ".system/eval"))

import mutation_tick  # noqa: E402
from lib.anthropic_client import StubClient, CompletionResult  # noqa: E402
from lib.planet_scope import PlanetScore  # noqa: E402


def _build_universe(tmp_path, journal_chars=2000):
    u = tmp_path / "universe"
    (u / "enigma").mkdir(parents=True)
    (u / "enigma" / "glossary.md").write_text("# glossary\n")
    pdir = u / "planets" / "planet-test"
    (pdir / "creatures").mkdir(parents=True)
    (pdir / "planet.md").write_text("---\nkeywords: [test]\n---\n# test\n")
    journal = "## Journal\n" + ("x " * journal_chars) + "\n"
    (pdir / "creatures" / "verbose.md").write_text(journal)
    return u


DISTILLED = """---
name: x
---

## Distilled Wisdom
- key fact one
- key fact two
"""


def test_promote_when_score_improves(tmp_path, monkeypatch):
    u = _build_universe(tmp_path)
    stub = StubClient(default=CompletionResult(
        text=DISTILLED, input_tokens=80, output_tokens=40,
    ))

    # Stub the scorer: baseline = high tokens, mutant = lower tokens, same accuracy
    calls = {"baseline": None, "mutant": None}

    def fake_score(*, planet_slug, universe_dir, **kw):
        if str(universe_dir).endswith("/universe") and "mutation" not in str(universe_dir):
            calls["baseline"] = universe_dir
            return PlanetScore(planet_slug, 0.90, 1000.0, 1100.0, 5)
        calls["mutant"] = universe_dir
        return PlanetScore(planet_slug, 0.90, 600.0, 700.0, 5)

    monkeypatch.setattr(mutation_tick, "_score", fake_score)

    result = mutation_tick.run(
        planet_slug="planet-test",
        planet_dir=u / "planets" / "planet-test",
        universe_dir=u,
        probe_subset=["any"],
        client=stub,
        proposer_model="claude-haiku-4-5-20251001",
        sut_model="claude-opus-4-6",
        judge_model="claude-opus-4-6",
    )
    assert result.outcome == "promoted"
    creature = u / "planets" / "planet-test" / "creatures" / "verbose.md"
    # original was overwritten with the distilled version
    assert "Distilled Wisdom" in creature.read_text()


def test_reject_when_accuracy_drops(tmp_path, monkeypatch):
    u = _build_universe(tmp_path)
    creature = u / "planets" / "planet-test" / "creatures" / "verbose.md"
    original_text = creature.read_text()
    original_mtime_ns = creature.stat().st_mtime_ns
    stub = StubClient(default=CompletionResult(
        text=DISTILLED, input_tokens=80, output_tokens=40,
    ))

    def fake_score(*, planet_slug, universe_dir, **kw):
        if "mutation" in str(universe_dir):
            return PlanetScore(planet_slug, 0.70, 500.0, 600.0, 5)  # accuracy dropped
        return PlanetScore(planet_slug, 0.90, 1000.0, 1100.0, 5)

    monkeypatch.setattr(mutation_tick, "_score", fake_score)

    result = mutation_tick.run(
        planet_slug="planet-test",
        planet_dir=u / "planets" / "planet-test",
        universe_dir=u,
        probe_subset=["any"],
        client=stub,
        proposer_model="claude-haiku-4-5-20251001",
        sut_model="claude-opus-4-6",
        judge_model="claude-opus-4-6",
    )
    assert result.outcome == "rejected"
    # Spec invariant: on rejection, the original file is NEVER touched.
    assert creature.read_text() == original_text
    assert creature.stat().st_mtime_ns == original_mtime_ns


def test_no_candidate_returns_skipped(tmp_path, monkeypatch):
    u = _build_universe(tmp_path, journal_chars=10)  # too short to qualify
    stub = StubClient(default=CompletionResult(
        text=DISTILLED, input_tokens=10, output_tokens=10,
    ))
    # _score should never be called when there's no candidate
    monkeypatch.setattr(mutation_tick, "_score",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("scorer called")))
    result = mutation_tick.run(
        planet_slug="planet-test",
        planet_dir=u / "planets" / "planet-test",
        universe_dir=u,
        probe_subset=["any"],
        client=stub,
        proposer_model="claude-haiku-4-5-20251001",
        sut_model="claude-opus-4-6",
        judge_model="claude-opus-4-6",
    )
    assert result.outcome == "skipped"


def test_cleanup_runs_even_when_mutant_scoring_raises(tmp_path, monkeypatch):
    """The temp universe must be cleaned up regardless of scoring success."""
    import tempfile
    import os
    u = _build_universe(tmp_path)
    stub = StubClient(default=CompletionResult(
        text=DISTILLED, input_tokens=80, output_tokens=40,
    ))

    seen = {}

    def fake_score(*, planet_slug, universe_dir, **kw):
        if "mutation" in str(universe_dir):
            seen["staged"] = Path(str(universe_dir))
            raise RuntimeError("network exploded")
        return PlanetScore(planet_slug, 0.90, 1000.0, 1100.0, 5)

    monkeypatch.setattr(mutation_tick, "_score", fake_score)

    result = mutation_tick.run(
        planet_slug="planet-test",
        planet_dir=u / "planets" / "planet-test",
        universe_dir=u,
        probe_subset=["any"],
        client=stub,
        proposer_model="claude-haiku-4-5-20251001",
        sut_model="claude-opus-4-6",
        judge_model="claude-opus-4-6",
    )
    # The mutant-score error becomes a rejected MutationResult, not a raise.
    assert result.outcome == "rejected"
    assert "mutant scoring" in result.reason.lower() or "network exploded" in result.reason.lower()
    # And the staged tempdir must be gone.
    if "staged" in seen:
        # staged universe path was tempdir/universe; tempdir = staged.parent
        assert not seen["staged"].parent.exists(), \
            f"staged tempdir leaked: {seen['staged'].parent}"


def test_proposer_error_returns_rejected(tmp_path, monkeypatch):
    """If propose_distillation raises ValueError (e.g. missing frontmatter),
    the orchestrator returns rejected — it does not bubble."""
    u = _build_universe(tmp_path)
    creature = u / "planets" / "planet-test" / "creatures" / "verbose.md"
    original_mtime_ns = creature.stat().st_mtime_ns

    # StubClient returns garbage with no frontmatter — proposer will raise ValueError
    stub = StubClient(default=CompletionResult(
        text="not markdown, no frontmatter here",
        input_tokens=10, output_tokens=10,
    ))
    # _score must not be called when the proposer fails
    monkeypatch.setattr(mutation_tick, "_score",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("scorer called on proposer failure")))

    result = mutation_tick.run(
        planet_slug="planet-test",
        planet_dir=u / "planets" / "planet-test",
        universe_dir=u,
        probe_subset=["any"],
        client=stub,
        proposer_model="claude-haiku-4-5-20251001",
        sut_model="claude-opus-4-6",
        judge_model="claude-opus-4-6",
    )
    assert result.outcome == "rejected"
    assert "proposer" in result.reason.lower()
    # Original is untouched.
    assert creature.stat().st_mtime_ns == original_mtime_ns
