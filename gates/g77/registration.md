# G77 registration (written 12 Nov 2026, before the gated run; bars fixed now)

### G77: Regularisation-parameter rules against the oracle (RQ2) · REGISTERED

- **Why.** Tikhonov power recovery needs a regularisation parameter per case. GCV needs no noise level; UPRE and the
  discrepancy principle need sigma, which a real chip knows only roughly. This gate asks how far each rule is from the
  best parameter in hindsight (the oracle), and whether knowing sigma helps. It builds on G11 (GCV, exploratory) and
  uses G84's scorer metrics. The choices below are the student's decisions of 12 Nov (`draft.md`).
- **Set-up.**
  - Case sets: `make_cases.py` (G84's construction over two stacks; it reproduces G84's case set exactly with
    G84's settings, checked 12 Nov). Seed 77 (never used before), stacks `3d` (G71 3D, TPU die on top, CPU die
    buried, 8 sensors per die) and `25d` (G71 2.5D, CPU and TPU chiplets on one layer, 16 sensors), noise 0.01,
    0.05 and 0.1 K: six case sets of 400 cases in `runs/cases/` (sha256 in `runs/cases/cases.json`). Each stack has
    one standard-normal noise draw, scaled by each sigma (common random numbers), so the noise levels differ only in
    sigma; with one sigma this is G84's draw bit for bit, and the G84 reproduction was rerun after the change.
  - Estimator: `bench.estimators.Tikhonov`, fitted on the train split (it uses only the training-mean power).
    Every case of the cal and test splits is scored: Tikhonov uses nothing from cal, and this gives 8 program groups
    instead of 4.
  - Rules: gcv, upre, discrepancy, lcurve with sigma known; upre and discrepancy also told 0.5 and 2 times sigma.
    Oracle: the grid value with the smallest squared power error over all dies, per case (evaluation only).
  - Grid: 80 log-spaced values from 1e-10 to 1e2 times the largest singular value squared (`regularise.default_grid`).
  - Metric: per-die relative power error `pow_rel`, aggregated as the mean over groups of the group median.
  - Code: `evaluate.py`; command `python gates/g77/evaluate.py gates/g77/runs/cases runs/main/result.json --factor K`.
- **Noise floor (`plan.md` 2.1).** Bar (a)'s metric is the ratio (rule / oracle). Its floor is the largest sample
  standard deviation of that ratio over three repeat case builds (seeds 78, 79, 80; every stack, noise, die and rule
  with sigma known), measured by `dry/floor.py`, output `dry/floor.json`: **floor = 0.098**. The factor follows the
  formula fixed in `dry/floor.py` before the floor was seen: K = max(1.5, 1 + 3 x floor) = **1.50**.
- **Pass if all hold:**
  - **(a) Each rule is near the oracle:** for every stack, noise level and die (buried die included), each rule with
    sigma known has a power error at most K times the oracle's.
  - **(b) Knowing sigma helps:** for every stack, noise level and die, UPRE and the discrepancy rule (sigma known)
    each have lower power error than GCV: group bootstrap of the paired difference (10,000 resamples, seed 0),
    two-sided p, Holm over the two rules, adjusted p < 0.05 and difference < 0.
- **Validity.** INCONCLUSIVE rather than FAIL if (v1) the seed-77 build's plumbing check (recorded in `cases.json`, checked by
  `evaluate.py`) fails (G71's seed-0 power
  solved with the factorised matrix differs from G71's stored PACT fields by more than 0.005 K, PACT's rounding), or
  (v2) the lambda grid does not reach past both ends of the spectrum in some case set: its low end must be at most
  1e-2 times the smallest singular value squared and its high end at least 1e2 times the largest. Past those points
  the solution no longer changes, so an oracle pick at a grid end is a real preference (no regularisation, or the
  training mean) rather than the grid's limit. Grid-end picks are reported per end.
- **Reported, not gated.**
  - (b) at the wrong sigma (0.5 and 2 times): does the order hold?
  - Every entry's power and peak errors, ratio to the oracle, how often it picks a grid end, and its median
    log10(lambda / oracle lambda).
  - Against `bayes_power` (c in the draft): not run here, since it uses the training covariance and Tikhonov does not.
- **Disclosed before the bars were fixed.** The draft's pilot (G84's case set, seed 84) gave peak errors only.
  Running `evaluate.py` on that set as a plumbing check (12 Nov) also gave the power ratios to the oracle, which were
  seen before this registration:
  - top die: gcv 1.38, upre 1.21, discrepancy 1.16, lcurve 1.69;
  - buried die: gcv 1.16, upre 0.97, discrepancy 0.99, lcurve 1.02;
  - the oracle picked the grid's low end in 31% of cases and the high end in 1%; that grid's low end is 1.4e-8
    times the smallest singular value squared, so these are converged picks (no regularisation best), not the grid.
  The floor runs (seeds 78-80, after the formula was fixed) also show where the rules sit: ratios of the gated rules
  range 0.93-1.83 on the 3d stack and 1.06-1.83 on the 25d stack. Above 1.5 on some floor seed: 25d ridge_dp (chiplets); 25d ridge_lc (chiplets); 25d ridge_upre (chiplets); 3d ridge_lc (top).
  Bar (a) is therefore expected to fail. The factor was not changed after seeing this.
  Ratios below 1 are possible because the oracle minimises squared power error over both dies together, and the
  metric is the per-die relative error. The factor formula (1.5 from the draft) was not changed after seeing them.
- **A fail means.**
  - (a) fails: that rule leaves at least (K - 1) of the attainable power accuracy on the table on this problem; its
    entry is reported as such and the best rule is used downstream.
  - (b) fails: knowing sigma does not reliably beat GCV here, so GCV (no noise model needed) is the default.
- **Not claimed.** The two stacks share seed 77, so they share the program split and the TPU draws: "holds on both
  stacks" is two solvers' views of one draw, not two independent draws. Two stacks from G71, steady state, one sensor layout per stack, Gaussian noise of known form, and
  CPU power from toggle shares. The oracle is per case and uses the truth; it bounds what a parameter choice could do
  with this estimator, not what any estimator could do.
- **Code and output.** `make_cases.py`, `evaluate.py` and `dry/` here; output in `runs/main/`; after the run,
  `python scripts/record_gate.py g77`.

Amendments go below, dated, each with the reason. Never re-run until it passes.
