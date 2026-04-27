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


def test_migration_upgrades_old_schema_preserving_rows(tmp_path, monkeypatch):
    """Pre-create an old-schema DB with one row, then call _connect()
    and verify the row survived AND the new statuses are now accepted."""
    monkeypatch.setenv("UNIVERSE_ROOT", str(tmp_path))
    (tmp_path / "enigma").mkdir()

    # Hand-build the OLD schema (no mutation_* in the CHECK constraint).
    db = tmp_path / "enigma" / "evolutions.db"
    import sqlite3 as _sql
    conn = _sql.connect(str(db))
    conn.executescript("""
        CREATE TABLE evolutions (
          planet_slug   TEXT PRIMARY KEY,
          status        TEXT NOT NULL CHECK (status IN
                           ('pending','running','complete','failed')),
          message       TEXT,
          started_at    TEXT,
          updated_at    TEXT NOT NULL,
          completed_at  TEXT,
          session_id    TEXT
        );
        INSERT INTO evolutions
          (planet_slug, status, message, started_at, updated_at)
        VALUES ('planet-legacy', 'complete', 'pre-migration row',
                '2026-04-01T00:00:00Z', '2026-04-01T00:00:00Z');
    """)
    conn.commit()
    conn.close()

    # Now call _connect() — this should run the migration.
    import importlib
    import evolve
    importlib.reload(evolve)
    new_conn = evolve._connect()

    # Pre-existing row survived.
    rows = new_conn.execute(
        "SELECT planet_slug, status, message FROM evolutions"
    ).fetchall()
    assert any(r["planet_slug"] == "planet-legacy" for r in rows)

    # New statuses are now accepted.
    now = evolve._now_iso(new_conn)
    new_conn.execute(
        "INSERT INTO evolutions "
        "(planet_slug, status, message, started_at, updated_at, completed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("planet-new", "mutation_promoted", "post-migration", now, now, now),
    )
    new_conn.commit()
    statuses = {r["status"] for r in new_conn.execute(
        "SELECT status FROM evolutions").fetchall()}
    assert "mutation_promoted" in statuses
    assert "complete" in statuses  # legacy status still valid
