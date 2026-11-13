# G77b registration (written 12 Nov 2026, before the gated run; bars fixed now)

### G77b: Parameter rules once the binned model's fixed error is removed (RQ2) · REGISTERED

- **Why.** G77 failed (12 Nov): the binned forward model misses the sensor temperatures by 0.73 K (3D) and 1.87 K
  (2.5D) rms, mostly a fixed offset per sensor, so the rules told sigma under-regularised. Solving about the training
  cases' mean readings instead of H mu cancels a fixed offset exactly. This gate asks whether UPRE and the discrepancy
  rule then choose lambda as well as the oracle, and whether the change helps them. The student approved registering
  it on 12 Nov, with the draft's choices (`draft.md`).
- **Set-up.**
  - Case sets: G77's builder (`gates/g77/make_cases.py`, unchanged) with seed 81 (never built before), stacks 3d and
    25d, noise 0.01, 0.05 and 0.1 K, one noise draw per stack scaled by sigma, in `runs/cases/`.
  - Estimator: `bench.estimators.Tikhonov`, with reference "model" (H mu, as G77) and "readings" (the train split's
    mean readings at each sensor). Fitted on train; cal and test scored (8 program groups).
  - Rules: gcv, upre, discrepancy, lcurve with sigma known, for both references; upre and discrepancy with the readings
    reference also told 0.5 and 2 times sigma. Each reference has its own oracle (smallest power error over all dies,
    per case, on the same grid as G77).
  - Metric: per-die `pow_rel`, mean over groups of the group median. Command:
    `python gates/g77b/evaluate.py gates/g77b/runs/cases gates/g77b/runs/main/result.json --factor K`.
- **Noise floor (`plan.md` 2.1).** Bar (a)'s metric is the ratio of a gated entry's power error to its reference's
  oracle. Its floor is the largest sample standard deviation of that ratio over G77's floor builds (seeds 78, 79, 80;
  every stack, noise and die), by `dry/floor.py`, output `dry/floor.json`: **floor = 0.0046**. Factor, by the formula
  in the draft and in `dry/floor.py`, fixed before the floor was run: K = max(1.2, 1 + 3 x floor) = **1.2**.
- **Pass if all hold:**
  - **(a) Near the oracle:** UPRE and the discrepancy rule with the readings reference (sigma known) have a power error
    at most 1.2 times the readings oracle's, for every stack, noise level and die.
  - **(b) The reference helps:** for every stack, noise level and die, UPRE and the discrepancy rule (sigma known)
    have lower power error with the readings reference than with the model reference: group bootstrap of the paired
    difference (10,000 resamples, seed 0), two-sided p, Holm over the two rules, adjusted p < 0.05 and difference < 0.
- **Validity.** INCONCLUSIVE rather than FAIL if (v1) the seed-81 build's plumbing check exceeds 0.005 K (PACT's
  rounding), or (v2) the lambda grid's low end is above 1e-2 times the smallest singular value squared or its high end
  below 1e2 times the largest, in any case set. Both are checked by `evaluate.py`.
- **Reported, not gated.** GCV and the L-curve with each reference, and the readings-minus-model test for them; the
  wrong-sigma entries; how much the noise level changes each ratio; grid-end picks; peak errors.
- **Disclosed before the bars were fixed.**
  - The draft's pilot (seed 78, noise 0.1): with the readings reference UPRE 1.01 / 0.98 (3d top / buried) and 1.03
    (25d), discrepancy 1.00 / 1.01 and 1.02.
  - The floor runs (seeds 78-80, every noise level) were scored with the full evaluation, so both bars were seen on
    them: the worst gated ratio was 1.031, 1.028 and 1.029, and (b) held on every stack, noise and die for all three
    seeds. Bar (a)'s 1.2 and bar (b)'s form were written in the draft before any of these runs. What seed 81 tests is
    whether this holds on a draw the bars were not seen on.
- **A fail means.**
  - (a) fails: removing the fixed error is not enough for the sigma rules; the remaining case-to-case model error
    (0.12 K on 3d, 0.36 K on 25d at seed 77) must enter sigma (G77's second lead).
  - (b) fails: the reference change does not reliably help on some stack or die; report where.
- **Not claimed.** As G77: two G71 stacks sharing one seed, steady state, one sensor layout per stack, Gaussian noise.
  The readings reference needs training readings from the same sensors on the same chip (calibration runs), and it
  removes only the error that is the same in every case.
- **Code and output.** `evaluate.py` and `dry/` here (G77's builder and helpers reused, not copied); output in
  `runs/main/`; after the run, `python scripts/record_gate.py g77b`.

Amendments go below, dated, each with the reason. Never re-run until it passes.
