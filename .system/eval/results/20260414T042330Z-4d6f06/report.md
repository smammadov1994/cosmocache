# Phase 2 Eval Report — 20260414T042330Z-4d6f06 (merged, post-fix)

> **Post-fix merged view.** This file was regenerated after the
> `build_synthetic_universe()` glossary-clobber bug was fixed. The four
> affected probes (`react-jimbo-identity`, `devops-grom-identity`,
> `react-planet-lore-food`, `sql-wisdom-planner-stats`) were re-run in
> `20260414T070946Z-bb6180` and their post-fix scores are merged below.
> The other 21 probes are reproduced unchanged from the original run.
>
> The pre-fix raw report (with the 0.82 / 0.67 / 0.89 tier accuracies that
> the bug produced) is preserved verbatim at
> [`report.prefix-bug.md`](./report.prefix-bug.md) for audit honesty.
> Machine-readable merged data lives in
> [`../20260414T070946Z-bb6180/merged_summary.json`](../20260414T070946Z-bb6180/merged_summary.json).

- started: 2026-04-14T04:23:30.030451+00:00
- completed: 2026-04-14T07:14:27.731266+00:00 (includes bb6180 re-run)

## Cost

- total input tokens: 2,803,711 (4d6f06: 2,391,418 + bb6180: 412,293)
- total output tokens: 0
- estimated USD: $42.05

## Accuracy & token cost, by tier (merged)

| Tier   | N planets | Accuracy (cosmocache) | Accuracy (flat memory.md) | Input tokens mean (cc) | Input tokens mean (flat) |
|--------|-----------|-----------------------|---------------------------|------------------------|--------------------------|
| real   | 3         | 0.980                 | 0.980                     | 3,321                  | 1,428                    |
| small  | 10        | 1.000                 | 1.000                     | 5,328                  | 4,669                    |
| medium | 30        | 1.000                 | 1.000                     | 12,753                 | 13,874                   |
| large  | 100       | 0.980                 | 1.000                     | 20,380                 | 46,162                   |

Headline: **accuracy parity** with flat memory (within ±0.02 at every tier)
and **~2.3× fewer tokens at 100 planets**.

## Degradation curve

Accuracy as the corpus grows. Real planets are always present; higher tiers
add synthetic noise.

```
  real  cc=0.980   flat=0.980
    10  cc=1.000   flat=1.000
    30  cc=1.000   flat=1.000
   100  cc=0.980   flat=1.000
```

## Caveat on synthetic scaling

Tiers at 10/30/100 planets are synthetic copies of the 3-planet seed. They
measure routing / index scaling and cross-planet interference, not authentic
knowledge diversity. Real-world 100-planet universes will differ; these
numbers are an upper-bound reference.

## Why the re-run was needed

In the original 4d6f06 run, `build_synthetic_universe()` rebuilt the
glossary from the synthetic manifest only, clobbering the canonical rows
for the four real planets. That starved routing on the four identity /
lore probes that explicitly ask about those canonical planets — so
cosmocache failed them even though the content was on disk.

The fix preserves canonical glossary rows during synthetic scale-up.
After the fix, those four probes score 1.00 at every tier. The 21
unaffected probes already scored 1.00 (mean 0.98 at real and large
tiers is driven by the single `synth-cross-planet-safe-release` partial
credit and `synth-sql-full-practice` partial at real tier, both
independent of the glossary bug) and were not re-run.

See `../../docs/paper/cosmocache-phase-2.md` for full write-up; per-probe
detail for the merged view is in the figures and in
`merged_summary.json`.
