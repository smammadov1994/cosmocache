#!/usr/bin/env python3
"""evolve.py — CLI for the universe-wide evolutions table.

Source of truth for "is a subagent currently researching planet X?"
Replaces the old `.evolving` marker-file mechanism with a single SQLite
DB (`<UNIVERSE_ROOT>/enigma/evolutions.db`) so multiple processes can
write concurrently and the dashboard can poll a tiny rendered file.

Schema (current-state-only, keyed by slug):

    CREATE TABLE evolutions (
      planet_slug   TEXT PRIMARY KEY,
      status        TEXT NOT NULL CHECK (status IN
                       ('pending','running','complete','failed',
                        'mutation_promoted','mutation_rejected')),
      message       TEXT,
      started_at    TEXT,        -- ISO8601 UTC, e.g. 2026-04-14T02:14:01Z
      updated_at    TEXT NOT NULL,
      completed_at  TEXT,
      session_id    TEXT
    );

Stdlib only — sqlite3 + argparse.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path


def _db_path() -> Path:
    root = Path(os.environ.get("UNIVERSE_ROOT", "/Users/bot/universe"))
    return root / "enigma" / "evolutions.db"


def _now_iso(conn: sqlite3.Connection) -> str:
    # sqlite's datetime('now') yields "YYYY-MM-DD HH:MM:SS" in UTC; we
    # reformat to ISO8601 with a trailing Z for unambiguous parsing.
    raw = conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%SZ', 'now')").fetchone()[0]
    return raw


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evolutions (
          planet_slug   TEXT PRIMARY KEY,
          status        TEXT NOT NULL CHECK (status IN
                           ('pending','running','complete','failed',
                            'mutation_promoted','mutation_rejected')),
          message       TEXT,
          started_at    TEXT,
          updated_at    TEXT NOT NULL,
          completed_at  TEXT,
          session_id    TEXT
        )
        """
    )
    # Phase 3: extend the CHECK constraint on existing DBs by recreating the
    # table. SQLite cannot ALTER TABLE a CHECK constraint, so we copy.
    #
    # Concurrency: multiple processes may call _connect() at once. We grab
    # an exclusive write lock with BEGIN IMMEDIATE, then re-read the live
    # DDL *inside* the transaction. The first writer rebuilds the table;
    # any process that was waiting on the lock then sees the new DDL and
    # skips the rebuild — so no two processes ever try to RENAME the same
    # table.
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='evolutions'"
    ).fetchone()
    if cur and "mutation_promoted" not in cur[0]:
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur2 = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='evolutions'"
            ).fetchone()
            if cur2 and "mutation_promoted" not in cur2[0]:
                conn.execute("ALTER TABLE evolutions RENAME TO evolutions_v1")
                conn.execute(
                    """
                    CREATE TABLE evolutions (
                      planet_slug   TEXT PRIMARY KEY,
                      status        TEXT NOT NULL CHECK (status IN
                                       ('pending','running','complete','failed',
                                        'mutation_promoted','mutation_rejected')),
                      message       TEXT,
                      started_at    TEXT,
                      updated_at    TEXT NOT NULL,
                      completed_at  TEXT,
                      session_id    TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO evolutions
                      (planet_slug, status, message, started_at, updated_at,
                       completed_at, session_id)
                    SELECT planet_slug, status, message, started_at, updated_at,
                           completed_at, session_id
                    FROM evolutions_v1
                    """
                )
                conn.execute("DROP TABLE evolutions_v1")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    # Phase 3 (post-review): a separate history table for mutation outcomes.
    # `evolutions` is single-state-per-slug (PRIMARY KEY planet_slug) and is
    # finalized by evolve("complete", ...) at the end of each tick — so it
    # cannot also hold per-mutation history. The `mutations` table accumulates
    # one row per propose-stage-score-gate attempt, keyed by an autoincrement
    # id with a (planet_slug, completed_at) index for fast per-planet listing.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mutations (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          planet_slug   TEXT NOT NULL,
          creature      TEXT,
          outcome       TEXT NOT NULL CHECK (outcome IN ('promoted', 'rejected')),
          reason        TEXT,
          accuracy_delta REAL,
          tokens_delta   REAL,
          completed_at  TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mutations_planet_time "
        "ON mutations (planet_slug, completed_at DESC)"
    )
    conn.commit()
    return conn


def cmd_start(args: argparse.Namespace) -> int:
    conn = _connect()
    now = _now_iso(conn)
    conn.execute(
        """
        INSERT OR REPLACE INTO evolutions
          (planet_slug, status, message, started_at, updated_at,
           completed_at, session_id)
        VALUES (?, 'running', ?, ?, ?, NULL, ?)
        """,
        (args.slug, args.msg, now, now, args.session_id),
    )
    conn.commit()
    print(f"started: {args.slug}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    conn = _connect()
    now = _now_iso(conn)
    cur = conn.execute("SELECT 1 FROM evolutions WHERE planet_slug = ?", (args.slug,))
    if cur.fetchone() is None:
        # auto-create a running row so callers don't have to start first
        conn.execute(
            """
            INSERT INTO evolutions
              (planet_slug, status, message, started_at, updated_at)
            VALUES (?, 'running', ?, ?, ?)
            """,
            (args.slug, args.msg, now, now),
        )
    elif args.msg is not None:
        conn.execute(
            "UPDATE evolutions SET status='running', message=?, updated_at=? "
            "WHERE planet_slug=?",
            (args.msg, now, args.slug),
        )
    else:
        conn.execute(
            "UPDATE evolutions SET status='running', updated_at=? "
            "WHERE planet_slug=?",
            (now, args.slug),
        )
    conn.commit()
    print(f"updated: {args.slug}")
    return 0


def _finalize(slug: str, status: str, msg: str | None) -> int:
    conn = _connect()
    now = _now_iso(conn)
    cur = conn.execute("SELECT 1 FROM evolutions WHERE planet_slug = ?", (slug,))
    if cur.fetchone() is None:
        conn.execute(
            """
            INSERT INTO evolutions
              (planet_slug, status, message, started_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (slug, status, msg, now, now, now),
        )
    elif msg is not None:
        conn.execute(
            "UPDATE evolutions SET status=?, message=?, updated_at=?, "
            "completed_at=? WHERE planet_slug=?",
            (status, msg, now, now, slug),
        )
    else:
        conn.execute(
            "UPDATE evolutions SET status=?, updated_at=?, completed_at=? "
            "WHERE planet_slug=?",
            (status, now, now, slug),
        )
    conn.commit()
    print(f"{status}: {slug}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    return _finalize(args.slug, "complete", args.msg)


def cmd_fail(args: argparse.Namespace) -> int:
    return _finalize(args.slug, "failed", args.msg)


def cmd_list(_: argparse.Namespace) -> int:
    conn = _connect()
    rows = conn.execute("SELECT * FROM evolutions ORDER BY planet_slug").fetchall()
    print(json.dumps([dict(r) for r in rows], indent=2))
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    conn = _connect()
    conn.execute("DELETE FROM evolutions WHERE planet_slug = ?", (args.slug,))
    conn.commit()
    print(f"cleared: {args.slug}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evolve.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_slug_msg(name: str, fn, with_session: bool = False):
        sp = sub.add_parser(name)
        sp.add_argument("slug")
        sp.add_argument("--msg")
        if with_session:
            sp.add_argument("--session-id", dest="session_id")
        sp.set_defaults(func=fn)
        return sp

    add_slug_msg("start", cmd_start, with_session=True)
    add_slug_msg("update", cmd_update)
    add_slug_msg("complete", cmd_complete)
    add_slug_msg("fail", cmd_fail)

    sp_list = sub.add_parser("list")
    sp_list.set_defaults(func=cmd_list)

    sp_clear = sub.add_parser("clear")
    sp_clear.add_argument("slug")
    sp_clear.set_defaults(func=cmd_clear)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
