# G77b: Parameter rules once the binned model's fixed error is removed (RQ2) · PASS (run 13 Nov 2026)

Registration: `registration.md` (queued for commit as #47 before the run). Draft and pilot: `draft.md`.
Output: `runs/main/` (git-ignored); record: `record/result.json`, `record/manifest.json`. Seed 81, cal + test
(8 program groups) per case set.

## Verdict

| Check | Result | Pass? |
|---|---|---|
| (v1) seed-81 plumbing against G71's PACT fields | max 0.0050 K (limit 0.005) | yes |
| (v2) lambda grid past both ends of the spectrum | low 1.4e-8 x s_min^2, high 1e2 x s_max^2 | yes |
| (a) UPRE and discrepancy, readings reference, within 1.2 of their oracle, every stack, noise, die | worst 1.032 | yes |
| (b) readings reference lowers UPRE's and discrepancy's power error, every stack, noise, die | all 18 tests, adjusted p <= 0.008 | yes |

**PASS.** Once the fixed error of the binned model is taken out, the rules that use the noise level pick lambda as
well as the best lambda in hindsight, on both stacks and at all three noise levels.

## Power error / own oracle (noise 0.01 and 0.1 K; 0.05 lies within their range or 0.01 of it)

| Stack, die | reference | oracle pow_rel | gcv | upre | dp | lcurve |
|---|---|---|---|---|---|---|
| 3d top | model (G77) | 0.097 | 1.49-1.51 | 1.14 | 1.11-1.13 | 1.67 |
| 3d top | readings | 0.096 | 1.59-1.60 | 1.01 | 1.00-1.01 | 1.81 |
| 3d buried | model | 0.216-0.218 | 1.16-1.19 | 0.99-1.00 | 0.98-1.00 | 1.09 |
| 3d buried | readings | 0.190 | 1.25-1.26 | 0.97-0.98 | 0.98-1.00 | 1.14-1.15 |
| 25d chiplets | model | 0.155 | 1.06 | 1.57 | 1.53-1.56 | 1.57 |
| 25d chiplets | readings | 0.132 | 1.03 | 1.03 | 1.02-1.03 | 1.03 |

Bar (b), readings minus model, power error: 25d -0.103 to -0.107; 3d top -0.011 to -0.014; 3d buried -0.024 to -0.031.

## Reported

- **The oracle improves too** with the readings reference: 25d 0.155 to 0.132, 3d buried 0.216-0.218 to 0.190, 3d
  top unchanged (0.097 to 0.096). The fixed error cost accuracy no lambda could recover.
- **GCV and the L-curve do not benefit on the 3D stack.** On the top die they get slightly worse (GCV 1.49 to 1.60,
  L-curve 1.67 to 1.81; differences +0.007 to +0.012, not significant); on the buried die GCV's absolute error falls
  but its ratio to the improved oracle rises (1.16-1.19 to 1.25-1.26). On 25d every rule reaches 1.03.
- **Wrong sigma barely matters** with the readings reference: 0.5 and 2 times sigma give 0.97-1.03 everywhere.
- **Noise level barely matters** either (the sigma-known entries move by at most 0.03 across 0.01-0.1 K; dp told 2
  sigma on the 3d buried die by 0.05): the remaining model error
  still dominates the sensor noise; the rules no longer mistake it for something it is not.

## What this means for RQ2

G77 and G77b together: with a binned power model, the choice of the regularisation rule matters less than the
reference the data are compared with. Compared with the training readings, UPRE and the discrepancy rule are within
3% of the oracle and robust to a factor-2 error in sigma; GCV and the L-curve are not reliable on the 3D stack's top
die. A real chip can form this reference from calibration runs on the same sensors.

## Not claimed

As registered: two G71 stacks sharing seed 81, steady state, one sensor layout per stack, Gaussian sensor noise, CPU
power from toggle shares. The reference removes only error that is the same in every case; it needs training readings
from the same sensors on the same chip. Both bars had held on seeds 78-80 before registration (disclosed there).
