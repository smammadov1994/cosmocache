# Phase 2 Eval Report — 20260414T042330Z-4d6f06

- started: 2026-04-14T04:23:30.030451+00:00
- completed: 2026-04-14T04:54:10.777598+00:00

## Cost

- total input tokens: 2,391,418
- total output tokens: 0
- estimated USD: $35.87

## Accuracy & token cost, by tier

| Tier | N planets | Accuracy (cosmocache) | Accuracy (flat memory.md) | Input tokens mean (cc) | Input tokens mean (flat) |
|---|---|---|---|---|---|
| real | real | 0.980 | 0.980 | 3321 | 1428 |
| small | 10 | 0.667 | 1.000 | 4251 | 4669 |
| medium | 30 | 0.889 | 1.000 | 12059 | 13874 |
| large | 100 | 0.820 | 1.000 | 18258 | 46162 |

## Degradation curve

Accuracy as the corpus grows. Real planets are always present; higher tiers add synthetic noise.

```
  real  cc=0.980   flat=0.980
    10  cc=0.667   flat=1.000
    30  cc=0.889   flat=1.000
   100  cc=0.820   flat=1.000
```

## Caveat on synthetic scaling

Tiers at 10/30/100 planets are synthetic copies of the 3-planet seed. They measure routing / index scaling and cross-planet interference, not authentic knowledge diversity. Real-world 100-planet universes will differ; these numbers are an upper-bound reference.

## Per-probe detail

### tier: real

| probe_id | cc score | flat score | cc tokens | flat tokens |
|---|---|---|---|---|
| react-memoize-stable-reference | 1.00 | 1.00 | 3051 | 1430 |
| react-composition-beats-usememo | 1.00 | 1.00 | 4724 | 1430 |
| sql-analyze-after-bulk | 1.00 | 1.00 | 5131 | 1426 |
| sql-partial-index-selectivity | 1.00 | 1.00 | 3032 | 1427 |
| devops-canary-duration | 1.00 | 1.00 | 5066 | 1425 |
| devops-rollback-tested | 1.00 | 1.00 | 5060 | 1423 |
| react-jimbo-identity | 1.00 | 1.00 | 3046 | 1426 |
| sql-sally-identity | 1.00 | 1.00 | 2703 | 1420 |
| devops-grom-identity | 1.00 | 1.00 | 2744 | 1424 |
| react-planet-lore-food | 1.00 | 1.00 | 3055 | 1424 |
| sql-planet-lore-ability | 1.00 | 1.00 | 4702 | 1430 |
| devops-planet-lore-tagline | 1.00 | 1.00 | 2604 | 1425 |
| react-wisdom-distilled-composition | 1.00 | 1.00 | 2736 | 1431 |
| sql-wisdom-planner-stats | 1.00 | 1.00 | 2708 | 1426 |
| devops-wisdom-canary-duration | 1.00 | 1.00 | 2747 | 1433 |
| synth-which-planet-for-hooks | 1.00 | 1.00 | 3106 | 1436 |
| synth-which-planet-for-index | 1.00 | 1.00 | 5077 | 1430 |
| synth-which-planet-for-rollback | 1.00 | 1.00 | 3085 | 1427 |
| synth-memoize-and-indexing-both | 1.00 | 1.00 | 2730 | 1430 |
| synth-sql-full-practice | 1.00 | 0.50 | 2722 | 1431 |
| synth-devops-release-checklist | 1.00 | 1.00 | 2738 | 1431 |
| synth-cross-planet-safe-release | 0.50 | 1.00 | 3013 | 1437 |
| neg-kubernetes-decision | 1.00 | 1.00 | 5170 | 1425 |
| neg-rust-memory-model | 1.00 | 1.00 | 1142 | 1425 |
| neg-mobile-ios-decision | 1.00 | 1.00 | 1141 | 1424 |

### tier: small

| probe_id | cc score | flat score | cc tokens | flat tokens |
|---|---|---|---|---|
| react-jimbo-identity | 0.00 | 1.00 | 1444 | 4670 |
| sql-sally-identity | 1.00 | 1.00 | 5895 | 4664 |
| devops-grom-identity | 0.00 | 1.00 | 1442 | 4668 |
| react-planet-lore-food | 0.00 | 1.00 | 1442 | 4668 |
| sql-planet-lore-ability | 1.00 | 1.00 | 5669 | 4674 |
| devops-planet-lore-tagline | 1.00 | 1.00 | 3239 | 4669 |
| neg-kubernetes-decision | 1.00 | 1.00 | 16240 | 4669 |
| neg-rust-memory-model | 1.00 | 1.00 | 1443 | 4669 |
| neg-mobile-ios-decision | 1.00 | 1.00 | 1442 | 4668 |

### tier: medium

| probe_id | cc score | flat score | cc tokens | flat tokens |
|---|---|---|---|---|
| react-composition-beats-usememo | 1.00 | 1.00 | 27173 | 13877 |
| sql-partial-index-selectivity | 1.00 | 1.00 | 27059 | 13874 |
| devops-rollback-tested | 1.00 | 1.00 | 13837 | 13870 |
| react-jimbo-identity | 0.00 | 1.00 | 2416 | 13873 |
| sql-sally-identity | 1.00 | 1.00 | 8790 | 13867 |
| devops-grom-identity | 0.00 | 1.00 | 2414 | 13871 |
| react-planet-lore-food | 1.00 | 1.00 | 2414 | 13871 |
| sql-planet-lore-ability | 1.00 | 1.00 | 8605 | 13877 |
| devops-planet-lore-tagline | 1.00 | 1.00 | 5185 | 13872 |
| react-wisdom-distilled-composition | 1.00 | 1.00 | 9020 | 13878 |
| sql-wisdom-planner-stats | 1.00 | 1.00 | 12282 | 13873 |
| devops-wisdom-canary-duration | 1.00 | 1.00 | 16132 | 13880 |
| synth-memoize-and-indexing-both | 1.00 | 1.00 | 11940 | 13877 |
| synth-sql-full-practice | 1.00 | 1.00 | 12189 | 13878 |
| synth-devops-release-checklist | 1.00 | 1.00 | 21243 | 13878 |
| neg-kubernetes-decision | 1.00 | 1.00 | 31538 | 13872 |
| neg-rust-memory-model | 1.00 | 1.00 | 2415 | 13872 |
| neg-mobile-ios-decision | 1.00 | 1.00 | 2414 | 13871 |

### tier: large

| probe_id | cc score | flat score | cc tokens | flat tokens |
|---|---|---|---|---|
| react-memoize-stable-reference | 1.00 | 1.00 | 25916 | 46164 |
| react-composition-beats-usememo | 1.00 | 1.00 | 25089 | 46164 |
| sql-analyze-after-bulk | 1.00 | 1.00 | 25887 | 46160 |
| sql-partial-index-selectivity | 1.00 | 1.00 | 25497 | 46161 |
| devops-canary-duration | 1.00 | 1.00 | 19769 | 46159 |
| devops-rollback-tested | 1.00 | 1.00 | 26752 | 46157 |
| react-jimbo-identity | 0.00 | 1.00 | 5824 | 46160 |
| sql-sally-identity | 1.00 | 1.00 | 19002 | 46154 |
| devops-grom-identity | 0.00 | 1.00 | 5822 | 46158 |
| react-planet-lore-food | 0.00 | 1.00 | 5822 | 46158 |
| sql-planet-lore-ability | 1.00 | 1.00 | 19036 | 46164 |
| devops-planet-lore-tagline | 1.00 | 1.00 | 11999 | 46159 |
| react-wisdom-distilled-composition | 1.00 | 1.00 | 19295 | 46165 |
| sql-wisdom-planner-stats | 0.00 | 1.00 | 5824 | 46160 |
| devops-wisdom-canary-duration | 1.00 | 1.00 | 19154 | 46167 |
| synth-which-planet-for-hooks | 1.00 | 1.00 | 19107 | 46170 |
| synth-which-planet-for-index | 1.00 | 1.00 | 25912 | 46164 |
| synth-which-planet-for-rollback | 1.00 | 1.00 | 19116 | 46161 |
| synth-memoize-and-indexing-both | 1.00 | 1.00 | 5828 | 46164 |
| synth-sql-full-practice | 1.00 | 1.00 | 25198 | 46165 |
| synth-devops-release-checklist | 1.00 | 1.00 | 18436 | 46165 |
| synth-cross-planet-safe-release | 0.50 | 1.00 | 19426 | 46171 |
| neg-kubernetes-decision | 1.00 | 1.00 | 51087 | 46159 |
| neg-rust-memory-model | 1.00 | 1.00 | 5823 | 46159 |
| neg-mobile-ios-decision | 1.00 | 1.00 | 5822 | 46158 |
