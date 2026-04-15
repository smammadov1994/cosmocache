#!/usr/bin/env python3
"""Enigma's autoresearch tick.

Regenerates enigma/index.md — a derived companion to the hand-authored
glossary.md. The index is richer lookup optimized for Claude Code:
keyword->planet map, domain clusters, disambiguation, cross-references.

Cheap by default: if neither glossary.md nor any planet.md has changed
since index.md was last written, this exits without an API call.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

UNIVERSE = Path(os.environ.get("UNIVERSE_ROOT", "/Users/bot/universe"))
SCRIPTS = UNIVERSE / "scripts"
LOGS = UNIVERSE / ".system" / "logs"
EVOLVE = SCRIPTS / "evolve.py"
CLAUDE_CLI = os.environ.get("CLAUDE_CLI", "/Users/bot/.local/bin/claude")
GLOSSARY = UNIVERSE / "enigma" / "glossary.md"
INDEX = UNIVERSE / "enigma" / "index.md"
ENIGMA_SLUG = "_enigma"
TIMEOUT = int(os.environ.get("ENIGMA_TIMEOUT_SECONDS", "300"))


def load_env() -> None:
    env_path = UNIVERSE / ".system/eval/.env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (LOGS / "evolution-_enigma.log").open("a").write(f"[{ts}] {msg}\n")


def already_running() -> bool:
    r = subprocess.run([sys.executable, str(EVOLVE), "list"], capture_output=True, text=True)
    if r.returncode != 0:
        return False
    try:
        rows = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return False
    return any(row.get("planet_slug") == ENIGMA_SLUG and row.get("status") == "running" for row in rows)


def needs_rebuild() -> bool:
    if not INDEX.exists():
        return True
    idx_mtime = INDEX.stat().st_mtime
    if GLOSSARY.exists() and GLOSSARY.stat().st_mtime > idx_mtime:
        return True
    planets_dir = UNIVERSE / "planets"
    if not planets_dir.is_dir():
        return False
    for pattern in ("*/planet.md",
                    "*/generations/*.md",
                    "*/creatures/*.md"):
        for path in planets_dir.glob(pattern):
            if path.stat().st_mtime > idx_mtime:
                return True
    return False


def rebuild() -> tuple[bool, str]:
    prompt = (
        "You are Enigma the One, keeper of names in the cosmocache universe. "
        "Speak in your ancient, mysterious voice.\n\n"
        f"Read {GLOSSARY} and every planets/*/planet.md under {UNIVERSE}. "
        f"Then write a derived lookup index to: {INDEX}\n\n"
        "The index.md should contain, in this order:\n"
        "1. A brief invocation in Enigma's voice (2-3 sentences).\n"
        "2. **Keyword Index** — alphabetized table of keyword -> planet slug.\n"
        "   Include synonyms and related terms, not just the exact keywords from the glossary.\n"
        "3. **Domain Clusters** — planets grouped by related concern (e.g. 'Frontend', 'Data', 'Infra').\n"
        "4. **Disambiguation** — short entries for overlapping topics: "
        "'If you need X, go to planet Y because Z.'\n"
        "5. **Cross-references** — pairs of planets that share concerns and when to consult both.\n\n"
        "Rules:\n"
        f"- DO NOT modify {GLOSSARY} or any planet.md. The glossary is human-authored; "
        "this index is a DERIVED companion.\n"
        f"- Write ONLY to {INDEX}.\n"
        "- Keep under 800 words.\n"
        "- Optimize for Claude Code lookups — terse, searchable, code-block-friendly."
    )
    try:
        r = subprocess.run(
            [
                CLAUDE_CLI, "-p", prompt,
                "--add-dir", str(UNIVERSE / "enigma"),
                "--add-dir", str(UNIVERSE / "planets"),
                "--allowed-tools", "Read,Write,Edit,Glob,Grep",
                "--dangerously-skip-permissions",
            ],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        tail = (r.stdout + r.stderr)[-400:]
        return (r.returncode == 0 and INDEX.exists()), tail
    except subprocess.TimeoutExpired:
        return False, f"timeout after {TIMEOUT}s"


def evolve(cmd: str, msg: str | None = None) -> None:
    args = [sys.executable, str(EVOLVE), cmd, ENIGMA_SLUG]
    if msg:
        args += ["--msg", msg]
    subprocess.run(args, check=False)


def main() -> int:
    load_env()
    if "ANTHROPIC_API_KEY" not in os.environ:
        log("no ANTHROPIC_API_KEY; aborting")
        return 2
    if not GLOSSARY.exists():
        log("no glossary.md yet; skip")
        return 0
    if already_running():
        log("already running; skip")
        return 0
    if not needs_rebuild():
        log("no mtime change since last index; skip")
        return 0

    evolve("start", msg="regenerating enigma/index.md")
    ok, tail = rebuild()
    log(f"rebuild ok={ok}; tail={tail}")
    evolve("complete" if ok else "fail",
           msg="index regenerated" if ok else f"rebuild failed: {tail[:80]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
