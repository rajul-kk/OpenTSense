# G86 draft (17 Nov 2026): one failed sensor · DRAFT, not registered; the bars below are proposals for the student

### G86: Does the field estimate survive one failed sensor, and does a self-check find it? (RQ3)

- **Why.** G102 showed the estimator ranking survives realistic sensor error (offset, gain, quantisation). A sensor
  can also fail outright: dead, stuck at one code, or drifting. With 8 sensors per die, one failure is an eighth of
  the information on that die.
- **Scope after G102.** G86's original list was noise, quantisation, representativeness and failure. Noise and
  quantisation are G102's (PASS); representativeness is G76's. G86 keeps failure only.
- **Cases and sensors.** G84's case set (sha256 f5941ad7...), G102's `ring_osc` profile (the middle published
  class; offset sigma 1.0 K, gain 1%, 0.25 K codes) through `gates/g102/readings.py`. Field model as G84 and G102
  (GaussianField, energy 0.9999, train split). One sensor fails per chip, each of the 16 in turn, in every test case.
- **Faults.** dead and known (left out); stuck at ambient (zero rise); frozen at its own train-split mean reading;
  drift +1 K and +2 K. Unknown faults are scored twice: unchecked, and checked by `opentsense.estimate.fault.repair`
  (each sensor predicted from the other 15 by the field model; the worst one is dropped when its |z| exceeds the
  two-sided Bonferroni threshold for alpha = 0.01 over 16 sensors, 3.42; fixed from the model, not from data).
- **Dry run (chips 1-5, `dry/floor.json`, `dry/faults.json`; RMSE mean group-median over chips and sensors, top /
  buried die):**

| Fault | Unchecked | Checked | Field below average (interval) | Faulty sensor dropped |
|---|---|---|---|---|
| none (healthy) | 0.26 / 0.29 K | same | 5 / 5 chips | 0% of cases (false alarms) |
| dead, known | 0.26 / 0.30 K (worst 0.66) | n/a | 80 / 80 pairs | n/a |
| stuck at ambient | 1.80 / 1.78 K (worst 10.5) | 0.26 / 0.30 K (worst 0.66) | 75, 70 -> 80, 80 / 80 | 100% |
| frozen | 0.37 / 0.36 K (worst 1.81) | 0.27 / 0.30 K (worst 0.65) | 80 / 80 both | 36% (min 24%) |
| drift +2 K | 0.27 / 0.35 K | same | 80 / 80 | 3% |
| drift +1 K | 0.26 / 0.32 K | same | 80 / 80 | 0% |

  Drift up to 2 K is not found and does little harm: the estimators are told the profile's total error (about 1 K),
  so a 2 K offset reads as two sigma. A frozen sensor is dropped only in the cases where its value is far off, which
  are the cases it would spoil.
- **Proposed bars (gated chips 6-15, unseen; G102's interval test, 10,000 resamples):**
  - **(a) A known dead sensor costs little:** in at least 95% of (chip, sensor) pairs, both dies, the interval of
    field_model (15 sensors) - average lies below 0.
  - **(b) The check removes a stuck sensor:** stuck at ambient, the faulty sensor is dropped in at least 99% of test
    cases over all pairs, and the checked field_model's interval lies below the average's in at least 95% of pairs,
    both dies.
  - **(c) The check does not invent faults:** on the healthy chips, at most 1% of test cases have a sensor dropped.
  - **(d) A frozen sensor does not spoil the estimate once checked:** the checked field_model's interval below the
    average's in at least 95% of pairs, both dies.
- **Reported, not gated.** RMSE and peak error per fault, unchecked and checked; detection shares; drift faults.
- **A fail means.** (a): the layout has no redundancy, so one dead sensor blinds part of a die; (b) or (d): the
  single-fault check is not enough; (c): the check's threshold is wrong for real sensor error (offsets are not
  Gaussian across sensors), so it needs calibrating on the cal split.
- **Not claimed.** One stack, steady state, 8 sensors per die, one fault at a time, faults lasting the whole test
  split; no intermittent faults, no two faults.
- **Lints checked:** A4 (both dies and all faults scored on the same test cases), A6 (the check is package code with
  tests, `tests/test_fault.py`), A14 (dry outputs kept; floor.py kept as run, faults.py beside it), A25 (every number
  above is in `dry/floor.json` or `dry/faults.json`, printed by `dry/summarise.py` and `dry/faults.py`).
