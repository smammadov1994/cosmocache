"""Render a Phase 2 eval run into a markdown report."""
from __future__ import annotations


def render_report(summary: dict) -> str:
    lines: list[str] = []
    lines.append(f"# Phase 2 Eval Report — {summary['run_id']}\n")
    lines.append(f"- started: {summary['started_at']}")
    lines.append(f"- completed: {summary['completed_at']}")
    lines.append("")

    lines.append("## Cost\n")
    c = summary["cost"]
    lines.append(f"- total input tokens: {c['total_input_tokens']:,}")
    lines.append(f"- total output tokens: {c['total_output_tokens']:,}")
    lines.append(f"- estimated USD: ${c['usd_estimate']:.2f}")
    lines.append("")

    lines.append("## Accuracy & token cost, by tier\n")
    lines.append("| Tier | N planets | Accuracy (cosmocache) | Accuracy (flat memory.md) | Input tokens mean (cc) | Input tokens mean (flat) |")
    lines.append("|---|---|---|---|---|---|")
    for t in summary["tiers"]:
        n = t["n_planets"] if t["n_planets"] is not None else "real"
        lines.append(
            f"| {t['name']} | {n} | "
            f"{t['cosmocache']['accuracy_mean']:.3f} | {t['flatmemory']['accuracy_mean']:.3f} | "
            f"{t['cosmocache']['input_tokens_mean']:.0f} | {t['flatmemory']['input_tokens_mean']:.0f} |"
        )
    lines.append("")

    lines.append("## Degradation curve\n")
    lines.append("Accuracy as the corpus grows. Real planets are always present; higher tiers add synthetic noise.\n")
    lines.append("```")
    for t in summary["tiers"]:
        n = t["n_planets"] if t["n_planets"] is not None else "real"
        lines.append(
            f"{str(n):>6}  cc={t['cosmocache']['accuracy_mean']:.3f}   flat={t['flatmemory']['accuracy_mean']:.3f}"
        )
    lines.append("```\n")

    lines.append("## Caveat on synthetic scaling\n")
    lines.append("Tiers at 10/30/100 planets are synthetic copies of the 3-planet seed. They measure "
                 "routing / index scaling and cross-planet interference, not authentic knowledge diversity. "
                 "Real-world 100-planet universes will differ; these numbers are an upper-bound reference.\n")

    lines.append("## Per-probe detail\n")
    for t in summary["tiers"]:
        lines.append(f"### tier: {t['name']}\n")
        lines.append("| probe_id | cc score | flat score | cc tokens | flat tokens |")
        lines.append("|---|---|---|---|---|")
        for p in t["per_probe"]:
            lines.append(
                f"| {p['probe_id']} | {p['cosmocache']['score']:.2f} | {p['flatmemory']['score']:.2f} | "
                f"{p['cosmocache']['tokens']} | {p['flatmemory']['tokens']} |"
            )
        lines.append("")

    return "\n".join(lines)
