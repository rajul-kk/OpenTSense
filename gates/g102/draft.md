# G102 draft (written 16 Nov 2026; NOT registered: bars below are proposals, fixed after the dry run measures the floor)

### G102: Do the estimation results survive a realistic sensor? (O2, RQ3; goals.md 12) · DRAFT

- **Why.** Every estimation result so far reads each sensor as its cell's exact temperature plus N(0, 0.1 K) (G84 and
  the case sets). Real on-die sensors have a fixed offset and gain error per sensor, a quantised code and a sample
  period. If the field estimators only beat the training mean because the readings are near-perfect, the thesis
  claim does not hold for a real chip.
- **Sensor model.** `opentsense/estimate/sensor.py`: reading = quantise(T + offset + gain (T - 358.15 K) + noise).
  Offset and gain are drawn once per sensor per chip and held for every case of that chip. Profiles, graded from
  published sensors (module docstring): `bjt_trimmed` (sigma 0.13 K, 0.0625 K codes), `ring_osc` (1.0 K, 0.25 K
  codes), `dts_1c` (2.0 K, 1 K register), and `ideal_gauss` (G84's model). The sample period does not enter a steady
  case set; it is in the model for the transient work after G94.
- **Cases.** G84's frozen case set, rebuilt by `../g84/make_cases.py` (its sha256 must equal G84's record,
  f5941ad7...; validity), absolute temperature = 300 K + rise. Only the readings are replaced: per profile, C chips
  (chip seeds 1..C), every case of a chip read with that chip's sensors. `noise_K` given to the estimators is the
  profile's datasheet total, sqrt(offset^2 + step^2 / 12 + noise^2), as a user would enter it.
- **Estimators.** G84's four: `average`, `field_model`, `bayes_power`, `inverted`; scored by `opentsense.bench.score`
  exactly as G84 (test split, group-median RMSE per program, group bootstrap, 10,000 resamples, seed 0).
- **Noise floor (dry run, before the bars).** The spread over chips of each estimator's mean group-median RMSE per die
  and profile; C = 5 proposed.
- **Pass if all hold (proposed):**
  - **(a) The field estimate still beats the floor estimator:** for `bjt_trimmed` and `ring_osc`, on both dies, in at
    least 4 of 5 chips, the 95% bootstrap interval of `field_model` - `average` RMSE lies below 0.
  - **(b) The wrong estimator is still caught:** as G84 (c), `inverted` - `average` above 0, every realistic profile,
    every chip, both dies.
- **Reported, not gated:** every profile's RMSE and peak error per estimator against `ideal_gauss`; `dts_1c` against
  (a) (expected to be hard: a 1 K register and 2 K offsets against rises of 12 to 67 K); how much of the loss is
  offset, quantisation or gain (one term on at a time, one chip).
- **A fail means:** (a) fails for `bjt_trimmed`: the estimation results need near-ideal sensors, and every result
  must state that; for `ring_osc` only: results hold for trimmed BJT-class sensors, not for oscillator sensors. The
  next step would be offset calibration on the cal split (not in this gate).
- **Not claimed:** one stack, steady state, one sensor layout (8 per die); profiles are representative of published
  sensor classes, not of a product; no sensor self-heating or supply sensitivity.
- **Effort:** half a day after the sensor model (done, tested): readings and scoring are seconds per profile and chip.
