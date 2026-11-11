# Sparse-sensor reconstruction on IC-ThermBench level 5 (5 Nov 2026, exploratory, not a gate)

- **Module:** `opentsense/estimate/`.
- **Tests:** `tests/test_estimate.py`, 14 tests, synthetic.
- **Data:** read only from `D:\Work\3D-ICE Thermal-modelling\Thermo\data\ic-thermbench\datasets`. Only the output temperature fields are used, so the transposed inputs do not matter.
- **Set-up:**
  - Gaussian field prior, rank 64, fitted on 64 × 64 fields.
  - Sensors read the true pixel temperature plus 0.1 K Gaussian noise.
  - Bands are split-conformal, α = 0.1. "cov" is the pixel coverage of the marginal band and the field coverage of the simultaneous band.
  - The OOD flag thresholds the Mahalanobis distance of the readings at the 95% calibration quantile.

## Benchmark split (`level5_m16_32.json`)
- **Splits:** train is Case16–18 plus 600 samples of Case19. Calibration and ID test are the two halves of the remaining 400 Case19 samples. OOD test is Case20.
- **Result:** Case20 is the easier set. At 32 sensors with Q-DEIM:
  - RMSE: 0.46 K on Case20 against 1.20 K on ID.
  - Coverage on Case20: 0.999 marginal, 1.000 simultaneous.
- **Why:** Case20 is a cool, narrow-range package. Its in-field range is 13 K, against 40 K for Case19.
- **OOD flag:** never fires on Case20. Its readings sit closer to the prior mean than ID's (AUROC ≈ 0), so the benchmark's single held-out package does not test cross-package robustness for this task.

## Leave one case out (`level5_loco_m32.json`, m = 32)
| held out | RMSE ID / held-out (K, greedy_a) | max error (K) | coverage marg / sim, held-out | OOD flag rate | AUROC |
|---|---|---|---|---|---|
| Case16 | 1.38 / 1.06 | 5.5 | 0.96 / 1.00 | 0.00 | 0.35 |
| Case17 (hot, 49 K range) | 0.94 / 2.86 | 15.8 | **0.42 / 0.27** | 1.00 | 1.00 |
| Case18 | 1.30 / 1.22 | 10.1 | 0.92 / 0.82 | 0.00 | 0.39 |
| Case19 | 1.22 / 2.08 | 13.0 | **0.81 / 0.08** | 0.87 | 0.98 |
| Case20 | 1.49 / 0.50 | 3.0 | 1.00 / 1.00 | 0.00 | 0.10 |

- **Coverage:** calibrated coverage holds on held-out packages that lie inside the training range (Case16, Case18, Case20), apart from the simultaneous band on Case18 (0.82). It collapses on the two packages that are hotter or wider than anything in training (Case17, Case19).
- **OOD flag:** it catches exactly those two packages from the 32 readings alone, at 87–100% detection with about a 5% false-alarm rate in distribution. So the flag works as a "do not trust the band" signal, not as a coverage fix.
- **Placement:** greedy A-optimal and Q-DEIM beat a uniform grid and random sites on ID data at 16 and 32 sensors, and in every leave-one-case-out fold. At 8 sensors the uniform grid was best on ID: 3.37 K, against 3.43 K for greedy A-optimal and 3.81 K for Q-DEIM.
- **Caveats:**
  - one seed, one noise level, one rank;
  - level 2–4 case labels come from the README layout, unconfirmed;
  - levels 2–4 were not run here (memory).
