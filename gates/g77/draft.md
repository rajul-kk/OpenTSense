# G77 draft (11 Nov 2026): regularisation parameter rules against the oracle · DRAFT, not registered

Row in `../../../todo-gates.md`: "Regularisation parameter chosen by UPRE or the discrepancy principle vs GCV and the
L-curve, each against the oracle parameter from ground truth". RQ2. Builds on G11 (GCV, exploratory).

## What exists (code, not results)

| Piece | File | Checked by |
|---|---|---|
| Tikhonov solution and the four rules on a lambda grid (SVD filter factors) | `opentsense/estimate/regularise.py` | `tests/test_regularise.py`: residual, solution norm, degrees of freedom and solution equal the dense formulas (m < n and m > n); the discrepancy pick meets its target; each rule within 1.5x of the oracle's median error on a graded test problem |
| Oracle lambda from the truth (evaluation only) | `regularise.oracle` | same |
| Benchmark entries `ridge_gcv`, `ridge_upre`, `ridge_dp`, `ridge_lc` (Tikhonov about the training-mean power) | `opentsense/bench/estimators.py` (`Tikhonov`) | `tests/test_bench.py`: each beats `average` on RMSE on the synthetic case set |

`BayesPower` now shares its set-up with `Tikhonov` (`LinearPower`). Re-scoring G84's frozen host case set gives
per-case metrics and `result.json` identical to the recorded run (apart from timings), so G84 is unaffected.

## Pilot (not a result)

One scorer run on G84's host case set (11 Nov), to check the plumbing. Group-median peak error, K:

| Estimator | top die | buried die |
|---|---|---|
| average | 6.275 | 5.148 |
| bayes_power | 2.290 | 0.448 |
| ridge_gcv | 3.205 | 0.828 |
| ridge_upre | 1.762 | 0.366 |
| ridge_dp | 1.975 | 0.380 |
| ridge_lc | 1.809 | 0.603 |
| field_model | 0.252 | 0.102 |

These numbers were seen before any bar was fixed. The registered run must use a case set the bars were not tuned on
(a fresh `make_cases.py` seed, or the G93 stacks once they exist).

## Ready for the registered run (12 Nov)

- `gates/g77/make_cases.py OUT --seed S --noise N`: G84's case maker unchanged except SEED and NOISE (seed 84, the
  pilot, is refused). Not yet run: it factorises G71's PACT matrix, a medium job, and waits for G92e's heavy run.
- Wrong-sigma entries in the estimator registry: `ridge_upre_s0.5`, `ridge_upre_s2`, `ridge_dp_s0.5`, `ridge_dp_s2`
  (the rule is told half or twice the true sigma). Unit test: at scale 1 they equal the plain entries, and the
  discrepancy rule's lambda rises with the sigma it is told.

## Open choices for registration (student)

1. **Case sets.** G84's set plus at least one other stack; the noise level swept (for example 0.01, 0.05, 0.1 K),
   because UPRE and the discrepancy principle depend on knowing sigma and GCV does not.
2. **Wrong sigma.** Run UPRE and the discrepancy rule with sigma off by a factor of 0.5 and 2 (the realistic case).
3. **Quantity.** Per-die power error (`pow_rel`) and peak error, buried die reported separately; the oracle minimises
   power error.
4. **Bars (proposal, apply the noise-floor rule of `plan.md` 2.1 first):**
   - (a) each rule's median power error within a registered factor of the oracle's (the unit test uses 1.5);
   - (b) the ranking question: does UPRE or the discrepancy rule beat GCV with sigma known, and does the order hold at
     the wrong sigma? Paired test with group bootstrap, Holm across rules;
   - (c) against `bayes_power`: reported, not gated, since it uses the training covariance and Tikhonov does not.
5. **Grid.** 80 log-spaced values from 1e-10 to 1e2 times the largest singular value squared; report how often a
   rule picks a grid end (a pick at an end means the grid, not the rule, decided).
