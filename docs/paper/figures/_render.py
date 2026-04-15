#!/usr/bin/env python3
"""Render figures for the cosmocache phase-2 paper.

Headline numbers reflect the post-fix merged result: raw answers from
20260414T042330Z-4d6f06 for the 21 probes unaffected by the glossary-
clobber bug, plus answers from 20260414T070946Z-bb6180 for the 4
probes re-run after the fix to build_synthetic_universe() preserved
canonical glossary rows. See merged_summary.json in the bb6180 dir.
Matches the cosmocache site palette.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Palette (mirrors site/styles.css :root vars).
BG         = "#f9f0cf"
FG         = "#2a2340"
FG_MUTE    = "#5e527a"
FG_DIM     = "#8a80a3"
VIOLET     = "#7b5cd6"
CORAL      = "#ef7a6d"
MOSS       = "#7cae7a"
GOLD       = "#e7b850"
BORDER     = (42/255, 35/255, 64/255, 0.14)
BORDER_SFT = (42/255, 35/255, 64/255, 0.07)

MONO = ["JetBrains Mono", "Berkeley Mono", "IBM Plex Mono",
        "DejaVu Sans Mono", "Menlo", "Monaco", "Courier New", "monospace"]

OUT_DIR = Path(__file__).resolve().parent

# Headline data (post-fix merged).
TIERS      = ["real",  "small", "medium", "large"]
PLANETS    = [3,       10,      30,       100]
CC_ACC     = [0.980,   1.000,   1.000,    0.980]
FLAT_ACC   = [0.980,   1.000,   1.000,    1.000]
CC_TOKENS  = [3321,    5328,    12753,    20380]
FLAT_TOK   = [1428,    4669,    13874,    46162]


def setup_matplotlib() -> None:
    mpl.rcParams.update({
        "font.family":      MONO,
        "font.size":        11,
        "axes.edgecolor":   FG,
        "axes.labelcolor":  FG,
        "xtick.color":      FG_MUTE,
        "ytick.color":      FG_MUTE,
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "svg.fonttype":     "none",
    })


def fig1_token_scaling() -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.4), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    ax.fill_between(PLANETS, CC_TOKENS, FLAT_TOK,
                    where=[f > c for f, c in zip(FLAT_TOK, CC_TOKENS)],
                    color=VIOLET, alpha=0.10, linewidth=0, zorder=1,
                    label="tokens saved")

    ax.plot(PLANETS, FLAT_TOK,
            color=CORAL, linewidth=2.0, marker="o", markersize=6,
            markerfacecolor=CORAL, markeredgecolor=BG, markeredgewidth=1.5,
            label="flat memory.md", zorder=3)
    ax.plot(PLANETS, CC_TOKENS,
            color=VIOLET, linewidth=2.0, marker="o", markersize=6,
            markerfacecolor=VIOLET, markeredgecolor=BG, markeredgewidth=1.5,
            label="cosmocache", zorder=4)

    for x, y in zip(PLANETS, CC_TOKENS):
        ax.annotate(f"{y:,}", (x, y), textcoords="offset points",
                    xytext=(0, -16), ha="center", fontsize=9,
                    color=VIOLET, fontweight="bold")
    for x, y in zip(PLANETS, FLAT_TOK):
        ax.annotate(f"{y:,}", (x, y), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=9,
                    color=CORAL, fontweight="bold")

    ax.set_xscale("log")
    ax.set_xticks(PLANETS)
    ax.set_xticklabels([str(p) for p in PLANETS])
    ax.tick_params(axis="x", which="minor", bottom=False)
    ax.set_xlabel("planets in universe (log scale)",
                  color=FG_MUTE, fontsize=11, labelpad=10)
    ax.set_ylabel("input tokens per probe (mean)",
                  color=FG_MUTE, fontsize=11, labelpad=10)

    ax.set_ylim(0, 52000)
    ax.set_yticks([0, 10000, 20000, 30000, 40000, 50000])
    ax.set_yticklabels(["0", "10k", "20k", "30k", "40k", "50k"])

    ax.grid(axis="y", color=BORDER_SFT, linewidth=1, zorder=0)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BORDER)
        ax.spines[spine].set_linewidth(1)

    ax.set_title("Figure 1. Input-token cost per probe, by universe size",
                 color=FG, fontsize=13, fontweight="bold",
                 loc="left", pad=18)

    leg = ax.legend(loc="upper left", frameon=False, fontsize=10,
                    labelcolor=FG, handlelength=1.6)
    for txt in leg.get_texts():
        txt.set_color(FG)

    ax.annotate("2.3x cheaper\nat 100 planets",
                xy=(100, (20380 + 46162) / 2),
                xytext=(46, (20380 + 46162) / 2),
                ha="right", va="center",
                fontsize=10, color=VIOLET, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color=VIOLET,
                                lw=1.2, alpha=0.6))

    plt.tight_layout()
    out = OUT_DIR / "fig1-token-scaling.svg"
    fig.savefig(out, format="svg", facecolor=BG, bbox_inches="tight",
                pad_inches=0.25)
    plt.close(fig)
    print(f"wrote {out}")


def fig2_accuracy_by_tier() -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.4), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    x = np.arange(len(TIERS))
    width = 0.38

    bars_cc = ax.bar(x - width/2, CC_ACC, width,
                     label="cosmocache", color=VIOLET,
                     edgecolor=BG, linewidth=1.2, zorder=3)
    bars_fl = ax.bar(x + width/2, FLAT_ACC, width,
                     label="flat memory.md", color=CORAL,
                     edgecolor=BG, linewidth=1.2, zorder=3)

    for b, v in zip(bars_cc, CC_ACC):
        ax.annotate(f"{v:.2f}", (b.get_x() + b.get_width()/2, v),
                    textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=9, color=VIOLET, fontweight="bold")
    for b, v in zip(bars_fl, FLAT_ACC):
        ax.annotate(f"{v:.2f}", (b.get_x() + b.get_width()/2, v),
                    textcoords="offset points", xytext=(0, 4),
                    ha="center", fontsize=9, color=CORAL, fontweight="bold")

    ax.set_xticks(x)
    labels = [
        "real\n(3 planets)",
        "small\n(10 synthetic)",
        "medium\n(30 synthetic)",
        "large\n(100 synthetic)",
    ]
    ax.set_xticklabels(labels, color=FG_MUTE, fontsize=10)

    ax.set_ylim(0, 1.15)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0", "0.25", "0.50", "0.75", "1.00"])
    ax.set_ylabel("LLM-judge accuracy",
                  color=FG_MUTE, fontsize=11, labelpad=10)

    ax.axhline(1.0, color=BORDER_SFT, linewidth=1, linestyle=":", zorder=1)
    ax.grid(axis="y", color=BORDER_SFT, linewidth=1, zorder=0)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BORDER)
        ax.spines[spine].set_linewidth(1)

    ax.set_title("Figure 2. Accuracy by tier (cosmocache vs flat)",
                 color=FG, fontsize=13, fontweight="bold",
                 loc="left", pad=18)

    leg = ax.legend(loc="lower left", frameon=False, fontsize=10,
                    labelcolor=FG, handlelength=1.6)
    for txt in leg.get_texts():
        txt.set_color(FG)

    plt.tight_layout()
    out = OUT_DIR / "fig2-accuracy-by-tier.svg"
    fig.savefig(out, format="svg", facecolor=BG, bbox_inches="tight",
                pad_inches=0.25)
    plt.close(fig)
    print(f"wrote {out}")


def fig3_savings_ratio() -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.0), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    ratios = [f / c for f, c in zip(FLAT_TOK, CC_TOKENS)]
    x = np.arange(len(TIERS))

    colors = []
    for r in ratios:
        if r < 1.0:
            colors.append(CORAL)   # flat is cheaper
        elif r < 1.15:
            colors.append(GOLD)    # near parity
        else:
            colors.append(VIOLET)

    bars = ax.bar(x, ratios, width=0.55,
                  color=colors, edgecolor=BG, linewidth=1.2, zorder=3)

    for b, r in zip(bars, ratios):
        ax.annotate(f"{r:.2f}x",
                    (b.get_x() + b.get_width()/2, r),
                    textcoords="offset points", xytext=(0, 6),
                    ha="center", fontsize=10, color=FG, fontweight="bold")

    ax.axhline(1.0, color=FG_DIM, linewidth=1, linestyle="--", zorder=2)
    ax.annotate("parity", xy=(3.45, 1.0), xytext=(0, 2),
                textcoords="offset points", ha="right", fontsize=9,
                color=FG_DIM)

    labels = [
        "real\n(3)",
        "small\n(10)",
        "medium\n(30)",
        "large\n(100)",
    ]
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=FG_MUTE, fontsize=10)

    ax.set_ylabel("flat tokens / cosmocache tokens",
                  color=FG_MUTE, fontsize=11, labelpad=10)
    ax.set_ylim(0, 3.0)
    ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax.grid(axis="y", color=BORDER_SFT, linewidth=1, zorder=0)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BORDER)
        ax.spines[spine].set_linewidth(1)

    ax.set_title("Figure 3. Token-cost savings ratio (higher = cosmocache wins)",
                 color=FG, fontsize=13, fontweight="bold",
                 loc="left", pad=18)

    plt.tight_layout()
    out = OUT_DIR / "fig3-savings-ratio.svg"
    fig.savefig(out, format="svg", facecolor=BG, bbox_inches="tight",
                pad_inches=0.25)
    plt.close(fig)
    print(f"wrote {out}")


def fig4_probe_scatter_large() -> None:
    """Per-probe detail at the 100-planet tier (post-fix merged)."""
    # Technical / routing / negative / cross probes from 4d6f06.
    # Identity / lore / wisdom probes previously clobbered by the glossary
    # bug were re-run under bb6180 after the fix; their new scores + tokens
    # replace the pre-fix entries below.
    probes = [
        ("react-memoize-stable-reference",       "technical", 1.00, 25916),
        ("react-composition-beats-usememo",      "technical", 1.00, 25089),
        ("sql-analyze-after-bulk",               "technical", 1.00, 25887),
        ("sql-partial-index-selectivity",        "technical", 1.00, 25497),
        ("devops-canary-duration",               "technical", 1.00, 19769),
        ("devops-rollback-tested",               "technical", 1.00, 26752),
        ("react-jimbo-identity",                 "identity",  1.00, 15350),  # re-run
        ("sql-sally-identity",                   "identity",  1.00, 19002),
        ("devops-grom-identity",                 "identity",  1.00, 15004),  # re-run
        ("react-planet-lore-food",               "lore",      1.00, 23327),  # re-run
        ("sql-planet-lore-ability",              "lore",      1.00, 19036),
        ("devops-planet-lore-tagline",           "lore",      1.00, 11999),
        ("react-wisdom-distilled-composition",   "wisdom",    1.00, 19295),
        ("sql-wisdom-planner-stats",             "wisdom",    1.00, 22656),  # re-run
        ("devops-wisdom-canary-duration",        "wisdom",    1.00, 19154),
        ("synth-which-planet-for-hooks",         "routing",   1.00, 19107),
        ("synth-which-planet-for-index",         "routing",   1.00, 25912),
        ("synth-which-planet-for-rollback",      "routing",   1.00, 19116),
        ("synth-memoize-and-indexing-both",      "cross",     1.00,  5828),
        ("synth-sql-full-practice",              "cross",     1.00, 25198),
        ("synth-devops-release-checklist",       "cross",     1.00, 18436),
        ("synth-cross-planet-safe-release",      "cross",     0.50, 19426),
        ("neg-kubernetes-decision",              "negative",  1.00, 51087),
        ("neg-rust-memory-model",                "negative",  1.00,  5823),
        ("neg-mobile-ios-decision",              "negative",  1.00,  5822),
    ]

    cat_order = ["technical", "identity", "lore", "wisdom",
                 "routing", "cross", "negative"]
    cat_color = {
        "technical": VIOLET,
        "identity":  CORAL,
        "lore":      GOLD,
        "wisdom":    MOSS,
        "routing":   "#4a7ba8",
        "cross":     "#a04a7b",
        "negative":  FG_DIM,
    }

    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    xpos = {c: i for i, c in enumerate(cat_order)}

    rng = np.random.default_rng(42)
    for cat in cat_order:
        xs, ys_pass, ys_fail, ys_partial = [], [], [], []
        for _, c, score, _tok in probes:
            if c != cat:
                continue
            jitter = rng.uniform(-0.18, 0.18)
            x = xpos[cat] + jitter
            if score == 1.0:
                xs.append(x); ys_pass.append(score)
            elif score == 0.0:
                xs.append(x); ys_fail.append(score)
            else:
                xs.append(x); ys_partial.append(score)
        # Plot all three sets per category with category color.
        pass_x = [x for (_, c, s, _t), x in zip(probes, []) if False]

    # Simpler: one scatter pass over everything with per-point style.
    for (pid, cat, score, _tok) in probes:
        jitter = rng.uniform(-0.18, 0.18)
        x = xpos[cat] + jitter
        color = cat_color[cat]
        if score == 1.0:
            marker, edge, size = "o", color, 90
            face = color
        elif score == 0.0:
            marker, edge, size = "X", color, 130
            face = CORAL
        else:
            marker, edge, size = "D", color, 90
            face = GOLD
        ax.scatter(x, score, marker=marker, s=size,
                   facecolor=face, edgecolor=edge, linewidth=1.4,
                   zorder=3)

    ax.set_xticks(list(xpos.values()))
    ax.set_xticklabels(cat_order, color=FG_MUTE, fontsize=10)
    ax.set_ylim(-0.15, 1.15)
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_yticklabels(["fail", "partial", "pass"])
    ax.set_ylabel("cosmocache probe outcome",
                  color=FG_MUTE, fontsize=11, labelpad=10)

    ax.grid(axis="y", color=BORDER_SFT, linewidth=1, zorder=0)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BORDER)
        ax.spines[spine].set_linewidth(1)

    ax.set_title("Figure 4. Per-probe outcomes, cosmocache at 100-planet tier",
                 color=FG, fontsize=13, fontweight="bold",
                 loc="left", pad=18)

    # Legend for markers.
    from matplotlib.lines import Line2D
    legend_elems = [
        Line2D([0], [0], marker="o", color="none",
               markerfacecolor=FG_MUTE, markeredgecolor=FG_MUTE,
               markersize=9, label="pass"),
        Line2D([0], [0], marker="D", color="none",
               markerfacecolor=GOLD, markeredgecolor=FG_MUTE,
               markersize=8, label="partial"),
        Line2D([0], [0], marker="X", color="none",
               markerfacecolor=CORAL, markeredgecolor=FG_MUTE,
               markersize=10, label="fail"),
    ]
    leg = ax.legend(handles=legend_elems, loc="lower right",
                    frameon=False, fontsize=10, labelcolor=FG,
                    handlelength=1.2)
    for txt in leg.get_texts():
        txt.set_color(FG)

    plt.tight_layout()
    out = OUT_DIR / "fig4-probe-scatter-large.svg"
    fig.savefig(out, format="svg", facecolor=BG, bbox_inches="tight",
                pad_inches=0.25)
    plt.close(fig)
    print(f"wrote {out}")


def main() -> None:
    setup_matplotlib()
    fig1_token_scaling()
    fig2_accuracy_by_tier()
    fig3_savings_ratio()
    fig4_probe_scatter_large()


if __name__ == "__main__":
    main()
