# G107 draft: how few sensors the buried die needs (goal 21, item 3)

**Question.** A buried die's sensors are expensive: their readout must cross the bond through TSVs or bond pads, and
TSV area is scarce. The protocol (section 1.1) has a case set with no sensor on the buried die, and Track P gives
each die its own budget. How much does the field model lose on the buried die as its budget drops from 8 to 4, 2, 1
and 0 with the top die keeping 8? Does a placement chosen for the field model (A-optimal greedy) win the loss back?
And if the budget is not split per die, where would the field model put the sensors?

The cost of one buried-die sensor (TSV count, area) is not modelled here; the gate measures only the accuracy side.

## Method (dry, 20 Nov; `dry/budget.py`, `dry/budget.json`)

- G84's case set (G71 stack, two 3 x 3 mm dies, 60 x 60 cells; TPU die on top, CPU die buried under it). The top
  die keeps G84's 8 uniform sites in every set.
- Site sets, chosen from the train split only:
  - `bot8/uniform`: G84's sites, the reference;
  - `bot4/uniform`, `bot2/uniform`, `bot1/uniform`: `estimate.placement.uniform_grid` on the buried die;
  - `bot0/uniform`: no sensor on the buried die, which is estimated from the top die's 8 alone;
  - `bot4/greedy_a`, `bot2/greedy_a`, `bot1/greedy_a`: A-optimal greedy on the field model, the buried die's sites
    placed given the top die's;
  - `joint12/greedy_a`, `joint16/greedy_a`: 12 or 16 sites anywhere on either die, no per-die budget (reported).
- Readings: `ring_osc` profile, chips 1-5 (salt 107), independent offsets and G105's die-wide correlated offsets
  (share 0.8, length 3 mm). Each chip is read once at the union of all sets' sites, and each set takes its sensors
  from that read (`bench.readings.subset`, new), so sets differ only in which sites are read. Scored as G104:
  average and field model on the test split.
- Placement noise (the profile's total over the train temperatures of every cell): 1.064 K.
- Runs, kept as run: `dry/budget_v1.json` read each set as its own chip, which redraws every sensor's error, so two
  sets differed in their sensors' errors as well as their sites. `dry/budget.json` reads one chip per chip number.
  The top die's largest change between sets (independent offsets, chip 4, `bot2/uniform` against `bot8/uniform`)
  fell from 0.23 K to 0.17 K; the rest is the joint field model using the buried die's sensors for the top die too.
  `dry/budget_v2.json` is the same run before a no-op refactor of `bench.readings`; its runs, sites and noise equal
  `dry/budget.json`'s.

## Dry results (`dry/budget.json`)

Field-model RMSE in K over the whole die (test split, mean over groups of the group median), mean over chips 1-5
(min-max); peak error the same way; the difference from `bot8/uniform` is paired by chip, mean +- standard error
over the 5 chips. The average's RMSE is 3.21 K top, 2.98 K buried, the same in every set.

| Offsets | Site set | Buried die RMSE | Buried die peak error | vs bot8, buried | vs bot8, top |
|---|---|---|---|---|---|
| independent | bot8/uniform | 0.32 (0.23-0.45) | 0.48 | - | - |
| independent | bot4/uniform | 0.37 (0.26-0.49) | 0.61 | +0.05 +- 0.03 | +0.03 +- 0.02 |
| independent | bot2/uniform | 0.37 (0.25-0.57) | 0.58 | +0.05 +- 0.02 | +0.04 +- 0.04 |
| independent | bot1/uniform | 0.30 (0.22-0.40) | 0.39 | -0.02 +- 0.02 | +0.01 +- 0.02 |
| independent | bot0/uniform | 0.39 (0.23-0.75) | 0.61 | +0.06 +- 0.10 | +0.04 +- 0.04 |
| independent | bot4/greedy_a | 0.25 (0.13-0.42) | 0.39 | -0.08 +- 0.02 | +0.01 +- 0.02 |
| independent | bot2/greedy_a | 0.31 (0.21-0.51) | 0.43 | -0.01 +- 0.02 | +0.02 +- 0.02 |
| independent | joint12/greedy_a (6 + 6) | 0.20 (0.13-0.31) | 0.32 | -0.12 +- 0.06 | -0.10 +- 0.09 |
| independent | joint16/greedy_a (8 + 8) | 0.18 (0.11-0.31) | 0.35 | -0.14 +- 0.06 | -0.12 +- 0.08 |
| 0.8, 3 mm | bot8/uniform | 0.53 (0.33-0.80) | 0.76 | - | - |
| 0.8, 3 mm | bot4/uniform | 0.62 (0.34-1.13) | 1.00 | +0.09 +- 0.08 | +0.01 +- 0.04 |
| 0.8, 3 mm | bot2/uniform | 0.59 (0.37-1.17) | 0.81 | +0.07 +- 0.12 | +0.03 +- 0.08 |
| 0.8, 3 mm | bot1/uniform | 0.58 (0.38-1.05) | 0.64 | +0.06 +- 0.13 | +0.11 +- 0.10 |
| 0.8, 3 mm | bot0/uniform | 0.97 (0.30-2.01) | 1.90 | +0.44 +- 0.30 | +0.23 +- 0.14 |
| 0.8, 3 mm | bot4/greedy_a | 0.50 (0.34-0.81) | 0.66 | -0.03 +- 0.07 | +0.08 +- 0.09 |
| 0.8, 3 mm | bot2/greedy_a | 0.54 (0.41-0.86) | 0.60 | +0.02 +- 0.09 | +0.09 +- 0.09 |
| 0.8, 3 mm | joint12/greedy_a (6 + 6) | 0.37 (0.20-0.72) | 0.69 | -0.15 +- 0.03 | -0.18 +- 0.04 |
| 0.8, 3 mm | joint16/greedy_a (8 + 8) | 0.38 (0.20-0.72) | 0.74 | -0.15 +- 0.03 | -0.19 +- 0.04 |

`bot1/greedy_a` chose the same site as `bot1/uniform` (the die centre, cell 30, 30), so its row is the same and is
not repeated. The field model beats the average (bootstrap CI of the RMSE difference below 0) in 5 of 5 chips for
every set, both dies and both offset models, `bot0/uniform` included.

Seen:
- **With independent offsets the buried die hardly needs its own sensors.** From the top die's 8 alone, the buried
  die's error is 0.39 K against 0.32 K with its own 8 (+0.06 +- 0.10 K, not resolved), an eighth of the average's
  2.98 K. One centre sensor already matches 8 (-0.02 +- 0.02 K).
- **With die-wide correlated offsets, zero is not enough, but one or two are.** `bot0/uniform` loses 0.44 +- 0.30 K
  on the buried die and 0.23 +- 0.14 K on the top die (its 8 sensors now carry the shared offset alone), with peak
  error 1.90 K against 0.76 K. With 1, 2 or 4 buried sensors on a uniform grid the loss is +0.06 to +0.09 K (within
  about one standard error: +0.09 +- 0.08 K for 4), and greedy's 2 or 4 give -0.03 and +0.02 K.
- **Where the sensors go matters more than how many there are.** `joint12/greedy_a` (12 sites, which the greedy split
  6 and 6) beats the 16-site reference by 0.10-0.18 K on both dies in both offset models (resolved in three of the
  four cells; the top die with independent offsets, -0.10 +- 0.09 K, is not); `bot4/greedy_a` beats it
  on the buried die with independent offsets (-0.08 +- 0.02 K). Greedy's buried sites cluster at the die centre
  (rows 23-36, columns 27-32), inside the CPU die's 1 mm active block (cells 20-39). If TSVs cannot go there, the
  gain may not hold; that is G104's keep-out question on the buried die, not tested here.
- Unexplained: with independent offsets, `bot1/uniform` (-0.02 K) beats `bot2/uniform` and `bot4/uniform` (+0.05 K).
  The single site sits at the die centre, where the hot block is; the two- and four-site grids miss it. Not tested.
- Five chips resolve about 0.1 K with independent offsets and about 0.3 K with correlated ones (the standard errors
  above). The gate takes 10 chips per offset model, as G104.

## Proposed gate (chips 21-30, unseen by the dry run, salt 107; both offset models)

- (a) `bot0/uniform`: no worse than `bot8/uniform` on the buried die by more than 0.25 K mean RMSE over the 10
  chips, independent offsets (G104's tolerance). If it passes, the protocol's no-buried-sensor case set costs the
  field model little when offsets are independent. (Beating the average is not a bar: the dry run beats it by about
  2.7 K on every chip, so it could not fail.)
- (b) `bot2/uniform`: the same tolerance against `bot8/uniform` on the buried die, independent offsets. If it
  passes, Track P can give a buried die a quarter of the top die's budget.
- (c) `bot2/uniform`: the same tolerance, die-wide correlated offsets (dry +0.07 +- 0.12 K, not resolved at 5
  chips). If (a) holds and (c) holds, a buried die needs a couple of sensors only to share the offset burden.
- Reported, not gated: every set, both offset models, peak errors, the paired differences with their standard
  errors, the joint split, `bot0/uniform` under correlated offsets (dry +0.44 +- 0.30 K), and whether the field
  model beats the average in every set.
- Cost: setup 121-160 s (load, one field-model fit, five greedy placements), then 15-21 s for 100 scored runs
  (`setup_s`, `wall_s` in `dry/budget*.json`); the gate's 200 take minutes. Light class.

## What it feeds

- Protocol section 1.1: whether the Track R case set with no buried sensor stays, and with what budget Track P's
  buried die starts.
- Goal 21 item 3 closes with a verdict; G104's keep-out on the buried die is the natural follow-up.

## Lints checked

| Lint | What the design does |
|---|---|
| A4 like with like | the same case set, splits, chips and one chip read per chip number for every set (`readings.subset`); the top die's 8 sites are G84's in every per-die set; differences paired by chip |
| A6 package logic | sites from `estimate.placement` (uniform grid, greedy with start sites), readings and the new subset in `bench.readings`; the script picks budgets and loops |
| A9 one source | profile, chips, salt, budgets and offset models are constants at the top of `dry/budget.py`; G105's setting is copied by value and named |
| A10 cost | measured over the three dry runs: setup 121-160 s, 15-21 s for 100 scored runs (`setup_s`, `wall_s` in `dry/budget*.json`) |
| A17 resume | `budget.json` is rewritten after each chip under a key of the settings and input hashes; a rerun skips finished chips and refuses other placed sites |
| A1 every state | the zero-sensor die is its own set, `per_die_count` records [8, 0]; the field model conditions the joint field, the average ignores readings, so both are defined there |
| A14 append-only | the first dry run is kept as `dry/budget_v1.json`; the gated run will write `runs/main/` |
| A25 citations | every number above is from `dry/budget.json` or, where named, `dry/budget_v1.json` |
| not applicable | A2, A3, A5, A11-A13, A15, A16, A18-A24 (no external tools, grids or long jobs) |
