# G77: Regularisation-parameter rules against the oracle (RQ2) · FAIL (run 12 Nov 2026)

Registration: `registration.md` (queued for commit as #44 before the run). Draft and review log: `draft.md`.
Output: `runs/main/` (git-ignored); record: `record/result.json`, `record/manifest.json`.

## Verdict

| Check | Result | Pass? |
|---|---|---|
| (v1) plumbing: G71's seed-0 power solved with the factorised matrix vs G71's PACT fields | max 0.0050 K (limit 0.005, PACT's rounding) | yes |
| (v2) the lambda grid reaches past both ends of the spectrum | low end 1.4e-8 x s_min^2, high end 1e2 x s_max^2 | yes |
| (a) every rule with sigma known within K = 1.5 of the oracle's power error, every stack, noise and die | worst 1.72 (lcurve, 3d top die); upre, dp, lcurve 1.63-1.67 on 25d | **no** |
| (b) UPRE and the discrepancy rule each beat GCV (sigma known), every stack, noise and die | only on the 3d buried die; tied on the 3d top die; GCV better on 25d | **no** |

Both validity conditions hold, so the verdict is **FAIL**: (a) and (b) both fail.

## Power error / oracle's (cal + test, 8 program groups; seed 77)

| Stack, die | noise K | gcv | upre | dp | lcurve | upre s0.5 / s2 | dp s0.5 / s2 |
|---|---|---|---|---|---|---|---|
| 3d top | 0.01 | 1.21 | 1.16 | 1.15 | 1.72 | 1.16 / 1.16 | 1.15 / 1.15 |
| 3d top | 0.1 | 1.22 | 1.16 | 1.11 | 1.69 | 1.16 / 1.15 | 1.14 / 1.07 |
| 3d buried | 0.01 | 1.16 | 0.98 | 0.98 | 1.03 | 0.98 / 0.98 | 0.98 / 0.98 |
| 3d buried | 0.1 | 1.16 | 0.98 | 0.99 | 1.03 | 0.98 / 0.98 | 0.98 / 1.00 |
| 25d chiplets | 0.01 | 1.05 | 1.67 | 1.67 | 1.67 | 1.67 / 1.67 | 1.67 / 1.66 |
| 25d chiplets | 0.1 | 1.05 | 1.67 | 1.63 | 1.67 | 1.67 / 1.67 | 1.65 / 1.58 |

Noise 0.05 is within 0.01 of the range of these two rows in every column (`record/result.json`). Ratios below 1 are possible: the oracle
minimises squared power error over both dies together, and the metric is each die's relative error.

Bar (b), sigma known, difference in power error against GCV (group bootstrap, Holm over the two rules):
- 3d buried die: UPRE -0.038 to -0.039 and DP -0.036 to -0.038 at every noise level, adjusted p < 0.001: both beat GCV.
- 3d top die: -0.005 to -0.010, intervals include 0 (adjusted p 0.19-0.58): no difference shown.
- 25d: UPRE +0.088 and DP +0.082 to +0.088, adjusted p < 0.001: GCV is better.

## What the failure shows (found after the run, not part of the verdict)

The noise level barely changes anything: every ratio moves by at most 0.09 between sigma = 0.01 and 0.1 K. The reason
is in the forward model, not the rules. At the sensors, the binned model (R for uniform power within each bin, applied
to the true binned power) misses the true temperatures by 0.73 K rms on the 3d stack and 1.87 K on the 25d stack,
7 to 190 times the sensor noise. Most of it is a fixed offset per sensor (up to 2.1 K on 3d and 4.3 K in magnitude on
25d), because the power inside each bin is concentrated in the blocks, which sit in the same place in every case; the
part that varies from case to case is 0.12 K (3d) and 0.36 K (25d).

So the rules that are told sigma (UPRE, discrepancy) expect a residual of about m sigma^2 and under-regularise against
a misfit that is mostly model error; GCV estimates the misfit from the data and does not. The L-curve has no such
excuse on the 3d top die and is simply the weakest rule there. On the buried 3d die, where the sensors see a smoothed
field, the sigma rules match the oracle (0.98).

## Leads (each would be a new gate)

- **Reference from the training readings.** Solve about the training-mean sensor readings instead of H mu, which
  removes the fixed binning offset; then rerun the rule comparison. If UPRE and DP recover, the claim becomes "sigma
  helps once the model's fixed error is removed".
- **Model error in sigma.** Tell UPRE and DP sigma_eff^2 = sigma^2 + (case-to-case mismatch measured on training
  cases): an estimate a real chip could make from calibration runs.
- **Finer bins near the blocks**, so the uniform-in-bin assumption holds where the power is.

## Not claimed

As registered: two G71 stacks sharing seed 77 (same program split and TPU draws), steady state, one sensor layout per
stack, Gaussian sensor noise, CPU power from toggle shares. The oracle uses the truth and bounds only this estimator.
