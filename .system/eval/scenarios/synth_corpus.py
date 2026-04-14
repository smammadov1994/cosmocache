"""Build simulated N-planet universes by replicating a seed universe.

Real planets always preserved; synthetic copies added until target_n_planets is
reached. Glossary regenerated from the result.
"""
from __future__ import annotations
import shutil
from pathlib import Path


def build_synthetic_universe(seed: Path, target_n_planets: int, out_dir: Path) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(seed, out_dir)

    real_planets = sorted((out_dir / "planets").glob("planet-*"), key=lambda p: p.name)
    n_real = len(real_planets)
    if target_n_planets <= n_real:
        return out_dir

    needed = target_n_planets - n_real
    for i in range(needed):
        base = real_planets[i % n_real]
        new_slug = f"{base.name}-synth-{i+1:03d}"
        new_dir = out_dir / "planets" / new_slug
        shutil.copytree(base, new_dir)
        planet_md = new_dir / "planet.md"
        if planet_md.exists():
            text = planet_md.read_text()
            text = text.replace(base.name, new_slug)
            planet_md.write_text(text)

    gloss = out_dir / "enigma/glossary.md"
    header_lines: list[str] = []
    existing_rows: list[str] = []
    saw_separator = False
    for l in gloss.read_text().splitlines():
        if not saw_separator:
            header_lines.append(l)
            if l.startswith("|---"):
                saw_separator = True
        elif l.startswith("| planet-"):
            existing_rows.append(l)

    if not saw_separator:
        header_lines = [
            "# Enigma's Glossary",
            "",
            "| Planet | Domain | Keywords | Last Visited | Gen | Creatures | Why Last Modified |",
            "|---|---|---|---|---|---|---|",
        ]

    # Number of data columns in the table — used to shape synth rows so they
    # match the real glossary's column count (real seed has 8; older stub has 7).
    n_cols = max((l.count("|") for l in header_lines if l.startswith("|---")), default=8) - 1

    real_slugs = {l.split("|")[1].strip() for l in existing_rows if "|" in l}

    synth_rows: list[str] = []
    for p in sorted((out_dir / "planets").glob("planet-*"), key=lambda x: x.name):
        slug = p.name
        if slug in real_slugs:
            continue
        if n_cols == 8:
            synth_rows.append(
                f"| {slug} | Synth-{slug} | synthetic domain | {slug},synth | "
                f"2026-04-13 | gen-0 | 1 | synthetic corpus |"
            )
        else:
            synth_rows.append(
                f"| {slug} | synthetic domain | {slug},synth | "
                f"2026-04-13 | gen-0 | 1 | synthetic corpus |"
            )

    gloss.write_text("\n".join(header_lines + existing_rows + synth_rows) + "\n")
    return out_dir
