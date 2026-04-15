#!/usr/bin/env python3
"""Render the phase-2 token-scaling chart as SVG for the landing page.

Matches the cosmocache site palette (parchment cream + violet/coral ink).
Hardcoded values are the post-fix merged numbers (21 unaffected probes from
run 4d6f06 + 4 re-run probes from bb6180). Source of truth:
docs/paper/figures/_render.py.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from pathlib import Path

# Palette — mirrors site/styles.css :root vars.
BG         = "#f9f0cf"   # ~ hsla(48, 71%, 93%, 1)
FG         = "#2a2340"
FG_MUTE    = "#5e527a"
FG_DIM     = "#8a80a3"
VIOLET     = "#7b5cd6"
CORAL      = "#ef7a6d"
BORDER     = (42/255, 35/255, 64/255, 0.14)
BORDER_SFT = (42/255, 35/255, 64/255, 0.07)

PLANETS   = [3,     10,    30,     100]
CC_TOKENS = [3321,  5328,  12753,  20380]
FLAT_TOK  = [1428,  4669,  13874,  46162]

MONO = ["JetBrains Mono", "Berkeley Mono", "IBM Plex Mono",
        "Menlo", "Monaco", "Courier New", "monospace"]

OUT = Path(__file__).resolve().parents[2] / "site" / "assets" / "scaling-chart.svg"


def main() -> None:
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

    ax.set_title("Token cost as the universe grows",
                 color=FG, fontsize=14, fontweight="bold",
                 loc="left", pad=18)

    leg = ax.legend(loc="upper left", frameon=False, fontsize=10,
                    labelcolor=FG, handlelength=1.6)
    for txt in leg.get_texts():
        txt.set_color(FG)

    ax.annotate("2.5× cheaper\nat 100 planets",
                xy=(100, (18258 + 46162) / 2),
                xytext=(46, (18258 + 46162) / 2),
                ha="right", va="center",
                fontsize=10, color=VIOLET, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color=VIOLET,
                                lw=1.2, alpha=0.6))

    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, format="svg", facecolor=BG, bbox_inches="tight",
                pad_inches=0.25)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
