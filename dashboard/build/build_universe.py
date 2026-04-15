#!/usr/bin/env python3
"""Compile the cosmocache universe (markdown on disk) into a single universe.json
that the static dashboard consumes.

Reads a universe directory that looks like:

    <root>/
      enigma/glossary.md        (optional, for metadata table)
      planets/
        <slug>/
          planet.md                     (YAML frontmatter + body)
          creatures/<slug>.md           (YAML frontmatter + Distilled Wisdom + Journal)
          generations/gen-N.md          (optional)

If <root>/planets/ is empty, falls back to <root>/.system/eval/scenarios/seed_universe/.

We keep this tiny on purpose: no PyYAML, no markdown libs. Frontmatter parsing
is a simple line-based scanner, wisdom extraction is a regex over the body.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- palette (matches site/styles.css accents) -----------------------------
PALETTE = ["#7b5cd6", "#7cae7a", "#ef7a6d", "#e7b850"]  # violet, moss, coral, gold

# Hand-picked planet -> palette color where we have opinions; everything else
# gets assigned round-robin from PALETTE in sorted slug order.
PLANET_COLOR_HINTS = {
    "planet-react": "#7b5cd6",  # violet
    "planet-sql": "#7cae7a",  # moss
    "planet-devops": "#ef7a6d",  # coral
}


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a markdown doc into (frontmatter_dict, body_text).

    Handles only the subset we emit: scalars, and inline lists like `[a, b, c]`.
    Good enough for cosmocache's hand-authored files.
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text
    # find the closing --- on its own line
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta: dict[str, Any] = {}
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if ":" not in raw:
            continue
        k, _, v = raw.partition(":")
        key = k.strip()
        val = v.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
        else:
            # strip quotes
            val = val.strip("\"'")
            # best-effort int
            if val.isdigit():
                meta[key] = int(val)
            else:
                meta[key] = val
    body = "\n".join(lines[end + 1 :])
    return meta, body


HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def extract_section(body: str, name: str) -> str:
    """Return the text under the LAST `## {name}` header (so an updated
    Distilled Wisdom block overrides the placeholder). Stops at next `## `."""
    matches = [
        m
        for m in HEADER_RE.finditer(body)
        if m.group(1).strip().lower() == name.lower()
    ]
    if not matches:
        return ""
    last = matches[-1]
    start = last.end()
    # find next ## header
    next_m = HEADER_RE.search(body, pos=start)
    end = next_m.start() if next_m else len(body)
    return body[start:end].strip()


# --- file tree / content harvesting ----------------------------------------
# Paths we never want to surface in the explorer, even if they exist inside
# a planet dir or the top-level universe.
_SKIP_NAMES = {".git", ".DS_Store", "node_modules", "__pycache__", ".pytest_cache"}
# Dirs the universe-wide explorer hides (infrastructure, not content).
_UNIVERSE_HIDDEN = {".system", "dashboard", "site", ".git"}
# Per-file cap so a stray giant file can't bloat universe.json.
_MAX_FILE_BYTES = 200_000


def _read_text_capped(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > _MAX_FILE_BYTES:
        data = data[:_MAX_FILE_BYTES]
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _harvest_tree(
    root: Path, rel: str, files: dict[str, str], hide: set[str] = frozenset()
) -> dict[str, Any]:
    """Recursively build a {type, name, children|path} tree for `root`, and
    populate `files` with text content of readable files. Returned paths are
    POSIX-style and relative to the original root."""
    node: dict[str, Any] = {"type": "dir", "name": root.name, "path": rel}
    children: list[dict[str, Any]] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        entries = []
    for entry in entries:
        if entry.name in _SKIP_NAMES or entry.name in hide:
            continue
        child_rel = entry.name if rel == "" else f"{rel}/{entry.name}"
        if entry.is_dir():
            children.append(_harvest_tree(entry, child_rel, files))
        elif entry.is_file():
            children.append({"type": "file", "name": entry.name, "path": child_rel})
            # Only ship text-ish files. Markdown, txt, json, yaml, small configs.
            ext = entry.suffix.lower()
            if ext in {
                ".md",
                ".txt",
                ".json",
                ".yaml",
                ".yml",
                ".toml",
                ".cfg",
                ".ini",
            }:
                files[child_rel] = _read_text_capped(entry)
    node["children"] = children
    return node


COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def clean_wisdom(text: str) -> str:
    text = COMMENT_RE.sub("", text)
    # collapse bullet markers, keep lines
    lines = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if raw.startswith(("- ", "* ", "+ ")):
            raw = raw[2:]
        lines.append(raw)
    return " ".join(lines).strip()


def extract_title(body: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def extract_flavor(body: str) -> str:
    """The first italic line `*...*` under the H1, if any."""
    in_after_h1 = False
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            in_after_h1 = True
            continue
        if in_after_h1:
            if not line:
                continue
            if line.startswith("*") and line.endswith("*") and len(line) > 2:
                return line.strip("*").strip()
            break
    return ""


def latest_autoresearch(planet_dir: Path) -> dict[str, Any] | None:
    """Return the most recent autoresearch file's summary as a dict, or None.

    Looks for generations/autoresearch-YYYY-MM-DD.md files, sorts by date,
    extracts the ## Summary section (first 800 chars), and returns metadata
    plus truncated content.
    """
    gdir = planet_dir / "generations"
    if not gdir.is_dir():
        return None
    candidates = sorted(gdir.glob("autoresearch-*.md"), reverse=True)
    if not candidates:
        return None
    latest = candidates[0]
    try:
        body = latest.read_text(encoding="utf-8")
    except OSError:
        return None
    # Parse date from filename: autoresearch-YYYY-MM-DD.md
    date = latest.stem.replace("autoresearch-", "")
    summary = extract_section(body, "Summary")
    # Also grab Open Questions so the panel has the full picture
    questions = extract_section(body, "Open Questions for Human")
    return {
        "filename": latest.name,
        "date": date,
        "summary": summary[:800] + ("…" if len(summary) > 800 else ""),
        "questions": questions[:400] + ("…" if len(questions) > 400 else ""),
    }


def load_planet(planet_dir: Path) -> dict[str, Any]:
    planet_md = planet_dir / "planet.md"
    meta, body = parse_frontmatter(planet_md.read_text(encoding="utf-8"))
    slug = meta.get("name") or planet_dir.name
    title = extract_title(body) or slug
    flavor = extract_flavor(body)

    creatures = []
    cdir = planet_dir / "creatures"
    if cdir.is_dir():
        for cf in sorted(cdir.glob("*.md")):
            cmeta, cbody = parse_frontmatter(cf.read_text(encoding="utf-8"))
            wisdom_raw = extract_section(cbody, "Distilled Wisdom")
            wisdom = clean_wisdom(wisdom_raw)
            journal_raw = extract_section(cbody, "Journal")
            journal = COMMENT_RE.sub("", journal_raw).strip()
            # Count journal entries (`### ` subheaders)
            session_entries = len(re.findall(r"^###\s+", journal, re.MULTILINE))
            creatures.append(
                {
                    "slug": cmeta.get("name") or cf.stem,
                    "title": extract_title(cbody) or (cmeta.get("name") or cf.stem),
                    "flavor": extract_flavor(cbody),
                    "expertise": cmeta.get("expertise", ""),
                    "born": cmeta.get("born", ""),
                    "born_in_generation": cmeta.get("born_in_generation", ""),
                    "last_seen": cmeta.get("last_seen", ""),
                    "sessions": cmeta.get("sessions", session_entries),
                    "wisdom": wisdom,
                    "wisdom_preview": (wisdom[:150] + "...")
                    if len(wisdom) > 150
                    else wisdom,
                    "journal_entries": session_entries,
                }
            )

    generations = []
    gdir = planet_dir / "generations"
    if gdir.is_dir():
        for gf in sorted(gdir.glob("*.md")):
            generations.append(
                {"name": gf.stem, "path": str(gf.relative_to(planet_dir))}
            )
    latest_run = latest_autoresearch(planet_dir)

    # File tree + markdown contents for the in-panel explorer.
    files: dict[str, str] = {}
    tree = _harvest_tree(planet_dir, "", files)
    tree["name"] = slug  # use slug rather than folder name for display
    # Evolution status no longer lives on the planet — it's read from the
    # SQLite evolutions table and emitted to the separate evolutions.json.

    return {
        "slug": slug,
        "title": title,
        "flavor": flavor,
        "domain": meta.get("domain", ""),
        "keywords": meta.get("keywords", []),
        "generation": meta.get("generation", ""),
        "born": meta.get("born", ""),
        "creatures": creatures,
        "generations": generations,
        "latest_run": latest_run,
        "tree": tree,
        "files": files,
    }


def pick_color(slug: str, idx: int) -> str:
    if slug in PLANET_COLOR_HINTS:
        return PLANET_COLOR_HINTS[slug]
    return PALETTE[idx % len(PALETTE)]


def layout_planets(planets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign polar coordinates (angle in radians, orbit radius) + color + size.

    Single-ring orbit for <=8 planets; otherwise distribute across 2 rings.
    Sizes scale with creature count, clamped to a comfy range.
    """
    n = len(planets)
    base_radius = 260  # px
    ring_gap = 110

    max_creatures = max((len(p["creatures"]) for p in planets), default=1) or 1

    out = []
    # sort by slug for determinism
    planets_sorted = sorted(planets, key=lambda p: p["slug"])
    for i, p in enumerate(planets_sorted):
        if n <= 8:
            ring = 0
            count_in_ring = n
            pos_in_ring = i
        else:
            ring = 0 if i < n // 2 else 1
            count_in_ring = (n // 2) if ring == 0 else (n - n // 2)
            pos_in_ring = i if ring == 0 else (i - n // 2)
        angle = (pos_in_ring / max(count_in_ring, 1)) * (2 * 3.14159265) + (
            0.35 if ring else 0
        )
        radius = base_radius + ring * ring_gap
        c_count = max(len(p["creatures"]), 1)
        size = 26 + 18 * (c_count / max_creatures)  # 26..44 px
        out.append(
            {
                **p,
                "layout": {
                    "angle": angle,
                    "radius": radius,
                    "ring": ring,
                    "size": round(size, 2),
                    "color": pick_color(p["slug"], i),
                },
            }
        )
    return out


def find_planets_root(root: Path) -> Path:
    live = root / "planets"
    if live.is_dir() and any(child.is_dir() for child in live.iterdir()):
        return live
    seed = root / ".system" / "eval" / "scenarios" / "seed_universe" / "planets"
    if seed.is_dir():
        return seed
    return live  # may be empty; caller will handle


def find_glossary(root: Path) -> Path | None:
    live = root / "enigma" / "glossary.md"
    if live.is_file() and live.stat().st_size > 0:
        # Prefer seed if live is the empty stub with only placeholder comment
        txt = live.read_text(encoding="utf-8")
        if "<!-- planets will be appended" in txt and "| planet-" not in txt:
            seed = (
                root
                / ".system"
                / "eval"
                / "scenarios"
                / "seed_universe"
                / "enigma"
                / "glossary.md"
            )
            if seed.is_file():
                return seed
        return live
    seed = (
        root
        / ".system"
        / "eval"
        / "scenarios"
        / "seed_universe"
        / "enigma"
        / "glossary.md"
    )
    if seed.is_file():
        return seed
    return None


def build(root: Path) -> dict[str, Any]:
    pdir = find_planets_root(root)
    planet_entries = []
    if pdir.is_dir():
        for child in sorted(pdir.iterdir()):
            if child.is_dir() and (child / "planet.md").is_file():
                try:
                    planet_entries.append(load_planet(child))
                except Exception as e:
                    sys.stderr.write(f"warn: failed to load {child}: {e}\n")
    planet_entries = layout_planets(planet_entries)

    glossary_md = ""
    gpath = find_glossary(root)
    if gpath:
        glossary_md = gpath.read_text(encoding="utf-8")

    # Universe-wide tree — shown in the explorer when no planet is selected.
    # Hides infrastructure dirs (.system, dashboard, site) to keep the view
    # focused on knowledge content.
    universe_files: dict[str, str] = {}
    universe_tree = _harvest_tree(root, "", universe_files, hide=_UNIVERSE_HIDDEN)
    universe_tree["name"] = "universe"

    return {
        "universe_root": str(root),
        "planets_root": str(pdir),
        "enigma": {
            "name": "Enigma the One",
            "flavor": "I am the keeper of names. Ask, and I will point the way.",
            "glossary_md": glossary_md,
        },
        "planets": planet_entries,
        "universe_tree": universe_tree,
        "universe_files": universe_files,
    }


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_evolutions(root: Path) -> dict[str, dict[str, Any]]:
    """Read the evolutions table read-only. Returns {slug: row_dict}.

    Returns {} if the DB file is missing, the table doesn't exist, or any
    sqlite error fires — evolution status is opportunistic, never fatal.
    """
    db_path = root / "enigma" / "evolutions.db"
    if not db_path.is_file():
        return {}
    try:
        # read-only URI guards against the build process accidentally writing.
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT planet_slug, status, message, started_at, updated_at, "
            "completed_at, session_id FROM evolutions"
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        slug = r["planet_slug"]
        out[slug] = {
            "status": r["status"],
            "message": r["message"],
            "started_at": r["started_at"],
            "updated_at": r["updated_at"],
            "completed_at": r["completed_at"],
            "session_id": r["session_id"],
        }
    return out


def build_evolutions(root: Path) -> dict[str, Any]:
    return {
        "evolutions": read_evolutions(root),
        "generated_at": _iso_now_utc(),
    }


def main() -> int:
    root = Path(os.environ.get("UNIVERSE_ROOT", "/data")).resolve()
    out_path = Path(os.environ.get("OUT_PATH", "web/universe.json")).resolve()
    if len(sys.argv) > 1:
        root = Path(sys.argv[1]).resolve()
    if len(sys.argv) > 2:
        out_path = Path(sys.argv[2]).resolve()

    if not root.is_dir():
        sys.stderr.write(f"error: universe root {root} is not a directory\n")
        return 2

    data = build(root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {out_path} with {len(data['planets'])} planets")

    # Sibling file for the cheap-to-poll evolution status.
    evo_path = out_path.parent / "evolutions.json"
    evo_data = build_evolutions(root)
    evo_path.write_text(
        json.dumps(evo_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {evo_path} with {len(evo_data['evolutions'])} evolutions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
