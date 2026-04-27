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


def _read_frontmatter_line(text: str, key: str) -> str | None:
    """Return the raw value of `<key>:` within the first --- block, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            break
        if lines[i].startswith(f"{key}:"):
            return lines[i].split(":", 1)[1].strip()
    return None


def _parse_list_literal(raw: str) -> list[str]:
    """Parse `[a, b, c]` or `a, b, c` into a clean list of tokens."""
    raw = raw.strip().strip("[").rstrip("]")
    if not raw:
        return []
    return [tok.strip().strip('"').strip("'")
            for tok in raw.split(",")
            if tok.strip()]


def read_planet_keywords(planet_dir: Path) -> list[str]:
    pmd = planet_dir / "planet.md"
    if not pmd.exists():
        return []
    raw = _read_frontmatter_line(pmd.read_text(), "keywords")
    return _parse_list_literal(raw) if raw else []


def extract_new_keywords(out_file: Path) -> list[str]:
    if not out_file.exists():
        return []
    raw = _read_frontmatter_line(out_file.read_text(), "new_keywords")
    if not raw:
        return []
    kws = _parse_list_literal(raw)
    # cap to 3 and drop anything that's not a short slug-ish token
    clean = [k.lower() for k in kws
             if k and len(k) <= 40 and " " not in k.strip()]
    return clean[:3]


def merge_keywords_into_planet(planet_dir: Path, new_kws: list[str]) -> list[str]:
    """Append genuinely-new kws to planet.md's keywords line. Returns added."""
    if not new_kws:
        return []
    pmd = planet_dir / "planet.md"
    if not pmd.exists():
        return []
    current = [k.lower() for k in read_planet_keywords(planet_dir)]
    additions = [k for k in new_kws if k not in current]
    if not additions:
        return []
    merged = current + additions
    text = pmd.read_text()
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("keywords:"):
            lines[i] = f"keywords: [{', '.join(merged)}]\n"
            pmd.write_text("".join(lines))
            return additions
    return []


def autoresearch(slug: str, planet_dir: Path, hint: str,
                 current_keywords: list[str]) -> tuple[bool, str]:
    date = time.strftime("%Y-%m-%d", time.gmtime())
    out_file = planet_dir / "generations" / f"autoresearch-{date}.md"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    kw_csv = ", ".join(current_keywords) if current_keywords else "(none)"
    prompt = (
        f"You are the autoresearch subagent for planet-{slug}.\n\n"
        f"Research hint from the judge: {hint}\n\n"
        f"Current glossary keywords for this planet: {kw_csv}\n\n"
        f"Step 1: Inspect the planet directory at {planet_dir}. Read code, skills, docs.\n"
        f"Step 2: Use WebFetch/WebSearch if current information is helpful.\n"
        f"Step 3: Write your findings to: {out_file}\n\n"
        "The file MUST start with a YAML frontmatter block:\n"
        "---\n"
        "new_keywords: [kw1, kw2, kw3]   # 0-3 terms NOT in current keywords; [] if nothing new\n"
        "---\n\n"
        "Rules for new_keywords:\n"
        "- Only propose terms that meaningfully index new material (libraries, concepts, patterns).\n"
        "- Single tokens or short hyphenated slugs (e.g. 'useMemo', 'canary-rollout'). No spaces.\n"
        "- Empty list is correct if nothing new worth indexing surfaced.\n\n"
        "After the frontmatter, write these sections:\n"
        "- Summary\n"
        "- Key Learnings\n"
        "- Open Questions for Human\n\n"
        "Rules:\n"
        "- DO NOT modify planet.md or anything in creatures/.\n"
        "- Write ONLY the output file above.\n"
        "- Keep report under 500 words (frontmatter excluded).\n"
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


def _run_mutation_tick(slug: str, planet_dir: Path) -> None:
    """Phase 3: propose a distilled creature, score, promote or reject.

    Wrapped in this helper so it stays a single non-fatal call site in main().
    """
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(UNIVERSE / ".system" / "eval"))
    import mutation_tick
    from lib.anthropic_client import AnthropicClient

    # Probe subset: pick up to 3 probes from probes.yaml whose ids contain any
    # of this planet's keywords. Falls back to first 3 probes if none match.
    import yaml
    probes_yaml = UNIVERSE / ".system" / "eval" / "scenarios" / "probes.yaml"
    if not probes_yaml.exists():
        log(slug, "mutation tick skipped: no probes.yaml")
        return
    probes = yaml.safe_load(probes_yaml.read_text()).get("probes", [])
    kws = read_planet_keywords(planet_dir)
    matching = [p["id"] for p in probes
                if any(kw in p["id"] for kw in kws)] or [p["id"] for p in probes[:3]]
    probe_subset = matching[:3]

    client = AnthropicClient()
    res = mutation_tick.run(
        planet_slug=slug,
        planet_dir=planet_dir,
        universe_dir=UNIVERSE,
        probe_subset=probe_subset,
        client=client,
        proposer_model="claude-haiku-4-5-20251001",
        sut_model="claude-opus-4-6",
        judge_model="claude-opus-4-6",
    )
    log(slug, f"mutation: outcome={res.outcome} creature={res.creature} "
              f"reason={res.reason}")

    # Record the outcome in evolutions.db so `cosmo evolve mutations` can show it.
    if res.outcome in ("promoted", "rejected"):
        status = "mutation_promoted" if res.outcome == "promoted" else "mutation_rejected"
        msg = f"{res.creature}: {res.reason}"[:200]
        import sqlite3
        db = UNIVERSE / "enigma" / "evolutions.db"
        # Always write a fresh row keyed by slug (the schema is single-state-per-slug).
        # We create the table via mutation_tick imports if needed; here we just upsert.
        with sqlite3.connect(str(db)) as conn:
            now = conn.execute(
                "SELECT strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
            ).fetchone()[0]
            conn.execute(
                """
                INSERT OR REPLACE INTO evolutions
                  (planet_slug, status, message, started_at, updated_at,
                   completed_at, session_id)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (slug, status, msg, now, now, now),
            )
            conn.commit()


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
    current_kws = read_planet_keywords(planet_dir)
    evolve("start", slug, msg=reason)
    ok, tail = autoresearch(slug, planet_dir, hint, current_kws)
    log(slug, f"autoresearch exit_ok={ok}; tail={tail}")
    if ok:
        date = time.strftime("%Y-%m-%d", time.gmtime())
        out_file = planet_dir / "generations" / f"autoresearch-{date}.md"
        new_kws = extract_new_keywords(out_file)
        added = merge_keywords_into_planet(planet_dir, new_kws)
        if added:
            log(slug, f"keywords merged into planet.md: {added}")

        # Phase 3: fitness-gated distillation. Only runs if a creature
        # qualifies; failures are logged but don't fail the tick.
        try:
            _run_mutation_tick(slug, planet_dir)
        except Exception as e:
            log(slug, f"mutation tick error (non-fatal): {e!r}")

    evolve("complete" if ok else "fail",
           slug,
           msg=("autoresearch ok" if ok else f"autoresearch failed: {tail[:80]}"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
