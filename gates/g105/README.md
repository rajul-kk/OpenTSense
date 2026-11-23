# G105: Do the field model's lead and the joint calibration survive spatially correlated sensor offsets? (O2, RQ3) · PASS (run 18 Nov 2026)

Registration: `registration.md` (queued as #195 before the run; bars fixed under the student's delegation of 18 Nov).
Run: `run.py runs/main` (chips 21-30; chips 1-20 were the dry run, `dry/corr.json`), scored by
`evaluate.py runs/main`. Output `runs/main/` (git-ignored); record: `record/{result,manifest}.json`.

## Verdict: PASS

Validity held: G84's case set rebuilt to its recorded sha256, the code and stack-config hashes unchanged from start
to end of the run, chips 21-30, the four registered settings with their values, profile `ring_osc`, salt 105,
10,000 resamples.

| Bar (setting 0.8, 3 mm) | Needed | Result |
|---|---|---|
| (a) field model beats the average, uncalibrated, both dies | CI below 0 in >= 8 of 10 chips | 10 of 10 on both dies |
| (b) calibration does not hurt, both dies | calibrated - uncalibrated mean RMSE <= 0.1 K | -0.02 K top, +0.01 K bottom |

## Reported (not gated), chips 21-30

Field-model RMSE in K (mean over chips of the mean group median), top / bottom; difference from independent offsets
paired by chip, mean +- standard error; fixed-error RMS and what calibration leaves of it:

| Offsets (share, length) | Uncalibrated | Calibrated | vs independent, uncalibrated | Fixed error | Left after calibration |
|---|---|---|---|---|---|
| independent | 0.26 / 0.34 | 0.24 / 0.30 | - | 1.09 K | 0.21 K (19%) |
| 0.5, 0.5 mm | 0.25 / 0.30 | 0.21 / 0.28 | -0.01 +- 0.04 / -0.04 +- 0.03 | 1.05 | 0.18 (17%) |
| 0.5, 1.5 mm | 0.44 / 0.47 | 0.43 / 0.46 | +0.18 +- 0.05 / +0.13 +- 0.05 | 0.99 | 0.43 (43%) |
| 0.8, 3 mm | 0.66 / 0.64 | 0.64 / 0.65 | +0.41 +- 0.06 / +0.30 +- 0.06 | 0.98 | 0.66 (67%) |

The field model beats the average in 10 of 10 chips in every setting, on both dies, calibrated or not. G105's output
records the intervals against the average, not its RMSE; the average does not read the sensors, so it is the same
as in G104's record on the same case set and test split, 3.21 / 2.98 K. The leave-one-out check raised no false
alarm in any chip or setting.

- **A die-wide smooth offset costs the field model the most of the four settings.** Its RMSE is about two and a
  half times the independent case's (0.66 against 0.26 K, top die), and still about a fifth of the average's.
- **Calibration cannot remove what looks like heat.** It removes 81% of an independent fixed error but only a third
  of a die-wide smooth one (0.66 of 0.98 K left), so calibrated and uncalibrated errors are almost equal at 0.8, 3 mm.
  This is the predicted weak point (`draft.md`): the joint calibration drops offset patterns it cannot tell from heat.
- **Against the dry run.** The gated chips show a larger effect than the dry run's 20 chips (+0.41 / +0.30 K against
  +0.18 / +0.13 K; dry fixed error left 40%, here 67%), and the 1.5 mm setting is now clearly above independent. The
  dry run's uncalibrated false alarms (3.0% at 0.8, 3 mm and 1.2-4.6% across settings, from a few chips with one
  large offset) did not recur.

**Not claimed.** One stack, steady state, 8 sensors per die on G84's grid, one sensor class; the correlation
settings are assumed, not measured.
