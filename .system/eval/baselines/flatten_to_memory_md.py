"""
flatten_to_memory_md.py — deterministic cosmocache universe flattener.

Walks a universe directory and emits a single memory.md string suitable
for the eval harness fair-flat-baseline comparisons.

CLI:
    python3 flatten_to_memory_md.py --universe PATH [--out PATH]

If --out is omitted, output goes to stdout.

Env var:
    COSMOCACHE_FLATTEN_NOW  ISO timestamp override (used by tests for determinism).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _read(path: Path) -> str:
    """Read a file, returning empty string if it doesn't exist."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _extract_summary_block(text: str) -> str:
    """Extract content from ## Summary until the next ## header (or EOF)."""
    match = re.search(r"^## Summary\b", text, re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    # Find next ## header after the Summary header
    next_h2 = re.search(r"^## ", text[match.end():], re.MULTILINE)
    if next_h2:
        end = match.end() + next_h2.start()
        return text[start:end].rstrip()
    return text[start:].rstrip()


def flatten(universe: Path, now: str | None = None) -> str:
    """
    Walk the universe and return a flattened memory.md string.

    Args:
        universe: Path to the universe root (must contain a planets/ subdir).
        now: ISO timestamp string override. If None, uses current UTC time.

    Returns:
        Full flattened memory.md content as a string.
    """
    if now is None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        ts = now

    parts: list[str] = []
    parts.append(f"# Memory (flattened at {ts})")

    planets_dir = universe / "planets"
    if not planets_dir.exists():
        return "\n".join(parts) + "\n"

    # Sort alphabetically by directory name for determinism
    planet_dirs = sorted(
        [p for p in planets_dir.iterdir() if p.is_dir()],
        key=lambda p: p.name,
    )

    for planet_path in planet_dirs:
        slug = planet_path.name
        parts.append(f"\n\n---\n\n## {slug}")

        # planet.md contents
        planet_md = _read(planet_path / "planet.md")
        if planet_md:
            parts.append(planet_md.rstrip())

        # Creatures — sorted alphabetically by filename
        creatures_dir = planet_path / "creatures"
        if creatures_dir.exists():
            creature_files = sorted(
                [f for f in creatures_dir.iterdir() if f.suffix == ".md" and f.is_file()],
                key=lambda f: f.name,
            )
            for creature_file in creature_files:
                stem = creature_file.stem
                content = _read(creature_file)
                parts.append(f"\n\n### creature: {stem}")
                if content:
                    parts.append(content.rstrip())

        # Generations
        generations_dir = planet_path / "generations"
        if generations_dir.exists():
            gen_files = [
                f for f in generations_dir.iterdir()
                if f.suffix == ".md" and f.is_file()
            ]

            # Separate active candidates (not ending in -archive) from archived
            active_candidates = [f for f in gen_files if not f.stem.endswith("-archive")]
            archived = [f for f in gen_files if f.stem.endswith("-archive")]

            # Active generation = highest-numbered gen-*.md not ending in -archive
            # Sort by extracting the numeric portion of the stem
            def _gen_sort_key(f: Path) -> int:
                m = re.search(r"(\d+)", f.stem)
                return int(m.group(1)) if m else -1

            if active_candidates:
                active = max(active_candidates, key=_gen_sort_key)
                content = _read(active)
                parts.append(f"\n\n### active generation: {active.stem}")
                if content:
                    parts.append(content.rstrip())

            # Archived generations — emit summary block only, sorted alphabetically
            for arch_file in sorted(archived, key=lambda f: f.name):
                content = _read(arch_file)
                summary = _extract_summary_block(content)
                parts.append(f"\n\n### archived: {arch_file.stem} (summary only)")
                if summary:
                    parts.append(summary)

    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flatten a cosmocache universe directory to a single memory.md string."
    )
    parser.add_argument(
        "--universe",
        required=True,
        type=Path,
        help="Path to the universe root directory.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output file path. Defaults to stdout.",
    )
    args = parser.parse_args()

    now = os.environ.get("COSMOCACHE_FLATTEN_NOW") or None
    result = flatten(args.universe, now=now)

    if args.out is None:
        sys.stdout.write(result)
    else:
        args.out.write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
