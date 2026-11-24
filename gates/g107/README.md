# G107: How few sensors does the buried die need? (O2, RQ3) · PASS (run 20 Nov 2026)

Registration: `registration.md` (queued as #240 before the run; bars fixed under the student's delegation). Run:
`run.py runs/main` (chips 21-30; chips 1-5 were the dry run, `dry/budget.json`), scored by `evaluate.py runs/main`.
Output `runs/main/` (git-ignored); record: `record/{result,manifest}.json`. `run.py` writes no manifest: the record's
`manifest.json` was written after the run from the input hashes the run recorded in `scores.json` (its `note` says
so). Cost (`runs/main.log`, git-ignored): "done in 189.4 s" for placement and scoring after the case-set rebuild,
peak working set 2.22 GB (measured by a psutil wrapper around `run.py`); the whole launch took about 7 min by the
launching shell's clock (not saved).

## Verdict: PASS

Validity held: G84's case set rebuilt to its recorded sha256; the placed sites, buried die and placement noise equal
to the dry run's; chips 21-30, salt 107, profile `ring_osc`, both offset models; every set present with its
registered per-die count; all values finite; the run complete with its inputs unchanged.

| Bar (buried die, mean RMSE over 10 chips minus `bot8/uniform`) | Needed | Result |
|---|---|---|
| (a) `bot0/uniform`, independent offsets | <= 0.25 K | +0.11 K |
| (b) `bot2/uniform`, independent offsets | <= 0.25 K | -0.06 K |
| (c) `bot2/uniform`, correlated offsets (0.8, 3 mm) | <= 0.25 K | +0.03 K |

## Reported (not gated), chips 21-30

Field-model RMSE and peak error on the buried die in K (mean over chips of the mean group median); paired
difference from `bot8/uniform`, mean +- standard error over chips, buried die then top die. The average's RMSE is
2.98 K buried, 3.21 K top. The field model beat the average (CI below 0) in 10 of 10 chips for every set, die and
offset model.

| Offsets | Site set | Buried RMSE | Buried peak error | vs bot8, buried | vs bot8, top |
|---|---|---|---|---|---|
| independent | bot8/uniform | 0.40 | 0.72 | - | - |
| independent | bot4/uniform | 0.48 | 0.83 | +0.08 +- 0.09 | -0.01 +- 0.05 |
| independent | bot2/uniform | 0.35 | 0.62 | -0.06 +- 0.05 | -0.06 +- 0.03 |
| independent | bot1/uniform | 0.40 | 0.70 | -0.00 +- 0.04 | -0.00 +- 0.03 |
| independent | bot0/uniform | 0.51 | 1.01 | +0.11 +- 0.07 | +0.03 +- 0.04 |
| independent | bot4/greedy_a | 0.32 | 0.48 | -0.08 +- 0.04 | -0.02 +- 0.03 |
| independent | bot2/greedy_a | 0.39 | 0.71 | -0.01 +- 0.04 | -0.01 +- 0.03 |
| independent | joint12/greedy_a (6 + 6) | 0.17 | 0.22 | -0.23 +- 0.04 | -0.18 +- 0.06 |
| independent | joint16/greedy_a (8 + 8) | 0.17 | 0.25 | -0.24 +- 0.04 | -0.20 +- 0.06 |
| 0.8, 3 mm | bot8/uniform | 0.44 | 0.93 | - | - |
| 0.8, 3 mm | bot4/uniform | 0.46 | 0.78 | +0.02 +- 0.09 | -0.02 +- 0.05 |
| 0.8, 3 mm | bot2/uniform | 0.47 | 0.78 | +0.03 +- 0.08 | +0.02 +- 0.05 |
| 0.8, 3 mm | bot1/uniform | 0.39 | 0.54 | -0.04 +- 0.08 | +0.06 +- 0.06 |
| 0.8, 3 mm | bot0/uniform | 0.71 | 1.37 | +0.28 +- 0.17 | +0.16 +- 0.09 |
| 0.8, 3 mm | bot4/greedy_a | 0.34 | 0.58 | -0.09 +- 0.07 | +0.04 +- 0.06 |
| 0.8, 3 mm | bot2/greedy_a | 0.39 | 0.63 | -0.04 +- 0.07 | +0.05 +- 0.06 |
| 0.8, 3 mm | joint12/greedy_a (6 + 6) | 0.29 | 0.61 | -0.15 +- 0.04 | -0.07 +- 0.04 |
| 0.8, 3 mm | joint16/greedy_a (8 + 8) | 0.29 | 0.65 | -0.15 +- 0.04 | -0.08 +- 0.04 |

`bot1/greedy_a` places the same site as `bot1/uniform` (registration), so its row is that one and is not repeated.

## What it means

- On this stack the buried die can be reconstructed from the top die's sensors: with independent offsets, no
  buried sensor costs +0.11 +- 0.07 K, within the 0.25 K bar. Its peak error rises from 0.72 to 1.01 K.
- With die-wide correlated offsets, no buried sensor costs +0.28 +- 0.17 K on the buried die (above the bar's
  tolerance, though not gated) and +0.16 +- 0.09 K on the top die; on the buried die, one to four buried sensors
  cost at most +0.03 K (on the top die up to +0.06 K). That a buried sensor or two helps by sharing the offset
  burden is a reading of these numbers, not tested (exploratory).
- Placement matters more than count: 12 sites placed by the greedy (split 6 + 6) beat the 16-site uniform reference
  by 0.15-0.23 K on the buried die in both offset models. The greedy's buried sites lie inside the CPU die's active
  block (rows 23-36, columns 27-32, against the block's cells 20-39: `sites` in `dry/budget.json`, which the run
  checked equal), and TSV keep-outs may forbid that; untested.
- For the protocol: the Track R case set with no buried sensor is a fair task with independent offsets and a harder
  one with correlated offsets; Track P can start a buried die at 2 sensors.

**Not claimed.** One stack (G71), steady state, one sensor class, whole-die RMSE; the cost of a buried sensor (TSVs,
area) is not modelled.
