# G81b: whole-program power timelines on the routed ASAP7 ibex · PASS

Registration: `registration.md` (with Amendment 1, 9 Nov, written before the run). Run: `run.sh main`, 9 Nov 2026, 5.9 h
(build 19 min, simulation 3.0 h two at a time, OpenSTA 2.5 h for 419 windows). Output: `runs/main/` (`result.json`, `manifest.json`).

| Bar | Result |
|---|---|
| (a) correct programs | all 19 Embench benchmarks `verify_benchmark()` = success with `done=1`; idle checksum `9c2704d8` = host model |
| (b) annotation | 100% of pins (70,206) in all 419 windows |
| (c) timeline vs power, Pearson on test windows ≥ 0.95 | all 20 programs; lowest crc32 0.977, then matmult-int 0.978; 16 of 20 ≥ 0.995. Relative RMS error 0.03–0.35% |

Reported, not gated:
- **Prediction (wider spread than G30's 1.11×): holds.** Mean window dynamic power per benchmark spans 6.72 mW (ud) to 8.30 mW (aha-mont64), 1.24×; single windows span 1.36×. Every window lay inside its benchmark's start/stop markers.
- **Idle:** sleep windows draw 0.32× the compute windows' total power (2.56 vs 8.08 mW; why sleep is not lower, e.g. how much of the clock tree still toggles in `wfi`, was not examined). Leakage is 0.12% of total in sleep windows and about 0.03% in compute: ASAP7 RVT leakage is negligible at TT, so idle phases in this core are a dynamic-power step, not a leakage window.
- **Spread within a program** is small for most (e.g. crc32 0.65%, xgboost 2%), larger for edn (12%), matmult-int (10%) and nettle-aes (20%), each from a few low-power windows. The high Pearson on near-constant programs comes from the fit tracking small real variations, with RMS errors well under 1%.
- **Per-region power** (4 × 4 die grid): e.g. aha-mont64's top-right region carries 0.4% and the centre regions 9–11%. Shares per program are in `result.json`.
- Verilator speed 1,100–1,450 cycles/s per job, two jobs at a time (23.4M cycles in all). The default-activity ratio is deferred (Amendment 1).

Consequence: the toggle timeline can stand in for window power between OpenSTA windows (G81c), with a per-program fit.
