# G106 registration (written 18 Nov 2026, after the dry runs, before the gated run)

### G106: Does G102's ranking survive sensors simulated as circuits? (O2, RQ3; goals.md 18) · REGISTERED

- **Why.** G102's sensor profiles are datasheet classes. A sensor built from our own cells, trimmed as a real chip
  is, has an error set by its process corner and its supply. Draft: `draft.md` (SPICE sweep and derived errors).
- **Sensor model.** `estimate.sensor_circuit` (tested): reading = quantise(T + error_corner(T) + droop_corner x
  squeeze + noise). Each chip is one corner, TT, SS or FF with equal odds (ASSUMED); `error_corner(T)` is the
  one-point-trimmed error from `dry/derive.json` (SPICE, `dry/sweep.json`), linear between the swept temperatures;
  droop is the linearised K per mV at 85 C; readout step 0.25 K and noise 0.1 K (G102's ring_osc, ASSUMED). The
  estimators are told the profile's total over the train split. Readings by `bench.readings.read_circuit`.
- **Cases.** G84's case set rebuilt by `../g84/make_cases.py` (sha256 must equal G84's, f5941ad7...), G84's sites,
  salt 106. **Gated chips: seeds 21 to 30**, none seen (the dry run used 1 to 5).
- **Profiles** (`run.py`): `asap7_ring/regulated` (gated); reported: `asap7_ring/core_g97` (the sensor on the core
  supply, squeeze from G97's tile maps: top die the case's TPU window, bottom die Ibex's k0-k4 mean, resampled onto
  G71's 1 mm active block; outside the block 0), `asap7_ring/core_scaled` (that squeeze times G84's power density
  over G97's, per TPU window on the top die: 3.35 W1, 3.28 W2, 3.06 W3; 1.57 on the bottom; G84's nominal block
  densities, not each case's own, which vary with the program; ASSUMED proportional),
  `ihp_ring/regulated`, `ihp_dvbe/one_point`, `ihp_dvbe/two_point`. Cases of one sensor share its generator (the
  three ASAP7 cases; the two dVBE trims), so they draw the same corner and read noise per chip.
- **Scoring.** As G102: average and field model (fitted once on the train fields), test split, group-median RMSE per
  die averaged over groups, group bootstrap of field model - average, 10,000 resamples. Code: `run.py`,
  `evaluate.py`.
- **Pass if:** **(a)** for `asap7_ring/regulated`, on both dies, in at least 8 of the 10 chips the 95% interval of
  field model - average RMSE lies below 0.
- **Validity (INCONCLUSIVE).** Case set sha256 equals G84's; chips 21 to 30; salt 106; every profile present for every
  chip.
- **Reported, not gated.** Per profile: chips below the average, mean field-model RMSE and peak error, the
  average's RMSE, the corners drawn, the noise the estimators were told; the squeeze statistics and scale factors.
- **A fail means.** A ring oscillator built from ASAP7 cells and trimmed once is not good enough for field
  estimation to beat the training mean, so G102's `ring_osc` class was optimistic.
- **Not claimed.** One stack, steady state, 8 sensors per die; no within-die mismatch between sensors (the corner is
  per chip), no self-heating, no dynamic IR; the squeeze at a 1 mm block is G97's tile squeeze of a 77-97 um block
  (with or without the stated scaling), not a full-chip PDN. Only 2 of the 16 G84 sites lie inside the block, so the
  core-supply cases move few sensors.
- **Who fixed the choices.** The student delegated them (18 Nov: "no questions just do what youd recommend as id pick
  that option either way"). Gated: the regulated supply (real ring sensors regulate or ratio their supply);
  core supply reported, at G97's squeeze and scaled; dVBE reported with both trims, not gated.
- **Disclosed from the dry run (chips 1-5, `dry/profiles/scores.json`, `evaluate.py dry/profiles --dry`).**
  Field model below the average in 5 of 5 chips on both dies for every ASAP7 case and both dVBE trims, 2 of 5 for
  the IHP ring. Mean field-model RMSE top / bottom: regulated 0.38 / 0.42 K, core_g97 0.47 / 0.48, core_scaled
  1.35 / 1.00, IHP ring 3.34 / 3.21, dVBE one-point 1.23 / 1.22, two-point 0.51 / 0.57. Squeeze over the test
  cases at the 2 sensors inside the block: mean 0.47 mV (0.06 mV over all 16 sensors, the other 14 being 0), max
  0.78 mV (2.62 mV scaled). Earlier dry runs are kept as run: `*_v1.*` used one scale for all TPU windows (3.94) and
  unpaired dVBE trims (review fixed both); `*_v2.*` gives the same results as the current `scores.json`, which adds
  the inside-block mean and each run's resample count from the scorer (`evaluate.py` requires 10,000). The bar is the draft's (a),
  unchanged.

Amendments go below, dated, each with the reason. Never re-run until it passes.
