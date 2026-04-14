#!/usr/bin/env python3
"""Phase 2 eval harness runner."""
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

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
        f"You are Claude. The cosmocache SessionStart hook has injected the following:\n\n{gloss}\n\n"
        "When answering a question about past work, if the glossary points to a planet, read "
        "that planet's planet.md, its creature files, and its active generation. Cite facts from "
        "those files. If nothing matches, say you don't know."
    )
    user = (
        f"{probe['question']}\n\n"
        f"(You may list the files you would read from the cosmocache at {universe_dir}. "
        "Answer from those files. If you cannot find the answer, say so explicitly.)"
    )
    return system, user


def build_flatmemory_prompt(flat_md: str, probe: dict) -> tuple[str, str]:
    system = (
        "You are Claude. The following memory.md has been loaded at session start. "
        "Answer from it. If nothing matches, say you don't know.\n\n" + flat_md
    )
    user = probe["question"]
    return system, user


def run(config: dict, dry_run: bool, only_probes: list[str]) -> int:
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
        return 0

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set; live run aborted.", file=sys.stderr)
        return 2

    client: BaseClient = AnthropicClient()
    budget = TokenBudget(limit=config["budget"]["max_total_tokens_per_run"])

    run_id = config.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    out_dir = HERE / "results" / run_id
    (out_dir / "probes").mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()

    from scenarios.synth_corpus import build_synthetic_universe
    from baselines.flatten_to_memory_md import flatten

    tier_summaries = []
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

        per_probe_results = []
        cc_scores, cc_tokens, flat_scores, flat_tokens = [], [], [], []
        for probe in tier_probes:
            if budget.exceeded():
                print(f"BUDGET EXCEEDED at tier={tier_name}, probe={probe['id']}; writing partial results.")
                break

            sys_a, usr_a = build_cosmocache_prompt(universe, probe)
            a = client.complete(system=sys_a, user=usr_a,
                                model=config["system_under_test"]["model"],
                                temperature=config["system_under_test"]["temperature"],
                                max_tokens=config["system_under_test"]["max_tokens"])
            budget.charge(a.input_tokens + a.output_tokens)

            sys_b, usr_b = build_flatmemory_prompt(flat_md, probe)
            b = client.complete(system=sys_b, user=usr_b,
                                model=config["system_under_test"]["model"],
                                temperature=config["system_under_test"]["temperature"],
                                max_tokens=config["system_under_test"]["max_tokens"])
            budget.charge(b.input_tokens + b.output_tokens)

            judge_prompt_tmpl = (HERE / "prompts/judge.txt").read_text()
            ja = client.complete(system="", user=judge_prompt_tmpl.format(
                question=probe["question"], expected_fact=probe["expected_fact"], answer=a.text),
                model=config["judge"]["model"], temperature=config["judge"]["temperature"],
                max_tokens=config["judge"]["max_tokens"])
            jb = client.complete(system="", user=judge_prompt_tmpl.format(
                question=probe["question"], expected_fact=probe["expected_fact"], answer=b.text),
                model=config["judge"]["model"], temperature=config["judge"]["temperature"],
                max_tokens=config["judge"]["max_tokens"])
            budget.charge(ja.input_tokens + ja.output_tokens + jb.input_tokens + jb.output_tokens)

            ja_r = parse_judge_response(ja.text)
            jb_r = parse_judge_response(jb.text)

            result = {
                "probe_id": probe["id"],
                "cosmocache": {"answer": a.text, "tokens": a.input_tokens, "score": ja_r.score, "reason": ja_r.reason},
                "flatmemory": {"answer": b.text, "tokens": b.input_tokens, "score": jb_r.score, "reason": jb_r.reason},
            }
            per_probe_results.append(result)
            (out_dir / "probes" / f"{tier_name}-{probe['id']}.json").write_text(json.dumps(result, indent=2))

            cc_scores.append(ja_r.score); cc_tokens.append(a.input_tokens)
            flat_scores.append(jb_r.score); flat_tokens.append(b.input_tokens)

        cc = aggregate(cc_scores, cc_tokens)
        fl = aggregate(flat_scores, flat_tokens)
        tier_summaries.append({
            "name": tier_name,
            "n_planets": t["n_planets"],
            "cosmocache": {"accuracy_mean": cc.accuracy_mean,
                           "input_tokens_mean": cc.input_tokens_mean,
                           "input_tokens_p95": cc.input_tokens_p95},
            "flatmemory": {"accuracy_mean": fl.accuracy_mean,
                           "input_tokens_mean": fl.input_tokens_mean,
                           "input_tokens_p95": fl.input_tokens_p95},
            "per_probe": [
                {"probe_id": r["probe_id"],
                 "cosmocache": {"score": r["cosmocache"]["score"], "tokens": r["cosmocache"]["tokens"]},
                 "flatmemory": {"score": r["flatmemory"]["score"], "tokens": r["flatmemory"]["tokens"]}}
                for r in per_probe_results
            ],
        })

    completed_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "config": config,
        "tiers": tier_summaries,
        "cost": {
            "total_input_tokens": budget.spent,
            "total_output_tokens": 0,
            "usd_estimate": round(budget.spent / 1_000_000 * 15.0, 2),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "report.md").write_text(render_report(summary))
    print(f"Run {run_id} complete. Report: {out_dir / 'report.md'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-probes", type=str, default="")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    dry_run = args.dry_run or cfg.get("dry_run", False)
    only = [s.strip() for s in args.only_probes.split(",") if s.strip()] or cfg.get("only_probes") or []
    return run(cfg, dry_run=dry_run, only_probes=only)


if __name__ == "__main__":
    raise SystemExit(main())
