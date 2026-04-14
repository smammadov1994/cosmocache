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
    rows = [l for l in gloss.splitlines() if l.startswith("| planet-")]
    assert len(rows) == 30


def test_does_not_mutate_seed(tmp_path):
    seed = REPO / ".system/eval/scenarios/seed_universe"
    seed_planets_before = sorted(p.name for p in (seed / "planets").glob("planet-*"))
    _ = build_synthetic_universe(seed, target_n_planets=10, out_dir=tmp_path / "u10")
    seed_planets_after = sorted(p.name for p in (seed / "planets").glob("planet-*"))
    assert seed_planets_before == seed_planets_after
