# G81f: Memory-die power follows the workload, refitted energy model (RQ2) · FAIL (run 16 Nov 2026)

Registration: `registration.md` (queued as #110 before the run): G81e's step 2 and bars unchanged, energy model
refitted (`dry/fit_energy2.json`). Run: `run.py runs/main`. Output `runs/main/` (git-ignored); record:
`record/{result,manifest}.json`.

## Verdict: FAIL on (a2)

| Validity | Result | Held? |
|---|---|---|
| (v2) controller | 0 violations in every command trace; G50a reproduced (6.2187 pJ/bit) | yes |
| (v3) energy model within 0.1% of DRAMPower per program | worst 3.4e-4 (G81e: 2.4e-3) | yes |

| Bar | Needed | Result |
|---|---|---|
| (a1) memory power differs by program | 15 of 19 | 17 of 19 (wikisort, sglib-combined near the median) |
| (a2) dynamic power follows the fills, Pearson >= 0.9 in every seed | 15 of 19 | **12 of 19** |
| (b) the sorted bank shares are structured | 15 of 19 | 18 of 19 (xgboost flat) |

The values of G81e's bars, seen before this registration (declared there), were the same: 17, 12 and 18.

| (a2) failed | Pearson over seeds 1-5 | Dynamic share of total power |
|---|---|---|
| nsichneu | 0.13-0.19 | 81% |
| xgboost | 0.79-0.86 | 54% |
| tarfind | 0.82-0.86 | 13% |
| huffbench | 0.84-0.87 | 10% |
| wikisort | 0.87-0.94 | 9% |
| sglib-combined | 0.87-0.96 | 6% |
| edn | 0.85-1.00 (one seed below) | 1% |

## Why (diagnosed after the run on seed 1; exploratory, the verdict stands)

- **nsichneu:** it misses in every window at an almost constant rate (coefficient of variation 3%), so misses carry
  no window-to-window signal. Its dynamic energy still varies by 16%, set by row-buffer hits against activates.
- **The others:** the energy per miss varies between windows by 25% (xgboost) to 83% (huffbench), because a miss
  costs an activate or rides an open row, and write-backs (up to 48% of transactions in tarfind) add energy the
  fills do not count. Pairing with all transactions moves Pearson by at most 0.02. Shifting the series by up to 5
  windows (controller backlog) does not help.

So the memory die's power does follow the program ((a1) and (b) pass), but per window it follows the row-buffer
behaviour, not the miss count alone. A 0.9 bar against misses was too strict for an open-page controller.

## Consequence

The benchmark uses the workload-driven memory maps (G81e's pipeline, this fit) with (a1) and (b) as the evidence that
they differ by program and are not flat. It does not claim that memory power tracks cache misses window by window.
Any rerun with another pairing (activates, or row misses) would be a new gate registered before it runs, not a
rescoring of this one.
