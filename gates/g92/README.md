# G92: gate-level leakage library and electro-thermal loop

**Verdict: FAIL on bar (a), 4 Nov 2026.** Bars (b) and (c) passed. The registration and Amendments 1 to 4 are in `registration.md`, the numbers in `runs/main/result.json`, and the failure entry in `../../../failures.md`.

| Bar | Result |
|---|---|
| (a) Library equals SPICE | **FAIL.** 630 of 645 states were solved and verified, including 348 sequential states. 9 of the other 15 are states the library lists that the circuit cannot hold, so the check refused them. The other 6 are in 4 cells the generator could not drive: antenna diode, bus holder, and two clock-gate cells. (Corrected 4 Nov from "11 / 4".) The G53 states matched `leak.py` within 0.17% at 25 to 100 °C (bar 1%). |
| (b) OpenSTA plumbing | PASS. With the shipped library, OpenSTA's design leakage equals G75's to 6 significant figures in all 4 windows. Dynamic power is identical across the 5 libraries, and leakage rises strictly with temperature: 5.56, 9.76, 21.3, 50.4 and 120 µW at 25, 50, 75, 100 and 125 °C (k0). |
| (c) Loop | PASS. Every case converged. The 1 × 1 grid matches `brentq` within 6e-14 K, and a full PACT solve matches the operator's peak within 0.0009 K. Measured amplification against 1/(1 − ρ): nominal and hot agree to 6 digits; stress gives 1.76 vs 1.98, which is within 25%. |

**Reported, not gated**
- **Shipped library ÷ SPICE at 25 °C, over 626 states:** 0.51 to 16.1×, median 1.14. 73% of states are more than 10% off. G53 saw only 8 states.
- **Nominal (300 K ambient):** leakage is 0.02% of power. The coupled loop moves the peak by 3.4e-5 K and ρ = 9e-6, so IHP 130 nm ibex has no meaningful feedback.
- **Hot (85 °C ambient):** coupled leakage is 31 µW against 5.9 µW from the shipped 25 °C library (5.3×). That is still 0.11% of power, and the peak moves 0.002 K.
- **Stress (synthetic, leakage × 2.9e4 so that ρ ≈ 0.5):** the peak moves 8.2 to 8.4 K. 1/(1 − ρ) overpredicts the amplification by 12%.
- **Run time:** SPICE 26 min (12 single-thread jobs), OpenSTA 2 min, scoring 4 min.

**Not claimed:** silicon accuracy, which rests on the PSP103 models; internal power at temperature, which stays at the 25 °C library value; or ρ near 1.

**Files**
- `opentsense/power/leaklib.py`: the library generator.
- `opentsense/thermal/electrothermal.py`: the loop.
- `power.tcl`, `evaluate.py`, `run.sh`: the gate scripts.
- `runs/aborted_1` to `aborted_3`: the stopped starts, not scored.

**Later finding (G92b, 4 Nov):** the 150 ns measurement window is not steady state for states set by a capture sequence at 25 °C (e.g. `sdfrbpq_1` Q = 1: 1148 pW at 150 ns, 658 pW at 100 µs). G92's sequential-state values carry this settling error; see `../g92b/README.md`. The loop conclusions (negligible IHP feedback) are not affected at that scale.
