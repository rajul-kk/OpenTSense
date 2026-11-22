# G104 registration (written 18 Nov 2026, after the dry run, before the gated run)

### G104: Does the field model still work with sensors only outside the dense logic? (O2, RQ3; goals.md 16) · REGISTERED

- **Why.** G84 and G102 put sensors on a regular grid over the whole die, inside the dense logic block too. Real
  designs often cannot place a sensor inside a dense block. Draft: `draft.md`.
- **Site sets** (`dry/sites.py`'s `site_sets`, used unchanged; 8 sensors per die, chosen from the train split only):
  `all/uniform` (G84's sites, checked equal), `outside/uniform` (the regular grid's points outside G71's 1 mm active
  block and a 2-cell ring around it: the 3 x 3 grid minus its centre), `all/greedy_a` and `outside/greedy_a`
  (A-optimal greedy on the field model, die by die).
- **Cases and readings.** G84's case set rebuilt by `../g84/make_cases.py`, sha256 must equal G84's (f5941ad7...).
  `ring_osc` profile, `bench.readings` with salt 104, with independent offsets and with G105's die-wide correlated
  offsets (share 0.8, length 3 mm). **Gated chips: seeds 21 to 30**, none seen (the dry run used 1 to 5).
- **Scoring.** `bench.score` as G102: average and field model (fitted once on the train fields), test split,
  group-median RMSE per die averaged over groups, group bootstrap of field model - average (10,000 resamples).
  Code: `run.py`, `evaluate.py`.
- **Pass if both hold:**
  - **(a) Sensors outside the block still beat the average:** for `outside/uniform`, in both offset models and on both
    dies, in at least 8 of the 10 chips the 95% interval of field model - average RMSE lies below 0.
  - **(b) The cost of keeping sensors out of the block is small:** with independent offsets, on both dies, the mean
    RMSE over the 10 chips of `outside/uniform` is no more than 0.25 K above that of `all/uniform`.
- **Validity (INCONCLUSIVE).** The case set's sha256 equals G84's; the placed sites equal the dry run's and the
  placement noise matches it to 1e-9 (checked before scoring; if not, nothing is scored, and the run is set up again
  rather than recorded); chips 21 to 30; the offset models are independent and (0.8, 3 mm); all four sets
  present for every chip; every set has 8 sensors on each die.
- **Reported, not gated.** Per offset model and set: mean RMSE and peak error, the average's RMSE, chips below the
  average, the paired difference from `all/uniform` (mean +- standard error over chips); `outside/greedy_a` against
  `outside/uniform` (dry run, correlated offsets: +0.16 +- 0.13 K bottom, -0.04 +- 0.24 K top, not resolved; against
  `all/uniform` it was +0.32 +- 0.09 K on the bottom die).
- **A fail means.** (a): with sensors kept out of the dense block the field estimate is not reliably better than the
  training mean, so results with in-block sensors do not carry over to real placements. (b): the restriction costs
  more than 0.25 K, which every estimation result must then state.
- **Not claimed.** RMSE is over the whole die; the block's own error is not measured. One stack, steady state, one
  sensor count, one sensor class; the ring width (2 cells, 100 um) is assumed.
- **Disclosed from the dry run (chips 1-5, `dry/sites.json`).** Field model below the average in 5 of 5 chips for
  every set, die and offset model (average 3.0-3.2 K). `outside/uniform` minus `all/uniform`: +0.09 +- 0.05 /
  +0.08 +- 0.04 K independent, +0.19 +- 0.10 / +0.16 +- 0.08 K correlated (top / bottom). The bars are the draft's,
  unchanged.
- **Who fixed the bars.** The student delegated the choice (18 Nov: "no questions just do what youd recommend as id
  pick that option either way"); these are the draft's proposed bars, fixed before any gated chip was drawn.

Amendments go below, dated, each with the reason. Never re-run until it passes.
