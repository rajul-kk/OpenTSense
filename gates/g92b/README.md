# G92b: gate-level leakage library and electro-thermal loop, every state planned from Liberty logic, IHP SG13G2 and ASAP7

**Verdict: FAIL on bar (a) for both kits, 4 Nov 2026.** Bars (b) and (c) passed for both. The registration and Amendment 1 (a scorer bracket fix) are in `registration.md`, the numbers in `runs/main/{ihp,asap7}/result.json`, and the failure entry in `../../../failures.md`.

| Bar | IHP SG13G2 (645 states) | ASAP7 RVT (8,576 states) |
|---|---|---|
| (a) Library equals SPICE | **FAIL.** 640 verified. The 5 failures are tri-state buffers (`ebufn_2/4/8`) with the enable off. The new all-outputs check planned the floating output at A's level, because the planner ignores `three_state`. 11 states classed unreachable, including all 9 G92 refused. The G53 cross-check matched within 0.17%. | **FAIL.** 8,552 verified. The 24 failures are a transient stop at the clock edge ("timestep too small") in the large DC clock gates (`ICGx2p67DC` to `ICGx8DC`) and `SDFHx4`/`SDFLx4`. 2 unreachable (tie cells), 19 free. The `leak.py` cross-check (INVx1, NAND2x1) matched within 0.22%. |
| (b) OpenSTA plumbing | PASS. Shipped-library leakage equals G75 in all 4 windows. Generated-library leakage rises strictly: 5.56 → 120 µW (k0, 25 → 125 °C). | PASS. Shipped-library leakage equals G34 in all 4 windows. Generated-library leakage: 2.22 → 116 µW (k0, 25 → 125 °C). |
| (c) Loop | PASS. 1 × 1 grid matches `brentq` exactly; PACT matches within 0.0009 K. Stress: amplification 1.76 measured vs 1.98 predicted. | PASS. 1 × 1 grid matches `brentq` exactly; PACT matches within 0.004 K. Stress (s ≈ 130 to 150): 1.60–1.69 measured vs 1.83–2.03 predicted, within 25%. |

**Correction, 5 Nov (found while preparing G92c): the ASAP7 count of 8,552 verified states is too high by 46.**
- When a transient aborts, ngspice prints 0 for its measurements. If every checked output was planned at 0, the level check passed, so the state was marked ok with 0 pW at that temperature.
- 46 ASAP7 states were affected:
  - DHLx1/2/3 and DLLx3: 2 each;
  - ICGx2p67DC to ICGx8DC: 4 each;
  - SDFLx4: 16;
  - NOR5xp2 and OAI31xp67: 1 each.
- So 8,506 ASAP7 states were truly verified, and the generated ASAP7 libraries hold 0 at some temperatures for those 46 states.
- The verdict is unchanged, since (a) had already failed.
- (b) and (c) used these libraries, so ASAP7's design leakage is slightly understated, to the extent ibex uses these cells.
- IHP's only zero-valued states are the `fill_*` cells, which have no transistors, so they are correct.
- G92 has the same check but was not affected: its only zeros are also `fill_*`.
- G92c adds an explicit abort check.

**Main finding, after the run: the 150 ns window is not steady state for captured states.**
- G53 chose the window, and G92 and G92b both used it. For states set by a capture sequence, internal nodes relax through leakage over microseconds at 25 °C.
- Two IHP states, measured at 150 ns / 1 µs / 10 µs / 100 µs:
  - `dlhq_1` open latch: 591 / 356 / 341 / **348** pW with G92's capture deck; 348 at every time with G92b's constant-input deck.
  - `sdfrbpq_1` with Q = 1: 1148 / 744 / 663 / **658** pW with G92's deck; 68 / 691 / 659 / **658** with G92b's.
- The decks converge to the same value given time, so the 116 IHP state values that moved between G92 and G92b are settling error, not wrong states.
- The G53 cross-check could not catch this, because `leak.py` uses the same window.
- **ASAP7 (`dry/settle7.py`, re-run 5 Nov, saving only the VDD current, 3 jobs at a time; the first try was stopped by the host's low-memory guard).**
  - 10 captured states (the first two non-forced states of DFFHQNx1, SDFHx1, DHLx1, ICGx1 and DFFASRHQNx1) at 25 °C, in pW at 150 ns / 1 µs / 10 µs / 100 µs:

    | Cell | State | 150 ns | 1 µs | 10 µs | 100 µs | 150 ns ÷ 100 µs − 1 |
    |---|---|---|---|---|---|---|
    | DFFHQNx1 | CLK·D·!QN | 191.4 | 186.6 | 169.1 | 158.2 | +21% |
    | DFFHQNx1 | CLK·D·QN | 271.0 | 184.4 | 173.1 | 166.2 | +63% |
    | SDFHx1 | CLK·D·SE·SI·!QN | 246.0 | 237.4 | 186.1 | 182.8 | +35% |
    | SDFHx1 | CLK·D·SE·SI·QN | 272.4 | 199.5 | 187.2 | 180.5 | +51% |
    | DHLx1 | !CLK·D·Q | 147.9 | 146.1 | 135.8 | 128.6 | +15% |
    | DHLx1 | !CLK·D·!Q | 255.7 | 168.3 | 158.6 | 158.6 | +61% |
    | ICGx1 | CLK·ENA·SE·!GCLK | 218.9 | 229.5 | 232.3 | 232.3 | −6% |
    | ICGx1 | CLK·ENA·SE·GCLK | 365.2 | 257.1 | 244.9 | 252.4 | +45% |
    | DFFASRHQNx1 | CLK·D·RESETN·SETN·QN | 337.5 | 249.9 | 225.2 | 214.7 | +57% |
    | DFFASRHQNx1 | CLK·D·RESETN·SETN·!QN | 276.6 | 264.4 | 243.7 | 234.7 | +18% |

  - All 10 are off by more than 5% at 150 ns: 9 too high (+15% to +63%) and 1 too low (−6%).
  - Five states are still falling by 3% to 6% between 10 µs and 100 µs, so 100 µs is not fully settled either.
  - ICGx1 with GCLK = 1 does not fall steadily (245 then 252 pW), so a settled value may need a DC solve, not a longer transient.
  - The ASAP7 captured-state values in this run, and the shipped ÷ SPICE ratios for those states, carry the same settling error as IHP.

**Reported, not gated**
- **Shipped library ÷ SPICE at 25 °C, reachable states:**
  - IHP: median 1.14, 70% more than 10% off.
  - ASAP7: median 1.29 (0.20 to 3.3), 98% more than 10% off. The shipped ASAP7 library overstates leakage at 25 °C for most states.
  - Both include the settling error above for captured states.
- **ASAP7 loop:**
  - **Nominal (300 K):** the peak is 333.8 K. Coupled leakage is 9.8 µW against 2.65 µW from the shipped library (3.7×), which is 0.14% of power. The peak moves 0.036 K, with ρ = 0.002.
  - **Hot (85 °C ambient):** the peak is 392 K. Leakage is 91 µW (34× shipped, 1.3% of power). The peak moves 0.42 K, with ρ = 0.015.
  - So feedback is about 10 to 200× IHP's, but still small for RVT ibex on this stack.
- **IHP loop:** as G92. The peak shift is 3.4e-5 K nominal and 0.002 K hot.
- **Run time:**
  - IHP: SPICE 13 min, OpenSTA 1 min.
  - ASAP7: SPICE 34 min, OpenSTA 3 min.
  - Scoring took about 1 min per kit.

**Next (G92c):**
- honour `three_state`;
- settle captured states, using a long run with a settle test or a DC solve seeded from the transient's end;
- use a larger shunt or a slower edge for the cells that stop.

**Files**
- `../../opentsense/power/leaklib.py`: the generator (G92's version is `../g92/leaklib_g92.py`).
- `power.tcl`, `evaluate.py`, `run.sh`: the gate scripts.
- `dry/`: the pre-registration dry-run and probe scripts, and the post-run settling scripts (`settle.py`, `settle7.py`).
