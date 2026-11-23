# G104: Does the field model still work with sensors only outside the dense logic? (O2, RQ3) · PASS (run 18 Nov 2026)

Registration: `registration.md` (queued as #196 before the run; bars fixed under the student's delegation of 18 Nov).
Run: `run.py runs/main` (chips 21-30; chips 1-5 were the dry run, `dry/sites.json`), scored by
`evaluate.py runs/main`. Output `runs/main/` (git-ignored); record: `record/{result,manifest}.json`.

## Verdict: PASS

Validity held: G84's case set rebuilt to its recorded sha256, the placed sites and placement noise equal to the dry
run's, the code, block-map and stack-config hashes unchanged from start to end, chips 21-30, both registered offset
models, all four sets with 8 sensors on each die.

| Bar | Needed | Result |
|---|---|---|
| (a) `outside/uniform` beats the average, both offset models, both dies | CI below 0 in >= 8 of 10 chips | 10 of 10 in all four |
| (b) `outside/uniform` - `all/uniform` mean RMSE, independent offsets, both dies | <= 0.25 K | +0.08 K top, +0.06 K bottom |

## Reported (not gated), chips 21-30

Field-model RMSE over the whole die in K (mean over chips of the mean group median), top / bottom; peak error;
difference from `all/uniform` paired by chip, mean +- standard error. The average's RMSE is 3.21 / 2.98 K.

| Offsets | Site set | RMSE | Peak error | vs all/uniform, top | vs all/uniform, bottom |
|---|---|---|---|---|---|
| independent | all/uniform | 0.27 / 0.36 | 0.58 / 0.63 | - | - |
| independent | outside/uniform | 0.35 / 0.42 | 0.72 / 0.72 | +0.08 +- 0.03 | +0.06 +- 0.03 |
| independent | all/greedy_a | 0.18 / 0.21 | 0.50 / 0.38 | -0.09 +- 0.03 | -0.15 +- 0.03 |
| independent | outside/greedy_a | 0.27 / 0.30 | 0.62 / 0.61 | -0.00 +- 0.03 | -0.06 +- 0.02 |
| 0.8, 3 mm | all/uniform | 0.46 / 0.48 | 0.99 / 0.90 | - | - |
| 0.8, 3 mm | outside/uniform | 0.62 / 0.58 | 1.29 / 0.91 | +0.16 +- 0.05 | +0.10 +- 0.03 |
| 0.8, 3 mm | all/greedy_a | 0.35 / 0.33 | 0.82 / 0.65 | -0.10 +- 0.07 | -0.15 +- 0.06 |
| 0.8, 3 mm | outside/greedy_a | 0.52 / 0.48 | 1.23 / 1.08 | +0.07 +- 0.10 | +0.00 +- 0.05 |

Every set beats the average in 10 of 10 chips, on both dies, in both offset models.

- **Keeping sensors out of the dense block costs little.** The uniform grid moved out of the block loses 0.06-0.08 K
  with independent offsets and 0.10-0.16 K with die-wide correlated ones; all eight sets stay at a fifth of the
  average's error or better.
- **A placement chosen for the field model wins the loss back.** Greedy A-optimal placement outside the block
  matches the unrestricted uniform grid (-0.00 / -0.06 K independent, +0.07 / +0.00 K correlated). Against the
  uniform grid outside the block it is better with independent offsets (-0.09 +- 0.04 / -0.12 +- 0.02 K) and about
  as much with correlated ones, though there within its spread (-0.09 +- 0.13 / -0.10 +- 0.08 K;
  `reported.outside_greedy_minus_outside_uniform`). Greedy on the whole die is the best set throughout.
- **The dry run's warning did not hold.** On chips 1-5, `outside/greedy_a` was 0.32 +- 0.09 K worse than
  `all/uniform` on the bottom die with correlated offsets; on chips 21-30 it is +0.00 +- 0.05 K. Five chips were too few
  (code lint L57); the registration reported it rather than gating on it.

**Not claimed.** RMSE and peak error are over the whole die; the block's own error is not measured. One stack, steady
state, 8 sensors per die, one sensor class; the 2-cell ring is assumed.
