import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

from mutation_tick import find_candidate  # noqa: E402


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_returns_none_when_no_creatures_dir(tmp_path):
    (tmp_path / "planet.md").write_text("# planet\n")
    assert find_candidate(tmp_path) is None


def test_returns_none_when_creatures_dir_empty(tmp_path):
    (tmp_path / "creatures").mkdir()
    assert find_candidate(tmp_path) is None


def test_returns_none_when_only_short_creatures(tmp_path):
    cdir = tmp_path / "creatures"
    cdir.mkdir()
    _write(cdir / "tiny.md", "## Journal\nshort entry\n")
    assert find_candidate(tmp_path) is None  # below 1500-char threshold


def test_returns_longest_creature_lacking_distilled_wisdom(tmp_path):
    cdir = tmp_path / "creatures"
    cdir.mkdir()
    long_journal = "## Journal\n" + ("x " * 800) + "\n"
    _write(cdir / "verbose.md", long_journal)
    _write(cdir / "shorter.md", "## Journal\n" + ("y " * 100))
    pick = find_candidate(tmp_path)
    assert pick is not None
    assert pick.name == "verbose.md"


def test_skips_creatures_with_distilled_wisdom_unless_journal_doubled(tmp_path):
    cdir = tmp_path / "creatures"
    cdir.mkdir()
    body = (
        "## Distilled Wisdom\nold summary line one\nold summary line two\n\n"
        "## Journal\n" + ("x " * 600) + "\n"
    )
    _write(cdir / "already-distilled.md", body)
    assert find_candidate(tmp_path) is None


def test_picks_creature_whose_journal_outgrew_distilled_wisdom(tmp_path):
    """Once journal is >= 2x the wisdom block, redistill it."""
    cdir = tmp_path / "creatures"
    cdir.mkdir()
    body = (
        "## Distilled Wisdom\nshort summary\n\n"
        "## Journal\n" + ("x " * 2000) + "\n"
    )
    _write(cdir / "outgrown.md", body)
    pick = find_candidate(tmp_path)
    assert pick is not None
    assert pick.name == "outgrown.md"
