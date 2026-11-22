# G104 draft: sensors only outside the dense logic (goal 16)

**Question.** G84 and G102 put sensors on a regular grid over the whole die, including the dense logic block. Real
designs often cannot place a sensor inside a dense block (no whitespace, routing blockage). How much does the field
model lose when every sensor sits outside the block, and does a placement chosen for the field model (A-optimal
greedy) win back the loss?

## Method (dry, 17-18 Nov; `dry/sites.py`, `dry/sites.json`)

- G84's case set (G71 stack, two 3 x 3 mm dies, 60 x 60 cells; the 1 mm active block of each die at cells 20-39,
  `gates/g71/inputs/maps.npz` act3). 8 sensors per die in every set.
- Site sets, chosen from the train split only:
  - `all/uniform`: G84's sites (checked equal), the reference;
  - `outside/uniform`: the smallest regular grid with 8 points outside the block and a 2-cell ring around it (here
    the 3 x 3 grid minus its centre);
  - `all/greedy_a`, `outside/greedy_a`: A-optimal greedy on the field model of the train fields
    (`estimate.placement.greedy_a`), die by die, the second die's sites placed given the first's.
- Readings: `ring_osc` profile, chips 1-5 (salt 104), with independent offsets and with G105's die-wide correlated
  offsets (share 0.8, length 3 mm). Scored as G102: average and field model on the test split.
- Placement noise (the profile's total over the train temperatures of the allowed cells): 1.064 K all, 1.070 K
  outside, so the two masks see the same noise.
- Runs, kept as run: `dry/sites_v1.json` (first; fewer input hashes, no average RMSE), `dry/sites_v2.json` (review
  round 1: more inputs hashed, the average recorded, a write after each chip), `dry/sites.json` (round 2: the field
  model fitted once, peak error recorded, the stack config hashed; `dry/sites_v3.json` is the same before round 3
  added the setup time and the fit checks). All give the same sites and the same field-model results to the last
  digit.

## Dry results

Field-model RMSE in K over the whole die (test split, mean over groups of the group median), mean over chips 1-5 (min-max); the
difference from `all/uniform` is paired by chip, mean +- standard error over the 5 chips:

| Offsets | Site set | Top | Bottom | vs all/uniform, top | vs all/uniform, bottom |
|---|---|---|---|---|---|
| independent | all/uniform | 0.24 (0.12-0.32) | 0.27 (0.22-0.35) | - | - |
| independent | outside/uniform | 0.33 (0.20-0.52) | 0.35 (0.27-0.49) | +0.09 +- 0.05 | +0.08 +- 0.04 |
| independent | all/greedy_a | 0.19 (0.11-0.34) | 0.20 (0.12-0.27) | -0.05 +- 0.05 | -0.07 +- 0.03 |
| independent | outside/greedy_a | 0.24 (0.13-0.33) | 0.30 (0.22-0.41) | -0.00 +- 0.03 | +0.03 +- 0.04 |
| 0.8, 3 mm | all/uniform | 0.48 (0.17-0.72) | 0.57 (0.24-1.02) | - | - |
| 0.8, 3 mm | outside/uniform | 0.66 (0.15-1.16) | 0.73 (0.30-1.42) | +0.19 +- 0.10 | +0.16 +- 0.08 |
| 0.8, 3 mm | all/greedy_a | 0.44 (0.24-0.68) | 0.55 (0.34-0.74) | -0.04 +- 0.12 | -0.02 +- 0.11 |
| 0.8, 3 mm | outside/greedy_a | 0.62 (0.37-0.99) | 0.89 (0.59-1.15) | +0.14 +- 0.14 | +0.32 +- 0.09 |

The field model beats the average (bootstrap CI of the RMSE difference below 0)
in 5 of 5 chips for every set, both dies and both offset models; the average's own RMSE is 3.0-3.2 K.

Seen:
- **Sensors outside the block still give a good whole-die map.** With 8 sensors around the block, the field model's
  whole-die error stays at a tenth (independent offsets) to a third (correlated) of the average's 3.0-3.2 K, and its
  peak error (mean over groups of the group median) is 0.2-1.2 K with independent offsets and
  0.4-4.2 K with correlated ones, over every set and chip. The block and its ring are about 16% of the die, so the whole-die figure can hide a larger
  error inside the block; the block's own error is not recorded. Moving the uniform grid out of the block costs
  about 0.08-0.09 K with independent offsets and 0.16-0.19 K with die-wide correlated ones (about two standard
  errors in each case).
- **Greedy placement outside the block wins that loss back while offsets are independent** (-0.00 / +0.03 K
  against `all/uniform`, within one standard error), but not with correlated offsets: on the bottom die it is
  0.32 +- 0.09 K worse, the clearest difference in the table (the top die, +0.14 +- 0.14 K, is not resolved). Its
  sites sit at the block's edge in two short rows (rows 17 and 42, columns 28-32 on the top die and 27-32 on the
  bottom; `sites` in `dry/sites.json`). Clustering alone does not explain the loss: `all/greedy_a` is clustered too
  (columns 28-30 on the top die) and is the best set under correlated offsets. The cause is not known.
- Greedy on the whole die is the best set in both offset models, but not resolved: -0.05 / -0.07 K with
  independent offsets (one to two standard errors), -0.04 / -0.02 K with correlated ones (under a third of one).
- Five chips resolve differences of about 0.1 K with independent offsets and about 0.25 K with correlated ones (code
  lint L57; G105's 5-chip run misled at this size). The gate below takes 10 chips per offset model.

## Proposed gate (for the student; chips 21-30, unseen by the dry run, salt 104; both offset models)

- (a) `outside/uniform`: the field model beats the average (CI below 0), both dies, in >= 8 of 10 chips, in both
  offset models.
- (b) `outside/uniform` is no worse than `all/uniform` by more than 0.25 K mean RMSE over the 10 chips, both dies,
  independent offsets.
- Reported, not gated: every set and offset model, and the paired differences with their standard errors; whether
  `outside/greedy_a` loses to `outside/uniform` under correlated offsets.
- Cost: about 70 s of setup and well under a second per scored set and chip, so the gate's 80 take minutes.

## Lints checked

| Lint | What the design does |
|---|---|
| A4 like with like | every set has 8 sensors per die (`per_die_count`), the same case set, splits, chips and readings stream; differences paired by chip |
| A6 package logic | placement in `estimate.placement` (greedy start sites, uniform grid refusing too few cells), readings in `bench.readings`; the script picks masks and loops |
| A9 one source | profile, chips, salt, ring and the offset models are constants at the top of `dry/sites.py`; G105's setting is copied by value and named |
| A10 cost | measured (`dry/sites.json`): setup (load, one field-model fit, placement) 68.4 s, then 5.3 s for 40 scored runs; the first run refitted each time, 3,971 s (`dry/sites_v1.json`) |
| A17 resume | `sites.json` is rewritten after each chip under a key of the settings and input hashes; a rerun skips finished chips |
| A14 append-only | dry output beside the code; the gated run writes `runs/main/` |
| A15 equivalence | `all/uniform` is checked equal to G84's sites before the fit; fitting the field model once gives the first run's results exactly (`dry/sites_v1.json`) |
| A25 citations | every number above is from `dry/sites.json` |
| not applicable | A1-A3, A5, A11-A13, A16-A24 (no external tools, grids or long jobs) |
