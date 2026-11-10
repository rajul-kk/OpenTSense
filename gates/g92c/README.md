# G92c: gate-level leakage library and electro-thermal loop, settled states, IHP SG13G2, ASAP7 RVT and ASAP7 LVT

**Verdict: FAIL on bar (a) for all three kits, 5 Nov 2026.** Bars (b) and (c) passed for all three. The registration is in `registration.md`, the numbers in `runs/main/{ihp,asap7,asap7_lvt}/result.json`, and the failure entry in `../../../failures.md`. The run used `JOBS=6` SPICE workers instead of 12 to fit host memory (a speed setting only). Wall time: IHP 19 min, ASAP7 RVT 43 min, LVT 42 min. The manifest records `dirty: true`: the G92c code is not committed yet.

| Bar | IHP SG13G2 (645 states) | ASAP7 RVT (8,576 states) | ASAP7 LVT (8,576 states) |
|---|---|---|---|
| (a) Library equals SPICE | **FAIL, on the G53 cross-check only.** All 645 states solved and checked (0 not ok); 6 three-state states flagged `hiz`; settling test passed on all 135 captured plans; settling validation `sdfrbpq_1` 657.93 vs 658.0 pW; G92b regression 2,500 values, max difference 0.0. But `dfrbp_1` differs from G53 by up to −18.7% (25 °C), against 1%. | **FAIL.** 7 of 8,595 solves failed the settling test (below). The G92b regression failed: max 15.0% (below). Cross-check INVx1/NAND2x1 within 0.23%; settling validation DHLx1 −0.44%, ICGx1 +0.02%. | **FAIL.** 2 entries failed: `AOI311xp33_L` with all inputs low (the state and its default entry). At 125 °C the transient stopped at t = 0, which the new abort check caught. Cross-check within 0.015%. |
| (b) OpenSTA plumbing | PASS | PASS | PASS (dynamic power identical across the five sets; leakage strictly rising) |
| (c) Loop | PASS | PASS | PASS |

## Why each kit failed

**IHP: the registered reference was itself unsettled (a registration error).**
- G53's `leak.py` measures `dfrbp_1` as the average current over 140–150 ns. That is the 150 ns method G92c replaces.
- For Q = 1 at 25 °C: G53 685.0 pW, G92c's own 150 ns transient 683.9 pW (within 0.2%), G92b 683.9 pW, and G92c settled 567.2 pW.
- So the library and the plumbing agree with G53 where they should. The bar compared a settled value with an unsettled one.
- Differences by temperature (Q0 / Q1): 25 °C −18.7% / −17.2%; 50 °C −8.2% / −7.0%; 75 °C +0.8% / −1.4%; 100 °C +0.4% / +1.8%.

**ASAP7 RVT, part 1: DC seeded from the continuation's end does not reliably stay on the stored value.**
- 7 failing entries, in 4 cells (DFFASRHQNx1, DFFLQNx1, SDFHx1, SDFLx1).
- Six failed only at 25 °C, where the DC value is 1.06–1.29% from the 10 ms continuation's end, against a 1% bar. At 50–125 °C they agree within 0.2%.
- One (DFFASRHQNx1, !CLK·!D·QN = 0) flipped to QN = 1 at 25 °C (−8.3%).
- **Post-run check** (`post/probe_cont.py`, `post/cont_100ms.log`; not scored): with a 100 ms continuation at 25 °C, all 9 DFFLQNx1 plans pass (worst 0.96%), and the flipped DFFASRHQNx1 state holds. But a *different* DFFASRHQNx1 state (CLK·!D·QN) now flips in the DC solve: 261.7 pW against 199.9 pW from the continuation, which held QN = 1.
- Even without a flip, the DC value stays about 0.5% below the continuation at 100 ms, so the continuation is still drifting.
- Conclusion: these cells have two DC solutions, and Newton seeded from a near-settled state can still land on the other one. A redesign should take the settled value from a long continuation with a flatness test, and use DC only as a cross-check.

**ASAP7 RVT, part 2: the regression bar was tighter than ngspice's 25 °C noise floor.**
- The registration claimed the 10 fF shunt could not change states with constant inputs, because a capacitor carries no DC current. That is wrong: these states are the average of an 8 ns transient, and the solve at 25 °C is not well conditioned.
- Of 8,125 compared states:

  | Temperature | Within 0.1% | 0.1–1% | 1–10% | Over 10% |
  |---|---|---|---|---|
  | 25 °C | 3,829 | 4,238 | 49 | 4 |
  | 50 °C | 6,816 | 1,290 | 19 | 0 |
  | 75 °C | 7,910 | 207 | 7 | 0 |
  | 100 °C | 8,083 | 36 | 6 | 0 |
  | 125 °C | 8,115 | 4 | 6 | 0 |

- The library total moves by only 0.04% at 25 °C.
- The worst values are deep-stack AO/OA/AOI/OAI 33x cells and the TIE cells. `OA333x2` (!A1·A2·A3·!B1·B2·B3·C1·C2·C3) at 25 °C:
  - transient: 112.3 pW (1 fF), 129.2 pW (10 fF);
  - DC `op`: 44.3 pW (1 fF), 13,098 pW (10 fF);
  - with `abstol=1e-16`: transient 117.0 pW, `op` 1,559 pW; with tighter `reltol`/`vntol` as well, most temperatures fail to converge.
  - At 50–125 °C, all four variants agree within 0.1%.
- So ngspice has no well-defined 25 °C solution for some deep-stack states. Their values carry about 1% noise, and a few carry more than 10%. This affects G92 and G92b's 25 °C values in the same way (`post/probe_comb.py`).

**LVT:** a single solver stop (above). The abort check that G92c added worked as intended: G92b's scorer would have passed it with 0 pW.

## Reported, not gated
- **150 ns ÷ settled, captured plans at 25 °C:**
  - IHP median 1.37 (0.96–1.89), 85% more than 5% off;
  - ASAP7 RVT median 1.37 (0.94–19.8), 61% more than 5% off;
  - LVT median 1.24 (0.95–2.95), 61% more than 5% off.
- **Shipped ÷ SPICE, reachable states at 25 °C:**
  - IHP median 1.17 (71% more than 10% off);
  - ASAP7 RVT median 1.29 (99.6%);
  - LVT median 1.43 (99.9%).
- **Design leakage, window k0, against G92b:**
  - IHP: 25 °C 5.21 vs 5.56 µW (−6%); at 125 °C both 120 µW.
  - ASAP7 RVT: 25 °C 2.20 vs 2.22 µW; at 100 °C 41.1 vs 49.2 µW (−16%); at 125 °C 96.8 vs 116 µW (−17%).
  - So in RVT ibex, settling lowers hot leakage by about a sixth.
- **LVT against RVT, same placed design:**
  - design leakage at 25 °C 18.0 vs 2.20 µW (8.2×), and 677 vs 96.8 µW at 125 °C (7.0×);
  - shipped LVT library 25.3 µW.
- **Loop, nominal ambient / 85 °C ambient, four windows:**

  | Kit | ρ (nominal) | Peak shift (nominal) | ρ (85 °C) | Peak shift (85 °C) | Amplification, measured vs 1/(1−ρ) |
  |---|---|---|---|---|---|
  | IHP | about 9.4e-6 | 3.5e-5 K | about 7.9e-5 | 0.002 K | |
  | ASAP7 RVT | 0.0016–0.0018 | 0.030–0.035 K | 0.012–0.014 | 0.35–0.38 K | |
  | ASAP7 LVT | 0.0154–0.0174 | 0.32–0.38 K | 0.089–0.099 | 2.9–3.2 K | 1.094–1.104 vs 1.098–1.110 |

  - G92b's RVT figures were ρ 0.0020–0.0022, peak shift 0.036 K, and 0.42 K hot.
  - LVT is the first case where leakage feedback is visible in a single-die ibex: about 3 K at 85 °C ambient.
- **Stress runs:** all converged; amplification measured vs predicted, within (c)'s bracket:
  - RVT 1.61–1.81 vs 1.85–2.12;
  - LVT 1.70–1.82 vs 1.85–2.17;
  - IHP 1.67–1.83 vs 1.82–2.11.

## Next (G92d, not registered)
1. **Captured states:** take the settled value from a long continuation, with a flatness test such as under 0.5% change over the last decade of time, and with the planned levels held. Keep DC only as a cross-check.
2. **Cross-check the IHP flip-flop** against a settled reference, not `leak.py`'s 150 ns value.
3. **Replace the 0.1% regression bar** with a bar set from the solver's measured noise floor. Report the deep-stack states whose 25 °C value is not unique.
4. **Retry solver stops** (as in LVT `AOI311xp33`) once, with a smaller first step, before failing.
