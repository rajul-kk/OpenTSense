# G77b draft (12 Nov 2026): parameter rules once the model's fixed error is removed · DRAFT, not registered

Follows G77 (FAIL, 12 Nov). There the binned forward model missed the sensor temperatures by 0.73 K (3D) and 1.87 K
(2.5D) rms, mostly a fixed offset per sensor, 7-190 times the sensor noise. The rules told sigma then under-regularised,
and the noise level barely mattered. RQ2.

## What exists (code, not results)

| Piece | File | Checked by |
|---|---|---|
| `Tikhonov(..., reference="readings")`: compare the readings with the training cases' mean readings instead of H mu | `opentsense/bench/estimators.py` | `tests/test_bench.py::test_reference_readings_removes_a_fixed_sensor_error`: a fixed sensor offset cancels exactly; without one, both references agree within 10% |
| Entries `ridge_gcv_ref`, `ridge_upre_ref`, `ridge_dp_ref`, `ridge_lc_ref` | same | same |
| Case builder and evaluation | `gates/g77/make_cases.py`, `gates/g77/evaluate.py` (would need the `_ref` entries added) | G77 |

## Pilot (not a result; seed 78, a G77 floor seed, noise 0.1 K, cal + test)

Power error / oracle's, top and buried die for 3D:

| Stack | reference | oracle pow_rel | gcv | upre | dp | lcurve |
|---|---|---|---|---|---|---|
| 3d | model (G77) | 0.093 / 0.204 | 1.32 / 1.26 | 1.15 / 1.03 | 1.11 / 1.03 | 1.72 / 1.12 |
| 3d | readings | 0.094 / 0.179 | 1.57 / 1.26 | 1.01 / 0.98 | 1.00 / 1.01 | 1.85 / 1.14 |
| 25d | model (G77) | 0.146 | 1.06 | 1.64 | 1.59 | 1.64 |
| 25d | readings | 0.127 | 1.03 | 1.03 | 1.02 | 1.03 |

With the readings reference, UPRE and the discrepancy rule sit at the oracle on both stacks, and the oracle itself
improves where the fixed error was largest (25d 0.146 to 0.127, 3d buried 0.204 to 0.179). GCV gets worse on the 3d
top die. These numbers were seen before any bar; seeds 77-80 are all seen now.

## Open choices for registration (student)

1. **Run it at all**, or record the lead and move on (G77 already answers RQ2's "which rule" for this estimator).
2. **Case sets.** A fresh seed (proposal: 81, built exactly as G77's), same stacks and noise levels.
3. **Bars (proposal; noise-floor rule first, the floor from seeds 78-80 with the readings reference):**
   - (a) UPRE and the discrepancy rule with the readings reference within a factor K of the oracle, every stack, noise
     and die (K = max(1.2, 1 + 3 x floor));
   - (b) the readings reference lowers UPRE's and the discrepancy rule's power error against the model reference, on
     every stack and die (group bootstrap, Holm over the two rules);
   - reported: GCV and the L-curve with each reference, the wrong-sigma entries, and whether noise now matters.
4. **Wrong sigma** as in G77 (0.5 and 2 times), reported.
