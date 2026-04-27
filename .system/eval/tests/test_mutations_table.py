import sys
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))


def test_evolve_connect_creates_mutations_table(tmp_path, monkeypatch):
    """The mutations history table is created idempotently on _connect()."""
    monkeypatch.setenv("UNIVERSE_ROOT", str(tmp_path))
    (tmp_path / "enigma").mkdir()
    import importlib
    import evolve
    importlib.reload(evolve)

    conn = evolve._connect()
    # Insert a row to verify the schema is what we expect.
    now = evolve._now_iso(conn)
    conn.execute(
        "INSERT INTO mutations "
        "(planet_slug, creature, outcome, reason, "
        " accuracy_delta, tokens_delta, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("planet-x", "alice.md", "promoted",
         "tokens 1000 -> 800", 0.0, -200.0, now),
    )
    conn.execute(
        "INSERT INTO mutations "
        "(planet_slug, creature, outcome, reason, "
        " accuracy_delta, tokens_delta, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("planet-x", "bob.md", "rejected",
         "no token savings", 0.0, 0.0, now),
    )
    conn.commit()

    # Both rows persist — this is true history, not single-state-per-slug.
    rows = conn.execute(
        "SELECT planet_slug, outcome, creature FROM mutations "
        "ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["outcome"] == "promoted"
    assert rows[1]["outcome"] == "rejected"

    # Both for the SAME planet — unlike evolutions, mutations holds many rows per slug.
    assert {r["planet_slug"] for r in rows} == {"planet-x"}


def test_invalid_outcome_rejected_by_check_constraint(tmp_path, monkeypatch):
    monkeypatch.setenv("UNIVERSE_ROOT", str(tmp_path))
    (tmp_path / "enigma").mkdir()
    import importlib
    import evolve
    importlib.reload(evolve)
    conn = evolve._connect()
    now = evolve._now_iso(conn)
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO mutations "
            "(planet_slug, outcome, completed_at) "
            "VALUES (?, ?, ?)",
            ("p", "totally-bogus-outcome", now),
        )
