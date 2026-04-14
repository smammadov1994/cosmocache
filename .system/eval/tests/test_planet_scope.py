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
