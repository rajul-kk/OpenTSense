# G102 registration (written 16 Nov 2026, after a dry run, before the gated run)

### G102: Does the estimator ranking survive a realistic sensor? (O2, RQ3; goals.md 12) · REGISTERED

- **Why.** Every estimation result so far reads each sensor as its cell's exact temperature plus N(0, 0.1 K). Real
  on-die sensors have a fixed offset and gain error per sensor and a quantised code. Draft: `draft.md`.
- **Sensor model.** `opentsense/estimate/sensor.py` (tested): reading = quantise(T + offset + gain (T - 358.15 K) +
  noise), offset and gain drawn once per sensor per chip. Profiles graded from published sensors (module docstring):
  `bjt_trimmed` (offset sigma 0.13 K, gain 0.1%, 0.0625 K codes, noise 0.02 K), `ring_osc` (1.0 K, 1%, 0.25 K,
  0.1 K), `dts_1c` (2.0 K, 2%, 1 K, 0.1 K), `ideal_gauss` (G84's model). Steady cases: the sample period does not
  enter.
- **Cases.** G84's case set rebuilt by `../g84/make_cases.py`; its sha256 must equal G84's record
  (f5941ad74a0d62f2...). Readings replaced per profile and chip (`readings.py`): every case of a chip, at 300 K +
  rise; `noise_K` given to the estimators = the profile's datasheet total, sqrt(offset^2 + (gain x rms |T -
  358.15 K|)^2 + step^2/12 + noise^2) over the train split's sensor temperatures (`sensor.Profile.total_sigma`);
  the gain term comes on top of the cited figure (conservative). Ambient from the stack config (300 K). **Gated chips: seeds 6 to 15**
  (10 chips per profile), none of them seen; the dry run used chips 1 to 5.
- **Scoring.** G84's estimators (`average`, `field_model`, `bayes_power`, `inverted`), `opentsense.bench.score` as G84:
  test split, group-median RMSE per program, group bootstrap of the difference against `average`, 10,000 resamples,
  seed 0.
- **Noise floor (dry run, `dry/floor.json`, chips 1-5, 2,000 resamples).** Chip-to-chip range of field_model's mean
  group-median RMSE (top / buried die): ideal 0.00 / 0.01 K, bjt_trimmed 0.13 / 0.09, ring_osc 0.65 / 0.46, dts_1c
  0.78 / 0.41. The bars are sign tests on bootstrap intervals (plan.md 2.1 option ii), counted over chips.
- **Pass if all hold:**
  - **(a) The field estimate still beats the floor estimator:** for `bjt_trimmed` and for `ring_osc`, on both dies, in
    at least 8 of the 10 chips, the 95% interval of `field_model` - `average` RMSE lies below 0.
  - **(b) The wrong estimator is still caught:** for `bjt_trimmed`, `ring_osc` and `dts_1c`, every chip, both dies,
    the 95% interval of `inverted` - `average` RMSE lies above 0 (G84 (c)).
- **Validity (INCONCLUSIVE).** The rebuilt case set's sha256 equals G84's record (checked before scoring), the scored
  chips are 6 to 15 and all four profiles are present.
- **What this gate can and cannot show (from review, 16 Nov).** Both bars compare against `average` (about 3 K
  RMSE), so they test whether the ranking holds: field estimation still beats the training mean and a wrong estimator
  is still caught. They cannot show that a profile leaves the estimates accurate enough: a profile that makes
  field_model several times worse can still pass. That is **reported, not gated**: the ratio of each estimator's
  RMSE and peak error to its `ideal_gauss` value, per profile, and every estimation result states the sensor model it
  assumes. No accuracy bar is set here because none was fixed before the dry run was seen.
- **Reported, not gated.** Mean RMSE and peak error over chips per profile, estimator and die; their ratio to
  `ideal_gauss`; `dts_1c` against (a); `bayes_power` against `average` (chips with the interval below 0).
- **A fail means.** (a) fails for `bjt_trimmed`: under trimmed BJT-class sensors the field estimate is no better than
  the training mean, so the estimation results need near-ideal sensors and must say so. For `ring_osc` only: the
  ranking holds for trimmed BJT-class sensors, not oscillator sensors; offset calibration on the cal split is the
  next step (not in this gate). (b) fails: a wrong estimator hides behind sensor
  error, and the scorer cannot rank under it.
- **Not claimed.** One stack, steady state, one layout of 8 sensors per die; profiles stand for published sensor
  classes, not a product; no self-heating or supply sensitivity.
- **Disclosed from the dry run (chips 1-5).** Mean field_model RMSE top / buried: ideal 0.06 / 0.09 K, bjt_trimmed
  0.08 / 0.11, ring_osc 0.39 / 0.36, dts_1c 0.46 / 0.48; average 3.21 / 2.98 K; field_model below average in 5 of 5
  chips for every profile and die; inverted above average throughout. The bars were proposed in `draft.md` before the
  dry run and are unchanged except the chip count (5 -> 10) and the held-out chip seeds. After the dry run, review
  changed what the estimators are told (`noise_K` now includes the gain term) and keyed each profile's generator by
  its name; the dry run used the earlier `readings.py` (kept as run in git history only through this note).
- **Code and output.** `readings.py`, `run.py`, `evaluate.py` here; output in `runs/main/`.

Amendments go below, dated, each with the reason. Never re-run until it passes.
