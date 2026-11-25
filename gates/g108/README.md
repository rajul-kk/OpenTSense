# G108: two outside-keep-out buried-die sensors vs eight (gated, 21 Nov 2026)

**Verdict: PASS.** Registered in [registration.md](registration.md), queued as repository commit 262 before the
launch at 00:22:43 (the launch log's name holds its start time). Held-out chips 31-40 and salt 107 come from
`key` in [record/manifest.json](record/manifest.json). Both offset models were run, 20 units, rc=0
([launch log](record/launch.log)). The evaluator, sha256
`da59a60a...` (`evaluator_sha256` in [result.json](record/result.json)), found every validity check true.

| Bar | Offsets | Buried-die paired RMSE, 2 minus 8 outside-uniform sites (mean ± SE) | Largest chip | Bar | Pass |
|---|---|---|---|---|---|
| (a) | Independent | +0.042 ± 0.065 K | +0.528 K | ≤ +0.25 K | yes |
| (b) | Correlated (0.8, 3 mm) | −0.234 ± 0.072 K | +0.013 K | ≤ +0.25 K | yes |

Source: `bars.a` / `bars.b` (`mean`, `se`, `chip_deltas`) in [record/result.json](record/result.json).

## Reported with the verdict

Buried die (`bot`), field-model RMSE, mean over chips 31-40. Source: `paired_rmse_K.<offset>.bot` in
[record/result.json](record/result.json).

| Contrast | Independent | Correlated |
|---|---|---|
| 2 vs 8 outside-uniform (primary) | +0.042 ± 0.065 K | −0.234 ± 0.072 K |
| 2 vs 8 outside-greedy | +0.087 ± 0.050 K | −0.047 ± 0.083 K |
| 2 vs 8 unrestricted uniform | +0.050 ± 0.066 K | −0.111 ± 0.047 K |
| 2 outside vs 8 unrestricted uniform (bridge) | +0.050 ± 0.066 K | −0.111 ± 0.047 K |
| Keep-out cost, 8 uniform sites | +0.007 ± 0.033 K | +0.123 ± 0.035 K |
| Keep-out cost, 8 greedy sites | +0.031 ± 0.042 K | +0.091 ± 0.059 K |

| Arm mean RMSE (buried die) | bot2 uniform | bot2 outside-uniform | bot8 uniform | bot8 outside-uniform |
|---|---|---|---|---|
| Independent | 0.374 K | 0.374 K | 0.325 K | 0.332 K |
| Correlated | 0.403 K | 0.403 K | 0.514 K | 0.637 K |

The two uniform two-site layouts coincide, so their keep-out cost is exactly 0.

## Caveats

- Bar (a) passes on the mean. One chip's delta (+0.528 K) is above the bar on its own; registration fixed the
  mean, not the per-chip maximum. The dry run had warned that single chips came close: +0.225 K, from the
  independent-offset buried-die per-chip deltas in [dry/keepout.json](dry/keepout.json) (line 4449).
- Under correlated offsets, eight outside-uniform sites score worse than two (0.637 vs 0.403 K). The paired mean
  was −0.234 K, which is within the registered +0.25 K tolerance. This run does not show why eight sites do worse
  here; the mechanism is **unverified**. Bar (b) tests "no more than 0.25 K worse"; it does not show that two
  sites are better in general.
- Scope as registered: one stack, steady state, one sensor profile, whole-die RMSE. The active-block keep-out is
  a map-derived proxy for the routing constraint.

## Reproduce

The run took 72.0 s (`wall_s` in `runs/main/scores.json`, not committed) with a peak working set of 2,207,854,592 B
([launch log](record/launch.log)). The command lines are in [registration.md](registration.md#execution). The
scorer is pinned at the version the [A15 rerun](dry/a15/keepout.json) used.
