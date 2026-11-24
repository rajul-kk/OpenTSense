# G107 registration (written 20 Nov 2026, after the dry run, before the gated run)

### G107: How few sensors does the buried die need? (O2, RQ3; goals.md 21, item 3) · REGISTERED

- **Why.** A buried die's sensors must be read out across the bond (TSVs or bond pads), and TSV area is scarce. The
  protocol (section 1.1) has a Track R case set with no sensor on the buried die, and Track P gives each die its own
  budget. Draft: `draft.md`.
- **Site sets** (`dry/budget.py`'s `site_sets`, used unchanged; chosen from the train split only). The top die keeps
  G84's 8 uniform sites in every per-die set. `bot8/uniform` (G84's sites, the reference), `bot4/uniform`,
  `bot2/uniform`, `bot1/uniform` (`estimate.placement.uniform_grid` on the buried die), `bot0/uniform` (no buried
  sensor), `bot4/greedy_a`, `bot2/greedy_a`, `bot1/greedy_a` (A-optimal greedy on the buried die given the top
  die's sites), `joint12/greedy_a`, `joint16/greedy_a` (no per-die budget).
- **Cases and readings.** G84's case set rebuilt by `../g84/make_cases.py`, sha256 must equal G84's (f5941ad7...).
  `ring_osc` profile, `bench.readings` with salt 107, with independent offsets and with G105's die-wide correlated
  offsets (share 0.8, length 3 mm). Each chip is read once at the union of all sets' sites and each set takes its
  sensors from that read (`bench.readings.subset`). **Gated chips: seeds 21 to 30**, none seen (the dry run used 1
  to 5).
- **Scoring.** `bench.score`: average and field model (fitted once on the train fields), test split, group-median
  RMSE per die averaged over groups. Code: `run.py` (calls `dry/budget.py`'s `main`), `evaluate.py`.
- **Pass if all three hold** (buried die; mean field-model RMSE over the 10 chips of the set minus that of
  `bot8/uniform`):
  - **(a) No buried sensor costs little with independent offsets:** `bot0/uniform`, independent offsets, <= 0.25 K.
  - **(b) Two buried sensors suffice with independent offsets:** `bot2/uniform`, independent offsets, <= 0.25 K.
  - **(c) Two buried sensors suffice with correlated offsets:** `bot2/uniform`, correlated offsets, <= 0.25 K.
- **Validity (INCONCLUSIVE).** The case set's sha256 equals G84's; the placed sites, the buried die and the
  placement noise equal the dry run's (`dry/budget.json`; checked before scoring, and if not, nothing is scored and
  the run is set up again rather than recorded); chips 21 to 30; salt 107; profile `ring_osc`; both offset models;
  every set present for every chip with its registered per-die count (8 and 8, 4, 2, 1, 0 on the buried die; 12 and
  16 in all for the joint sets); every RMSE and peak error finite; `scores.json` carries `complete` and
  `inputs_unchanged` (the sha256 of every input, `run.py`, `dry/budget.json` and `make_cases.py` included, equal at
  the start and the end).
- **Reported, not gated.** Per offset model, set and die: mean RMSE and peak error, the average's RMSE, chips where
  the field model is below the average (CI below 0), the paired difference from `bot8/uniform` (mean +- standard
  error over chips); the joint sets' split between the dies; `bot0/uniform` with correlated offsets.
- **A fail means.** (a): the top die's sensors alone do not reconstruct the buried die within 0.25 K, so the
  no-buried-sensor case set measures a real loss and every result on it must say so. (b) or (c): a quarter budget
  on the buried die costs more than 0.25 K, so Track P's buried budget cannot start at 2.
- **Not claimed.** One stack (G71, buried CPU die under the TPU die), steady state, one sensor class, whole-die RMSE;
  the cost of a buried sensor (TSVs, area) is not modelled; greedy's buried sites lie inside the active block, which
  real TSV keep-outs may forbid.
- **Disclosed from the dry run (chips 1-5, `dry/budget.json`).** Buried die, minus `bot8/uniform`: `bot0/uniform`
  +0.06 +- 0.10 K independent, +0.44 +- 0.30 K correlated; `bot2/uniform` +0.05 +- 0.02 K independent, +0.07 +-
  0.12 K correlated. The field model was below the average in 5 of 5 chips for every set, die and offset model.
  `bot1/greedy_a` places the same buried site as `bot1/uniform` (cell 30, 30), so the two are one site set read
  once; they are kept as two names and reported as one result, not as greedy agreeing with uniform.
  The bars are the draft's after review (bar (a) changed from "beats the average", which could not fail), fixed
  before any gated chip was drawn.
- **Who fixed the bars.** The student delegated the choice (18 Nov: "no questions just do what youd recommend as id
  pick that option either way"; 20 Nov: "register G107 and run it").

Amendments go below, dated, each with the reason. Never re-run until it passes.
