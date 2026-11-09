# G81c: real program power levels in the guard-margin testbed · FAIL on (b), throughput clause only (9 Nov 2026)

Registration: `registration.md` (bars fixed before any run; no amendments). Code: `g81c.py`. Result: `runs/main/result.json`, log `run_main.log` (34 min).

## Runs
| Attempt | Log | Outcome |
|---|---|---|
| Dry run 1 | `dry_attempt1_memerr.log` | Blocked: host low on memory, `MemoryError` (396 MiB) inside G39's `sensors` |
| Dry run 2 | `dry_attempt2_noplant.log` | Blocked: `experiments/code/sens/plant62.npz` had been moved to `experiments/scratch_archive_2026-10-29/sens/`. Copied back (sha256 `e9d24859…83c1`, identical to the archive copy) |
| Dry run 3 | `dry.log`, `dry/result.json` | (v) PASS: limits, oracle calibration, (a), (b) and verdicts equal `g69_res.json` |
| Main | `run_main.log`, `runs/main/result.json` | (v) PASS again; (a) PASS; (b) FAIL. Claude Code's low-memory guard stopped the launching shell; the Python process kept running to completion, and its output is unaffected |

## Results
Tile power: programs 6.44–7.96 mW (G81b totals × 7.75/8.081), sleep 2.565 mW; G30 kernels 7.00–7.75 mW.

| | Margin (K) | F4test violation | Oracle | Excess (pp) | Throughput |
|---|---|---|---|---|---|
| (a) E, F1+F2+F3 | 3.0 | 0.041% | 0.470% | −0.43 ✓ | 0.99086 |
| (a) R, F1+F2+F3 | 6.0 | 0.141% | 0.470% | −0.33 | 0.99451 |
| (b) E, F4cal | 0.0 | 0.387% | 0.470% | −0.08 ✓ | **0.99542** |
| (b) R, F4cal | 5.25 | 0.733% | 0.470% | +0.26 | **0.99569** |

(b) fails only on its throughput clause (E ≥ R): E is 0.027 pp lower. R's lead comes from violating more on F4test. E's calibrated margin is at the grid floor (0 K), so E could not trade violation for throughput.

Reported, not gated:
- Limits (°C): F1 66.39, F2 67.28, F3 56.20, F4 66.74.
- Uncontrolled CPU peak 10/50/90%: F1 45.8 / 61.1 / 69.7 °C; F4 46.3 / 63.6 / 69.7 °C.
- F4cal margins on other families: E excess F1 −0.17, F2 0.00, F3 +13.8 pp; R F1 +0.09, F2 +0.001, F3 +2.5 pp (F3's moving hotspots are still uncovered, as G69 found).
- Frequency cost of the F4cal margins: R 0.336%, E 0%.

## Reading
- Margins calibrated on synthetic workloads hold when the tiles run real programs: (a) is well inside the bar. At the testbed's resolution (one 77 µm tile ≈ 1.5 thermal cells, 0.5 ms steps), real-program power levels behave like G30's kernels.
- Calibration on one program set covers a disjoint set for violation: both policies are inside 0.5 pp on F4test.
- The failed clause compares policies at different realised violation. Future policy comparisons should be made at matched realised violation, or allow negative margins. Carried into G89; G81c is not amended.
- Not tested: real schedules (still F1's synthetic phase structure), TPU workloads (G81d), memory power (G81e).
