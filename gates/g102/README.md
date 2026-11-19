# G102: Does the estimator ranking survive a realistic sensor? (O2, RQ3) · PASS (run 16 Nov 2026)

Registration: `registration.md` (queued as #108 before the run). Run: `run.py runs/main` (chips 6-15; chips 1-5 were
the dry run), scored by `evaluate.py runs/main`. Output `runs/main/` (git-ignored); record: `record/{result,manifest}.json`.

## Verdict: PASS

Validity held: G84's case set rebuilt to its recorded sha256, the code hashes unchanged from start to end of the run,
chips 6-15 and all four sensor profiles present.

| Bar | Needed | Result |
|---|---|---|
| (a) field model beats the average, `bjt_trimmed` and `ring_osc`, both dies | CI below 0 in >= 8 of 10 chips | 10 of 10 in all four |
| (b) the inverted estimator stays worse than the average, three realistic profiles, both dies | above 0 in every chip | 10 of 10 in all six |

## Reported (not gated): RMSE in K, mean over chips 6-15 (top / bottom die)

| Profile | average | field model | bayes power | inverted |
|---|---|---|---|---|
| ideal_gauss (G84's model) | 3.21 / 2.98 | 0.07 / 0.09 | 1.22 / 0.40 | 6.97 / 6.08 |
| bjt_trimmed | 3.21 / 2.98 | 0.07 / 0.10 | 1.22 / 0.42 | 6.98 / 6.14 |
| ring_osc | 3.21 / 2.98 | 0.23 / 0.31 | 1.29 / 0.58 | 7.01 / 6.42 |
| dts_1c | 3.21 / 2.98 | 0.29 / 0.35 | 1.29 / 0.59 | 6.96 / 6.30 |

The average does not read the sensors, so its row is the same in every profile. A trimmed BJT sensor costs the field
model almost nothing over G84's idealised sensor. A ring oscillator or a 1 K register triples or quadruples its
error, to about 0.3 K, which is still ten times better than the average. The ordering of the estimators is the same
in every profile. `dts_1c` was reported only: the field model beats the average in every chip there too
(`result.json`, `reported`).

## What this means

The estimation results (G84 onward) were scored with an idealised sensor. With per-sensor offsets, gain errors and
quantised codes from published sensor classes, the ranking holds and the field model's error stays below 0.4 K.
Not claimed: transient sampling (steady cases only), sensor placement, sensor failure, self-heating.
