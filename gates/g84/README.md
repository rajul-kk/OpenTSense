# G84: Benchmark scorer · PASS (10 Nov 2026)

Registration: `registration.md` (bars fixed before the gated run; dry-run numbers disclosed there).
Run: `bash gates/g84/run.sh main` → `runs/main/{host,image}/`, verdict in `runs/main/result.json` (copied to `record/`).

## Verdict

| Bar | Result | Value |
|---|---|---|
| (v) plumbing | PASS | G71 seed 0 through the factorised G71 matrix vs G71's stored PACT fields: max 0.0050 K both dies (PACT's 0.01 K rounding) |
| (a) one command | PASS | `run.sh` built 400 cases and scored 4 estimators; `result.json`, `per_case.npz`, `manifest.json` written |
| (b) second machine | PASS | Image (Python 3.14, numpy 2.3.4, scipy 1.16.3) vs host (3.10, 2.2.6, 1.15.3): case T identical (max diff 0.0 K); per-case metrics max 2.6e-11 (margin 1e-6) |
| (c) wrong estimator worse | PASS | `inverted` − `average`, group-median RMSE: top +3.76 K [3.27, 4.02], buried +3.10 K [2.63, 3.47] |

## Reported (test split, 4 unseen programs, 80 cases; mean over groups of the group median)

| Estimator | Peak error top / buried (K) | RMSE top / buried (K) | Power error top / buried (rel. L2) | Fit time |
|---|---|---|---|---|
| average | 6.28 / 5.15 | 3.21 / 2.99 | 0.149 / 0.164 | < 0.01 s |
| field_model | 0.25 / 0.10 | 0.071 / 0.096 | n/a (temperature only) | 73 s |
| bayes_power | 2.29 / 0.45 | 1.22 / 0.40 | 0.095 / **0.359** | 0.02 s |
| inverted (wrong on purpose) | 16.06 / 12.03 | 6.97 / 6.09 | 0.343 / 0.442 | 0.03 s |

## Notes

- **Buried-die power is the hard part again.** `bayes_power` recovers the buried die's temperature (0.45 K peak) but
  its power worse than the training mean (0.359 against 0.164 relative L2). This matches the exploratory G54/G59
  identifiability limit. The same estimator improves the top die's power (0.095 against 0.149).
- `bayes_power` trails `field_model` on temperature here because its forward model assumes uniform power over each
  0.3 mm bin, and the TPU block concentrates power inside bins. This is a property of this case set, not a ranking of
  the methods (see "Not claimed" in the registration).
- Bar (c) rests on 4 test groups; the bootstrap interval is coarse at that size.
- Peak error alone did not separate a wrong estimator from the floor on the synthetic unit-test set (the dry run),
  so bar (c) uses RMSE. `protocol.md` should name its primary metric with this in mind.
