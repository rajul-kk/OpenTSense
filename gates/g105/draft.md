# G105 draft: spatially correlated sensor offsets (goal 17)

**Question.** Real offsets come partly from process variation, which is smooth across a die, so neighbouring sensors
share part of their offset. G102 and G86b drew every sensor's offset independently. Do the field model's lead over
the average (G102) and the joint calibration (G86b) survive offsets that are partly a smooth field?

**Why it is expected to hurt.** A smooth offset pattern looks like heat: the field model can explain it as a
temperature change, and `fault.offsets` drops patterns it cannot tell from heat (singular values below 1%), so such
offsets survive calibration and pass the leave-one-out check unseen.

## Method

- `estimate.sensor.Correlation`: each sensor's offset is sqrt(1 - share) x its independent draw + sqrt(share) x a
  zero-mean Gaussian field at its position, squared-exponential covariance of length `length_mm`, dies independent
  (separate wafers). The total 1-sigma offset stays the profile's. Without it the draws are G102's exactly:
  `tests/test_sensor.py` checks that `bench.readings.with_sensor` gives G102's case sets for `ring_osc`, `dts_1c`
  and `bjt_trimmed`.
- Same chip seed in every setting: the independent offset, gain and read noise come from the same stream (the
  smooth part is drawn from a child generator), so a chip is paired across settings; the independent part is
  scaled by sqrt(1 - share).
- Settings (share, length): independent; 0.5, 0.5 mm; 0.5, 1.5 mm; 0.8, 3 mm (the die is 3 mm, sensors about 1 mm
  apart). Values ASSUMED: the published within-die correlation lengths span about a millimetre to the die size;
  a source is to be graded before registration.
- G84's case set and sites, `ring_osc`, field model and average as G102, joint calibration on the cal split as G86b.
- Left after calibration: RMS of (estimated - true) fixed error per sensor, where the true fixed error on the cal
  split is the offset plus the gain error times (mean cal temperature - trim point), which calibration rightly
  absorbs.

## Dry run (chips 1-20, salt 105; `dry/corr.py`, `dry/corr.json`, 129 s)

RMSE in K, test split, mean over groups of the group median; mean over chips (min-max); difference from independent
offsets paired by chip, mean +- standard error:

| Offsets | Fixed error RMS | Left after calibration | Field model uncal, top / bottom | Calibrated, top / bottom | vs independent, uncal top / bottom | Beats average |
|---|---|---|---|---|---|---|
| independent | 1.05 K | 0.27 K (26%) | 0.29 (0.12-0.58) / 0.38 (0.20-0.74) | 0.29 / 0.34 | - | 20/20 chips, both dies |
| 0.5, 0.5 mm | 1.04 | 0.24 (23%) | 0.31 / 0.36 | 0.27 / 0.32 | +0.02 +- 0.03 / -0.02 +- 0.03 | 20/20 |
| 0.5, 1.5 mm | 1.06 | 0.27 (25%) | 0.35 / 0.41 | 0.30 / 0.34 | +0.06 +- 0.06 / +0.04 +- 0.04 | 20/20 |
| 0.8, 3 mm | 1.06 | 0.42 (40%) | 0.47 (0.20-1.09) / 0.51 (0.25-0.93) | 0.43 / 0.45 | +0.18 +- 0.07 / +0.13 +- 0.05 | 20/20 |

False alarms of the leave-one-out check (share of test cases with a sensor dropped), mean over chips (worst chip):
uncalibrated 3.4% (69%), 1.2% (24%), 4.6% (89%), 3.0% (60%); calibrated 0 in every chip and setting.

Seen:
- Correlation over a length shorter than the sensor spacing (0.5 mm, 1 mm spacing) changes nothing measurable; at
  1.5 mm the differences are within one standard error.
- A die-wide smooth offset (0.8, 3 mm) raises the field model's error by about 0.18 K (top) and 0.13 K (bottom),
  about half again the independent case, and calibration leaves 40% of the fixed error against 26%: the
  unidentifiable part that looks like heat. The calibrated difference stays (+0.13 / +0.11 K).
- The field model still beats the average (about 3 K) in all 20 chips, every setting, both dies.
- Uncalibrated false alarms come from chips with one large offset (up to 89% of cases in one chip); calibration
  removes them in every setting. The uncalibrated rates move with the setting (3.4% independent, 1.2% to 4.6%
  correlated) about as much as one chip changes them; no correlated setting raises them beyond that spread, and a
  smooth offset passes the check unseen rather than tripping it.
- The first dry runs (5 chips, `dry/corr_v1.json`, `dry/corr_v2_5chips.json`) suggested the die-wide setting
  tripled the error; that was chip-to-chip spread (and, in v1, a metric that counted gain error and unpaired read
  noise). Kept as run.

## Proposed bars (for the student; chips 21-30, unseen by the dry run, salt 105, setting 0.8 / 3 mm unless stated)

- (a) field model beats the average (bootstrap CI of RMSE difference below 0), both dies, in >= 8 of 10 chips.
- (b) the calibrated field model is no worse than the uncalibrated one by more than 0.1 K mean RMSE, both dies.
- Reported, not gated: RMSE and calibration residual per setting; false alarms.

## Lints checked

| Lint | What the design does |
|---|---|
| A4 like with like | settings share chip seeds, the independent stream and read noise (paired by chip); the same case set, sites and splits |
| A6 package logic | the correlation model is `estimate.sensor.Correlation`, readings `bench.readings`; the script only loops |
| A9 one source | settings, chips, salt and alpha are constants at the top of `dry/corr.py` |
| A10 cost | measured: 129 s for 4 settings x 20 chips |
| A14 append-only | dry output beside the code; the gated run writes `runs/main/` |
| A15 equivalence | moving G102's readings to the package reproduces G102's readings exactly (checked above) |
| A25 citations | every number above is from `dry/corr.json` |
| not applicable | A1-A3, A5, A11-A13, A16-A24 (no external tools, grids or long jobs) |
