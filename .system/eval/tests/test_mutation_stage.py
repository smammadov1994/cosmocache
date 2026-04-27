import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

from mutation_tick import stage_mutation  # noqa: E402


def _make_universe(tmp_path: Path) -> Path:
    """Build a minimal universe layout under tmp_path/universe."""
    u = tmp_path / "universe"
    (u / "enigma").mkdir(parents=True)
    (u / "enigma" / "glossary.md").write_text("# glossary\n")
    pdir = u / "planets" / "planet-test"
    (pdir / "creatures").mkdir(parents=True)
    (pdir / "planet.md").write_text("---\nkeywords: [test]\n---\n# test\n")
    (pdir / "creatures" / "alice.md").write_text("original alice\n")
    (pdir / "creatures" / "bob.md").write_text("original bob\n")
    return u


def test_stage_creates_temp_universe_with_replacement(tmp_path):
    u = _make_universe(tmp_path)
    creature = u / "planets" / "planet-test" / "creatures" / "alice.md"
    staged_root, staged_creature = stage_mutation(
        universe_dir=u,
        creature_path=creature,
        new_content="distilled alice\n",
    )
    try:
        # staged universe is at a different path
        assert staged_root != u
        # staged creature has the new content
        assert staged_creature.read_text() == "distilled alice\n"
        # other creatures are copied verbatim
        bob = staged_root / "planets" / "planet-test" / "creatures" / "bob.md"
        assert bob.read_text() == "original bob\n"
        # glossary is copied
        gloss = staged_root / "enigma" / "glossary.md"
        assert gloss.read_text() == "# glossary\n"
        # original creature is UNTOUCHED
        assert creature.read_text() == "original alice\n"
    finally:
        import shutil
        # staged_root is tmpdir/universe; the actual tempdir is its parent.
        shutil.rmtree(staged_root.parent, ignore_errors=True)


def test_stage_returns_creature_under_staged_root(tmp_path):
    u = _make_universe(tmp_path)
    creature = u / "planets" / "planet-test" / "creatures" / "alice.md"
    staged_root, staged_creature = stage_mutation(
        universe_dir=u, creature_path=creature, new_content="x",
    )
    try:
        # staged_creature path is INSIDE staged_root
        assert staged_root in staged_creature.parents
        # and same relative position
        rel_orig = creature.relative_to(u)
        rel_staged = staged_creature.relative_to(staged_root)
        assert rel_orig == rel_staged
    finally:
        import shutil
        # staged_root is tmpdir/universe; the actual tempdir is its parent.
        shutil.rmtree(staged_root.parent, ignore_errors=True)
