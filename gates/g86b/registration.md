# G86b registration (written 19 Nov 2026, after the dry runs, before the gated run)

The history is in `draft.md`. The draft left its bars to the student; the student delegated open choices on 18 Nov
("no questions just do what youd recommend as id pick that option either way"), so the draft's proposed bars are taken
as they stand, marked *(delegated)*.

### G86b: Does a per-chip offset calibration stop G86's false alarms without hiding faults? (RQ3) · REGISTERED

- **Why.** G86 (FAIL on (c)) dropped a healthy sensor in 68 of 80 test cases on chip 12, whose drawn offset was
  +2.69 K (2.7 sigma of the ring-oscillator profile). A threshold set from the noise model cannot tell a large fixed
  offset from a fault, so each chip's offsets are calibrated first.
- **Cases, sensors, estimator, check.** As G86, from its `run.py` (imported, unchanged): G84's case set rebuilt by
  `../g84/make_cases.py`, its sha256 equal to G84's (f5941ad7...); `ring_osc` readings through G102's
  `readings.with_sensor`; the field model `GaussianField(energy=0.9999)` fitted once on train; the average is the
  train-split mean field; the check is `fault.repair` at `fault.threshold(0.01, 16)` (3.4205). **Gated chips: seeds
  16 to 25**, never drawn before (G86's dry run used 1 to 5, its gated run 6 to 15).
- **Calibration.** On each chip's cal split (80 cases, programs in neither train nor test), the offsets are
  `opentsense.estimate.fault.offsets`: each sensor's mean leave-one-out residual, with the leak of one sensor's
  offset into its neighbours' predictions removed by solving (I - W) o = residual (singular values below 1% of the
  largest dropped). No true temperature is read. The offsets are subtracted from every test reading. Faults start
  after calibration: they are injected on the test split only.
- **Conditions per chip.** Healthy; each of the 16 sensors in turn shifted +2.7 K in cal and test (an in-spec
  outlier like chip 12's; its offsets re-calibrated with the shift); each sensor in turn failing on test: stuck at
  ambient (zero rise), frozen at its train-split mean reading, drift +1 K and +2 K.
- **Statistic.** As G86: per die, the group-bootstrap 95% interval of (checked estimate - average) RMSE, mean over
  programs of the group median, 10,000 resamples, seed 0 (`opentsense.bench.metrics.bootstrap_diff`).
- **Pass if all hold** *(delegated)*:
  - **(a)** Healthy chips, calibrated: a sensor is dropped in at most 1% of all test cases over the 10 chips (G86's
    failed bar).
  - **(b)** Each sensor in turn +2.7 K, calibrated: a sensor is dropped in at most 1% of all test cases over the
    160 (chip, sensor) pairs.
  - **(c)** Stuck at ambient, calibrated: the faulty sensor is the one dropped in at least 99% of all test cases over
    the 160 pairs, and the interval lies below 0 in at least 95% of pairs, for each die separately.
  - **(d)** Frozen, calibrated: the interval lies below 0 in at least 95% of pairs, for each die separately.
- **Validity (INCONCLUSIVE otherwise).** The case set's sha256 equals G84's before scoring; the code's sha256
  (`run.py`, `evaluate.py`, this file and G86's inputs) is unchanged from start to end of the run; the threshold
  equals 3.4205 (checked in `evaluate.py`, which G86's did not check); profile `ring_osc`, outlier 2.7 K, 80 test
  cases; chips 16 to 25 each with 16 sensors and every condition present.
- **Reported, not gated.** Detection shares of every fault; checked RMSE mean and worst per fault; the healthy false
  alarms without calibration (on the same chips); the healthy field model's RMSE calibrated and checked against
  uncalibrated and unchecked; the largest estimated offset per chip.
- **A fail means.** (a) or (b): calibration on 80 cases does not take out a large fixed offset; (c) or (d):
  calibration absorbs part of what the check needs to see a fault.
- **Not claimed.** Faults present during calibration (a sensor dead from power-on would be folded into its offset);
  drift detection (a single-snapshot statistic cannot see it at these sizes; reported only); other sensor profiles.

### Dry runs (chips 1 to 5; `draft.md`, `dry/`)

| Chips 1-5, calibrated | `dry/calib.json` (plain mean residual) | `dry/calib_lstsq.json` (`fault.offsets`, as gated) |
|---|---|---|
| Healthy false alarms | 0% on every chip | 0% on every chip |
| +2.7 K outlier false alarms, mean over sensors | 0% | 0% |
| Stuck at ambient detected | 100% | 100% |
| Frozen detected | 34.9% to 35.4% | 35.1% to 35.3% |
| Largest estimated offset per chip | 1.45 to 2.91 K | 1.39 to 2.87 K |

The two estimates differ by up to 1.39 K on a sensor (chip 3) but give the same detection shares on these chips.

### Code and output

`run.py` (scores per chip), `evaluate.py` (bars, validity, `<run dir>/result.json`); run
`python gates/g86b/run.py gates/g86b/runs/main`, then `python gates/g86b/evaluate.py gates/g86b/runs/main` and
`python scripts/record_gate.py g86b`.

Lints checked: A4 (one population: G84's case set and splits, as G86), A9 (G86's constants imported from its
`run.py`, the threshold from `fault.threshold`), A14 (G86 stays as recorded; new gate, new chips), A16 (per chip, one
chip's failure stops the run but nothing is recorded partially), A25 (every number above cites its file).

Amendments go below, dated, each with the reason. Never re-run until it passes.
