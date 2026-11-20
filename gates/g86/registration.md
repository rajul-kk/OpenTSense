# G86 registration (written 17 Nov 2026, after the dry run, before the gated run)

### G86: Does the field estimate survive one failed sensor, and does a self-check find it? (RQ3) · REGISTERED

- **Why and scope.** G102 (PASS) covered sensor noise, offset, gain and quantisation; representativeness was G76,
  dropped by the student on 17 Nov (G56, exploratory, quoted instead). G86 keeps sensor failure. Draft and dry run:
  `draft.md`, `dry/floor.json`, `dry/faults.json`. Bars accepted by the student on 17 Nov as proposed in the draft.
- **Cases and sensors.** G84's case set rebuilt by `../g84/make_cases.py`; its sha256 must equal G84's record
  (f5941ad7...). Readings from G102's `ring_osc` profile through `../g102/readings.py` (offset sigma 1.0 K, gain 1%,
  0.25 K codes, noise 0.1 K; estimators told the profile's datasheet total). **Gated chips: seeds 6 to 15**; the dry
  run used 1 to 5.
- **Estimator.** G84's field model: `GaussianField(energy=0.9999)` fitted once on the train split (the fit does not
  read the readings). Average: the train-split mean field. Test split.
- **Faults.** Each of the 16 sensors in turn fails in every test case of a chip (160 (chip, sensor) pairs):
  dead (known, left out); stuck at ambient (zero rise); frozen at its own train-split mean reading; drift +1 K and
  +2 K. Unknown faults are scored unchecked and checked by `opentsense.estimate.fault.repair` at
  `fault.threshold(0.01, 16)` (3.42; fixed from the model).
- **Statistic.** Per die, the group-bootstrap 95% interval of (estimate - average) RMSE, mean over programs of the
  group median, 10,000 resamples, seed 0 (`opentsense.bench.metrics.bootstrap_diff`, as G102).
- **Pass if all hold (each die separately):**
  - **(a)** dead, known: the interval lies below 0 in at least 95% of the 160 pairs.
  - **(b)** stuck at ambient, checked: the faulty sensor is the one dropped in at least 99% of all test cases over
    the 160 pairs, and the interval lies below 0 in at least 95% of pairs.
  - **(c)** healthy chips, checked: a sensor is dropped in at most 1% of all test cases over the 10 chips.
  - **(d)** frozen, checked: the interval lies below 0 in at least 95% of pairs.
- **Validity (INCONCLUSIVE).** The case set's sha256 equals G84's before scoring; the code's sha256 is unchanged
  from start to end of the run; chips 6 to 15 and all faults present.
- **Reported, not gated.** Mean and worst RMSE per fault, unchecked and checked; detection shares; the drift faults.
- **A fail means.** (a): one dead sensor blinds part of a die in this layout; (b) or (d): the single-fault check is
  not enough; (c): the threshold does not fit real sensor error and needs calibrating on the cal split.
- **Not claimed.** One stack, steady state, 8 sensors per die, one fault at a time, lasting the whole test split.
- **Code and output.** `run.py` (writes `runs/main/`), `evaluate.py` (writes `record/result.json`).

Amendments go below, dated, each with the reason. Never re-run until it passes.
