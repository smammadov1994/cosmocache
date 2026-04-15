#!/usr/bin/env python3
"""Per-planet evolution tick. Invoked by launchd (see install_evolution_cron.sh).

Flow:
  1. Skip if planet is already 'running' in evolutions.db.
  2. Skip if any file in the planet was modified in the last hour
     (don't disturb a user who's actively working here).
  3. Ask Haiku judge: is there code / skills / researchable material?
  4. If skip -> exit silently (no DB row written).
  5. If evolve -> evolve.py start, spawn `claude -p` as autoresearch,
     evolve.py complete or fail based on exit code.
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
HAIKU = "claude-haiku-4-5-20251001"
AUTORESEARCH_TIMEOUT = int(os.environ.get("AUTORESEARCH_TIMEOUT_SECONDS", "600"))
USER_ACTIVITY_WINDOW = int(os.environ.get("USER_ACTIVITY_WINDOW_SECONDS", "3600"))


def load_env() -> None:
    """Pick up ANTHROPIC_API_KEY from the eval .env if not already set."""
    env_path = UNIVERSE / ".system/eval/.env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def log(slug: str, msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (LOGS / f"evolution-{slug}.log").open("a").write(f"[{ts}] {msg}\n")


def already_running(slug: str) -> bool:
    r = subprocess.run([sys.executable, str(EVOLVE), "list"], capture_output=True, text=True)
    if r.returncode != 0:
        return False
    try:
        rows = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return False
    return any(row.get("planet_slug") == slug and row.get("status") == "running" for row in rows)


def recent_activity(planet_dir: Path) -> tuple[Path, float] | None:
    """Return (file, age_seconds) of the most recently modified file inside
    USER_ACTIVITY_WINDOW, or None if nothing was touched in that window.

    Ignores paths the tick itself writes (generations/autoresearch-*.md)
    so successful ticks don't keep blocking themselves.
    """
    now = time.time()
    cutoff = now - USER_ACTIVITY_WINDOW
    newest: tuple[Path, float] | None = None
    for p in planet_dir.rglob("*"):
        if not p.is_file():
            continue
        # Skip files that autoresearch itself writes.
        if p.parent.name == "generations" and p.name.startswith("autoresearch-"):
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if mtime <= cutoff:
            continue
        if newest is None or mtime > newest[1]:
            newest = (p, mtime)
    if newest is None:
        return None
    return (newest[0], now - newest[1])


def file_manifest(planet_dir: Path, limit: int = 200) -> list[str]:
    items: list[str] = []
    for p in sorted(planet_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(planet_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        items.append(str(rel))
        if len(items) >= limit:
            break
    return items


def judge_decision(slug: str, planet_dir: Path) -> dict:
    import anthropic
    manifest = file_manifest(planet_dir)
    prompt = (
        f"You are the evolution judge for planet '{slug}' in the cosmocache universe.\n"
        "Decide if an autoresearch agent should investigate this planet right now.\n\n"
        "EVOLVE if any of:\n"
        "- Code files present (.py, .ts, .tsx, .js, .jsx, .go, .rs, .sh, .rb, .java, .c, .cpp)\n"
        "- `skills/` directory with skill markdown\n"
        "- `src/`, `lib/`, `code/`, or `tools/` directories\n"
        "- Docs or notes beyond planet.md that describe something researchable (APIs, libraries, papers, runbooks)\n\n"
        "SKIP if:\n"
        "- Only planet.md + creatures/ + generations/ (pure memory, nothing new to research)\n"
        "- Planet is empty or near-empty\n"
        "- Manifest shows only markdown memory files\n\n"
        f"File manifest for planets/{slug}/ (up to 200 files):\n"
        + "\n".join(manifest)
        + "\n\nRespond with ONE line of raw JSON, no code fences. Schema:\n"
        '{"decision": "evolve" | "skip", "reason": "<one sentence>", "hint": "<one sentence of what to research, empty if skip>"}'
    )
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=HAIKU,
        max_tokens=200,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().split("\n", 1)[0] if "\n" not in text else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"decision": "skip", "reason": f"judge-unparseable: {text[:80]}", "hint": ""}


def autoresearch(slug: str, planet_dir: Path, hint: str) -> tuple[bool, str]:
    date = time.strftime("%Y-%m-%d", time.gmtime())
    out_file = planet_dir / "generations" / f"autoresearch-{date}.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    prompt = (
        f"You are the autoresearch subagent for planet-{slug}.\n\n"
        f"Research hint from the judge: {hint}\n\n"
        f"Step 1: Inspect the planet directory at {planet_dir}. Read code, skills, docs.\n"
        f"Step 2: Use WebFetch/WebSearch if current information is helpful.\n"
        f"Step 3: Write your findings to: {out_file}\n\n"
        "Rules:\n"
        "- DO NOT modify planet.md or anything in creatures/.\n"
        "- Write ONLY the output file above.\n"
        "- Keep report under 500 words.\n"
        "- Sections: Summary, Key Learnings, Open Questions for Human.\n"
    )
    try:
        r = subprocess.run(
            [
                CLAUDE_CLI, "-p", prompt,
                "--add-dir", str(planet_dir),
                "--allowed-tools", "Read,Write,Edit,Glob,Grep,WebFetch,WebSearch",
                "--dangerously-skip-permissions",
            ],
            capture_output=True, text=True, timeout=AUTORESEARCH_TIMEOUT,
        )
        tail = (r.stdout + r.stderr)[-400:]
        return (r.returncode == 0 and out_file.exists()), tail
    except subprocess.TimeoutExpired:
        return False, f"timeout after {AUTORESEARCH_TIMEOUT}s"


def evolve(cmd: str, slug: str, msg: str | None = None) -> None:
    args = [sys.executable, str(EVOLVE), cmd, slug]
    if msg:
        args += ["--msg", msg]
    subprocess.run(args, check=False)


def main() -> int:
    args = sys.argv[1:]
    force = False
    if "--force" in args:
        force = True
        args = [a for a in args if a != "--force"]
    if len(args) != 1:
        print("usage: evolution_tick.py [--force] <slug>", file=sys.stderr)
        return 2
    slug = args[0]
    planet_dir = UNIVERSE / "planets" / slug
    if not planet_dir.is_dir():
        print(f"no such planet: {slug}", file=sys.stderr)
        return 2

    load_env()
    if "ANTHROPIC_API_KEY" not in os.environ:
        log(slug, "no ANTHROPIC_API_KEY; aborting")
        return 2
    if already_running(slug):
        log(slug, "already running; skip")
        return 0
    if not force:
        hit = recent_activity(planet_dir)
        if hit is not None:
            rel = hit[0].relative_to(planet_dir)
            log(slug, f"skip: {rel} modified {hit[1]:.0f}s ago "
                      f"(window={USER_ACTIVITY_WINDOW}s)")
            return 0
    elif force:
        log(slug, "force: bypassing recent-activity guard")

    try:
        decision = judge_decision(slug, planet_dir)
    except Exception as e:
        log(slug, f"judge error: {e!r}")
        return 1

    log(slug, f"judge: {json.dumps(decision)}")
    if decision.get("decision") != "evolve":
        return 0

    reason = decision.get("reason", "autoresearch")[:120]
    hint = decision.get("hint", "")
    evolve("start", slug, msg=reason)
    ok, tail = autoresearch(slug, planet_dir, hint)
    log(slug, f"autoresearch exit_ok={ok}; tail={tail}")
    evolve("complete" if ok else "fail",
           slug,
           msg=("autoresearch ok" if ok else f"autoresearch failed: {tail[:80]}"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
