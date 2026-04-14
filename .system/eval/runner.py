#!/usr/bin/env python3
"""Phase 2 eval harness runner.

Two-phase design:
  - answer phase: runs cosmocache agent + flat memory one-shot per probe,
    writes raw answers to results/<run-id>/probes/<tier>-<id>.json (no scores).
    Resumable — re-running skips probes whose JSON already has answers.
  - judge phase: reads those JSONs, runs the judge, fills in scores, writes
    summary.json and report.md. Rerunnable without re-answering.

Default is --phase both (answer then judge, same behavior as before).
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from lib.anthropic_client import AnthropicClient, BaseClient
from lib.scoring import parse_judge_response, aggregate
from lib.report import render_report
from lib.tokens import TokenBudget
from lib.agent import run_agent
from lib.tools_impl import TOOL_DEFS, dispatch as tools_dispatch

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def _load_dotenv() -> None:
    for path in (HERE / ".env", REPO / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)

TIER_INCLUSION = {
    "small":  {"small"},
    "medium": {"small", "medium"},
    "large":  {"small", "medium", "large"},
    "real":   {"small", "medium", "large"},
}


def load_probes(only: list[str] | None) -> list[dict]:
    path = HERE / "scenarios/probes.yaml"
    d = yaml.safe_load(path.read_text())
    probes = d["probes"]
    if only:
        probes = [p for p in probes if p["id"] in set(only)]
    return probes


def plan_probes(probes: list[dict], tier_name: str) -> list[dict]:
    include = TIER_INCLUSION[tier_name]
    return [p for p in probes if p["scale_tier"] in include]


def build_cosmocache_prompt(universe_dir: Path, probe: dict) -> tuple[str, str]:
    gloss = (universe_dir / "enigma/glossary.md").read_text()
    system = (
        "You are Claude. The cosmocache SessionStart hook has injected Enigma's glossary below. "
        "You have two tools:\n"
        "  - list_files(path): list files under a directory inside the universe.\n"
        "  - read_file(path): read a file inside the universe.\n"
        "All paths are RELATIVE to the universe root (do not include the absolute prefix). "
        "Typical layout: `planets/<planet-slug>/planet.md`, `planets/<planet-slug>/creatures/*.md`, "
        "`planets/<planet-slug>/generations/<gen>/*.md`.\n\n"
        "Workflow: 1) read the glossary below, 2) if a planet matches the question, read its "
        "planet.md and relevant creature/generation files, 3) answer citing those files. "
        "If no planet matches, say you don't know — do not confabulate.\n\n"
        f"=== Enigma's glossary ===\n{gloss}"
    )
    user = probe["question"]
    return system, user


def build_flatmemory_prompt(flat_md: str, probe: dict) -> tuple[str, str]:
    system = (
        "You are Claude. The following memory.md has been loaded at session start. "
        "Answer from it. If nothing matches, say you don't know.\n\n" + flat_md
    )
    user = probe["question"]
    return system, user


def _probe_answered(probe_data: dict) -> bool:
    cc = probe_data.get("cosmocache", {})
    fl = probe_data.get("flatmemory", {})
    return "answer" in cc and "answer" in fl


def _probe_judged(probe_data: dict) -> bool:
    cc = probe_data.get("cosmocache", {})
    fl = probe_data.get("flatmemory", {})
    return "score" in cc and "score" in fl


def run_answers(config: dict, dry_run: bool, only_probes: list[str], run_id: str | None) -> tuple[int, str | None]:
    """Run cosmocache + flat answers for all probes. Returns (exit_code, run_id)."""
    probes = load_probes(only_probes)
    tiers = config["scale_tiers"]

    total_planned = 0
    planned_by_tier: list[tuple[str, int]] = []
    for t in tiers:
        p = plan_probes(probes, t["name"])
        planned_by_tier.append((t["name"], len(p)))
        total_planned += len(p) * 2

    print(f"{total_planned} probes planned (across {len(tiers)} tiers)")
    for name, n in planned_by_tier:
        print(f"  {name}: {n} probes x 2 systems = {n*2} calls")

    if dry_run:
        return 0, None

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set; live run aborted.", file=sys.stderr)
        return 2, None

    client: BaseClient = AnthropicClient()
    budget = TokenBudget(limit=config["budget"]["max_total_tokens_per_run"])

    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out_dir = HERE / "results" / run_id
    (out_dir / "probes").mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        started_at = existing.get("started_at") or datetime.now(timezone.utc).isoformat()
        prior_spent = existing.get("answer_tokens_charged", 0)
        budget.charge(prior_spent)
        print(f"Resuming run {run_id} (prior answer tokens charged: {prior_spent:,})")
    else:
        started_at = datetime.now(timezone.utc).isoformat()

    from scenarios.synth_corpus import build_synthetic_universe
    from baselines.flatten_to_memory_md import flatten

    tier_manifest: list[dict] = []
    for t in tiers:
        tier_name = t["name"]
        tier_probes = plan_probes(probes, tier_name)
        if not tier_probes:
            continue

        if t["n_planets"] is None:
            universe = HERE / "scenarios/seed_universe"
        else:
            import tempfile
            tmp = Path(tempfile.mkdtemp(prefix=f"cosmocache-synth-{tier_name}-"))
            universe = build_synthetic_universe(HERE / "scenarios/seed_universe", t["n_planets"], tmp)

        flat_md = flatten(universe, now="2026-04-13T00:00:00Z")

        print(f"\n=== answer: tier {tier_name}: {len(tier_probes)} probes ===", flush=True)
        probe_ids: list[str] = []
        for idx, probe in enumerate(tier_probes, 1):
            probe_ids.append(probe["id"])
            probe_path = out_dir / "probes" / f"{tier_name}-{probe['id']}.json"

            if probe_path.exists():
                existing = json.loads(probe_path.read_text())
                if _probe_answered(existing):
                    print(f"[{idx}/{len(tier_probes)}] {probe['id']} (skipped — already answered)", flush=True)
                    continue

            if budget.exceeded():
                print(f"BUDGET EXCEEDED at tier={tier_name}, probe={probe['id']}; stopping answer phase.", flush=True)
                break

            print(f"[{idx}/{len(tier_probes)}] {probe['id']}", flush=True)

            sys_a, usr_a = build_cosmocache_prompt(universe, probe)
            a = run_agent(
                client,
                system=sys_a,
                user=usr_a,
                tools=TOOL_DEFS,
                tool_handler=lambda name, inp, _u=universe: tools_dispatch(_u, name, inp),
                model=config["system_under_test"]["model"],
                temperature=config["system_under_test"]["temperature"],
                max_tokens=config["system_under_test"]["max_tokens"],
                max_iterations=12,
            )
            print(f"  [cc  {probe['id']}] iters={a.iterations} tool_calls={a.tool_calls} in={a.input_tokens} out={a.output_tokens}", flush=True)
            budget.charge(a.input_tokens + a.output_tokens)

            sys_b, usr_b = build_flatmemory_prompt(flat_md, probe)
            b = client.complete(system=sys_b, user=usr_b,
                                model=config["system_under_test"]["model"],
                                temperature=config["system_under_test"]["temperature"],
                                max_tokens=config["system_under_test"]["max_tokens"])
            print(f"  [flat {probe['id']}] in={b.input_tokens} out={b.output_tokens}", flush=True)
            budget.charge(b.input_tokens + b.output_tokens)

            data = {
                "probe_id": probe["id"],
                "tier": tier_name,
                "question": probe["question"],
                "expected_fact": probe["expected_fact"],
                "cosmocache": {
                    "answer": a.text,
                    "input_tokens": a.input_tokens,
                    "output_tokens": a.output_tokens,
                    "iterations": a.iterations,
                    "tool_calls": a.tool_calls,
                },
                "flatmemory": {
                    "answer": b.text,
                    "input_tokens": b.input_tokens,
                    "output_tokens": b.output_tokens,
                },
            }
            probe_path.write_text(json.dumps(data, indent=2))

        tier_manifest.append({"name": tier_name, "n_planets": t["n_planets"], "probe_ids": probe_ids})

    completed_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "run_id": run_id,
        "started_at": started_at,
        "answer_completed_at": completed_at,
        "config": config,
        "tiers": tier_manifest,
        "answer_tokens_charged": budget.spent,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nAnswer phase complete. Run ID: {run_id}")
    print(f"  probes dir: {out_dir / 'probes'}")
    print(f"  answer tokens charged: {budget.spent:,}")
    print(f"\nNext: python3 runner.py --config {Path('configs/smoke.yaml')} --phase judge --run-id {run_id}")
    return 0, run_id


def run_judge_phase(run_id: str) -> int:
    """Run judge on the probe JSONs of an existing run. Writes summary.json + report.md."""
    out_dir = HERE / "results" / run_id
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: no manifest at {manifest_path}. Did the answer phase run?", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text())

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set; judge phase aborted.", file=sys.stderr)
        return 2

    client: BaseClient = AnthropicClient()
    judge_cfg = manifest["config"]["judge"]
    judge_prompt_tmpl = (HERE / "prompts/judge.txt").read_text()

    judge_tokens = 0
    tier_summaries: list[dict] = []

    for tm in manifest["tiers"]:
        tier_name = tm["name"]
        probe_ids = tm["probe_ids"]
        print(f"\n=== judge: tier {tier_name}: {len(probe_ids)} probes ===", flush=True)
        per_probe: list[dict] = []
        cc_scores: list[float] = []; cc_tokens: list[int] = []
        flat_scores: list[float] = []; flat_tokens: list[int] = []

        for idx, pid in enumerate(probe_ids, 1):
            probe_path = out_dir / "probes" / f"{tier_name}-{pid}.json"
            if not probe_path.exists():
                print(f"[{idx}/{len(probe_ids)}] {pid} SKIPPED — no answer file", flush=True)
                continue
            data = json.loads(probe_path.read_text())

            if _probe_judged(data):
                print(f"[{idx}/{len(probe_ids)}] {pid} (already judged)", flush=True)
            else:
                print(f"[{idx}/{len(probe_ids)}] {pid}", flush=True)
                ja = client.complete(system="", user=judge_prompt_tmpl.format(
                    question=data["question"], expected_fact=data["expected_fact"],
                    answer=data["cosmocache"]["answer"]),
                    model=judge_cfg["model"], temperature=judge_cfg["temperature"],
                    max_tokens=judge_cfg["max_tokens"])
                jb = client.complete(system="", user=judge_prompt_tmpl.format(
                    question=data["question"], expected_fact=data["expected_fact"],
                    answer=data["flatmemory"]["answer"]),
                    model=judge_cfg["model"], temperature=judge_cfg["temperature"],
                    max_tokens=judge_cfg["max_tokens"])
                judge_tokens += ja.input_tokens + ja.output_tokens + jb.input_tokens + jb.output_tokens
                ja_r = parse_judge_response(ja.text)
                jb_r = parse_judge_response(jb.text)
                data["cosmocache"]["score"] = ja_r.score
                data["cosmocache"]["reason"] = ja_r.reason
                data["flatmemory"]["score"] = jb_r.score
                data["flatmemory"]["reason"] = jb_r.reason
                probe_path.write_text(json.dumps(data, indent=2))
                print(f"  cc={ja_r.score:.2f}  flat={jb_r.score:.2f}", flush=True)

            per_probe.append({
                "probe_id": data["probe_id"],
                "cosmocache": {"score": data["cosmocache"]["score"], "tokens": data["cosmocache"]["input_tokens"]},
                "flatmemory": {"score": data["flatmemory"]["score"], "tokens": data["flatmemory"]["input_tokens"]},
            })
            cc_scores.append(data["cosmocache"]["score"]); cc_tokens.append(data["cosmocache"]["input_tokens"])
            flat_scores.append(data["flatmemory"]["score"]); flat_tokens.append(data["flatmemory"]["input_tokens"])

        cc = aggregate(cc_scores, cc_tokens)
        fl = aggregate(flat_scores, flat_tokens)
        tier_summaries.append({
            "name": tier_name,
            "n_planets": tm["n_planets"],
            "cosmocache": {"accuracy_mean": cc.accuracy_mean,
                           "input_tokens_mean": cc.input_tokens_mean,
                           "input_tokens_p95": cc.input_tokens_p95},
            "flatmemory": {"accuracy_mean": fl.accuracy_mean,
                           "input_tokens_mean": fl.input_tokens_mean,
                           "input_tokens_p95": fl.input_tokens_p95},
            "per_probe": per_probe,
        })

    total_input = manifest.get("answer_tokens_charged", 0) + judge_tokens
    summary = {
        "run_id": run_id,
        "started_at": manifest["started_at"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "config": manifest["config"],
        "tiers": tier_summaries,
        "cost": {
            "total_input_tokens": total_input,
            "total_output_tokens": 0,
            "usd_estimate": round(total_input / 1_000_000 * 15.0, 2),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "report.md").write_text(render_report(summary))
    print(f"\nJudge phase complete. Report: {out_dir / 'report.md'}")
    return 0


def main() -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-probes", type=str, default="")
    ap.add_argument("--phase", choices=["answer", "judge", "both"], default="both",
                    help="answer: run SUT only (expensive). judge: score an existing run. both: default, runs answer then judge.")
    ap.add_argument("--run-id", type=str, default=None,
                    help="Resume a prior answer run or specify which run to judge. Required for --phase judge.")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    dry_run = args.dry_run or cfg.get("dry_run", False)
    only = [s.strip() for s in args.only_probes.split(",") if s.strip()] or cfg.get("only_probes") or []
    run_id = args.run_id or cfg.get("run_id")

    if args.phase == "judge":
        if not run_id:
            print("ERROR: --phase judge requires --run-id <id>", file=sys.stderr)
            return 2
        return run_judge_phase(run_id)

    rc, run_id = run_answers(cfg, dry_run=dry_run, only_probes=only, run_id=run_id)
    if rc != 0 or dry_run or args.phase == "answer":
        return rc
    return run_judge_phase(run_id)


if __name__ == "__main__":
    raise SystemExit(main())
