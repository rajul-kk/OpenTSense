# G105 registration (written 18 Nov 2026, after the dry run, before the gated run)

### G105: Do the field model's lead and the joint calibration survive spatially correlated sensor offsets? (O2, RQ3; goals.md 17) · REGISTERED

- **Why.** Real offsets come partly from process variation, which is smooth across a die, so neighbouring sensors
  share part of their offset. G102 and G86b drew every offset independently. A smooth offset pattern looks like heat,
  so the field model can mistake it for a temperature change and the joint calibration cannot identify it. Draft:
  `draft.md`.
- **Offset model.** `estimate.sensor.Correlation` (tested): each sensor's offset is sqrt(1 - share) x its independent
  draw + sqrt(share) x a zero-mean squared-exponential Gaussian field at its position (length `length_mm`), dies
  independent, total 1-sigma offset unchanged. The smooth part comes from a child generator, so a chip's independent
  offset, gain and read noise are the same in every setting (paired by chip). Settings (share, length): independent;
  0.5, 0.5 mm; 0.5, 1.5 mm; 0.8, 3 mm. Values ASSUMED (published within-die correlation lengths span about a
  millimetre to the die size); the gate is on the strongest, **0.8, 3 mm**.
- **Cases.** G84's case set rebuilt by `../g84/make_cases.py`; its sha256 must equal G84's record (f5941ad7...).
  G84's sites, `ring_osc` profile (G102), readings by `bench.readings.read_chip` with salt 105. **Gated chips: seeds
  21 to 30**, none seen (the dry run used 1 to 20).
- **Scoring.** As `dry/corr.py`: field model (GaussianField, energy 0.9999, on the train fields) and the training
  mean, test split, group-median RMSE per die averaged over groups; group bootstrap of field model - average, 10,000
  resamples. Calibrated = readings minus `fault.offsets` fitted on the cal split. Code: `run.py`, `evaluate.py`.
- **Pass if both hold (setting 0.8, 3 mm):**
  - **(a) The field model still beats the average:** uncalibrated, on both dies, in at least 8 of the 10 chips the
    95% interval of field model - average RMSE lies below 0.
  - **(b) Calibration does not hurt:** on both dies, the calibrated field model's mean RMSE over the 10 chips is no
    more than 0.1 K above the uncalibrated one's.
- **Validity (INCONCLUSIVE).** The rebuilt case set's sha256 equals G84's, the scored chips are 21 to 30, and all four
  settings are present for every chip.
- **Reported, not gated.** Per setting: mean RMSE uncalibrated and calibrated; chips below the average; the paired
  difference from independent offsets (mean +- standard error over chips); the fixed-error RMS and the part left after
  calibration; false alarms of the leave-one-out check.
- **A fail means.** (a): under a die-wide smooth offset the field estimate is no better than the training mean, so
  every estimation result must state that it assumes independent offsets. (b): the joint calibration makes estimates
  worse when offsets are smooth, so it must not be applied without a correlation check.
- **Not claimed.** One stack, steady state, one layout of 8 sensors per die, one sensor class; the correlation
  settings are assumed, not measured.
- **Disclosed from the dry run (chips 1-20, `dry/corr.json`).** At 0.8, 3 mm: field model 0.47 / 0.51 K uncalibrated,
  0.43 / 0.45 K calibrated (top / bottom), +0.18 +- 0.07 / +0.13 +- 0.05 K above independent offsets; below the
  average in 20 of 20 chips in every setting; calibration leaves 40% of the fixed error (26% independent). The 5-chip
  runs (`dry/corr_v1.json`, `dry/corr_v2_5chips.json`) are kept as run. The bars are the draft's, unchanged.
- **Who fixed the bars.** The student delegated the choice (18 Nov: "no questions just do what youd recommend as id
  pick that option either way"); these are the draft's proposed bars, fixed before any gated chip was drawn.

Amendments go below, dated, each with the reason. Never re-run until it passes.
