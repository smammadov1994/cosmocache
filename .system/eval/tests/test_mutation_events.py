import os
import sys
import sqlite3
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))


def test_evolutions_table_accepts_mutation_statuses(tmp_path, monkeypatch):
    monkeypatch.setenv("UNIVERSE_ROOT", str(tmp_path))
    (tmp_path / "enigma").mkdir()
    import importlib
    import evolve
    importlib.reload(evolve)  # rebind _db_path() to new env

    conn = evolve._connect()
    now = evolve._now_iso(conn)
    # both new statuses must be accepted by the CHECK constraint
    for status in ("mutation_promoted", "mutation_rejected"):
        conn.execute(
            "INSERT INTO evolutions "
            "(planet_slug, status, message, started_at, updated_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (f"planet-{status}", status, "test", now, now, now),
        )
    conn.commit()
    rows = conn.execute(
        "SELECT planet_slug, status FROM evolutions ORDER BY planet_slug"
    ).fetchall()
    assert {r["status"] for r in rows} >= {"mutation_promoted", "mutation_rejected"}
