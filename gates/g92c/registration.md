# G92c registration (written 5 Nov 2026, before the gated run)

### G92c: Gate-level leakage library and electro-thermal loop, settled states, IHP SG13G2, ASAP7 RVT and ASAP7 LVT (RQ1, O1) · REGISTERED
- **Why:**
  - G92b failed bar (a) on both kits; bars (b) and (c) passed.
    - IHP: 5 states of `ebufn_2/4/8` with the output disabled (TE_B = 1). The planner ignored `three_state`, so the check expected a level on a floating output.
    - ASAP7: 24 states in 7 cells (ICGx2p67DC, ICGx4DC, ICGx5p33DC, ICGx6p67DC, ICGx8DC, SDFHx4, SDFLx4), where the capture transient stopped with "timestep too small" at some temperatures.
  - After the run, the 150 ns window turned out not to be steady state for captured sequential states.
    - IHP: from −90% to +74% on 2 cells.
    - ASAP7: from −6% to +63% on 10 states (G92b README).
  - The user asked on 5 Nov for LVT to be included. ASAP7 ships LVT and SLVT libraries and SPICE netlists with the same 202 cells as RVT. LVT is added as a third kit; SLVT is not run.
- **What changes from G92b:** only the library generator (`opentsense/power/leaklib.py`). G92b's version is kept as `gates/g92b/leaklib_g92b.py`. The OpenSTA step and the loop are G92b's.
  1. **Settling (captured states).**
     - A captured state is one whose stored value is set by a capture sequence: not forced, not combinational.
     - Its capture transient (G92b's sequence) runs as before at each temperature, and its node voltages at the end are written to a raw file.
     - **Continuation:** at that temperature, with every input constant at its final level, the transient continues from those voltages (`.ic`, `uic`) to 10 ms. With no edges left, the step may grow to 100 µs.
     - **DC solve:** every node is seeded (`.nodeset`) from the continuation's end. Its solution is the steady state, and its leakage is the state's value.
     - **Settling test (new, per state and temperature):**
       - the DC value is within 1% of the continuation's end value;
       - every output is at its planned level (10% of VDD) at the end of the capture, the end of the continuation, and the DC point.
     - The 150 ns value is kept and reported.
     - **Why two steps:** seeding the DC solve from the capture's end alone let Newton jump to the other stored value in SDFHx4/SDFLx4 at 25 °C (dry run). A 1 ms continuation showed the cell does hold the planned state (QN = 0.7 V, 418 pW).
     - States with constant inputs (forced, combinational) already start from a DC operating point, so they are unchanged.
  2. **Three-state outputs.**
     - An output whose `three_state` expression is true at the state's inputs is high-impedance.
     - It is left floating, at the isolated cell's own DC level, and it is not checked. The state is flagged `hiz`.
     - Only IHP uses `three_state` (`ebufn_2/4/8`, among others); ASAP7 does not.
  3. **Clock-edge solver fix (ASAP7).** The node shunt rises from 1 fF to 10 fF (`.options cshunt=1e-14`); input edges stay at 0.05 ns.
     - On the 8 cells that failed in G92b (159 plans), the dry run gave:

       | Setting | Plans failing |
       |---|---|
       | 1 fF, 0.05 ns edges (G92b) | 31 |
       | 1 fF, 0.2 ns edges | 22 |
       | 10 fF, either edge | 4, the SDFHx4/SDFLx4 flip, fixed by item 1's continuation |

     - A capacitor carries no DC current, and settled values come from a DC solve. So the shunt changes only the transient path, never a settled value. The regression bar below tests this for the states with constant inputs.
  4. **Abort check (a G92b scoring bug).**
     - When an analysis aborts, ngspice prints 0 for its measurements, which passed G92b's level check whenever every planned output was 0.
     - That passed 46 ASAP7 states with 0 pW at some temperatures (G92b README, correction of 5 Nov).
     - Any "aborted", "timestep too small", "failed!", "no convergence" or "singular matrix" in a run now fails the plan.
  5. **LVT kit** (`asap7_lvt`):
     - Liberty: the five LVT TT files matching the RVT ones.
     - SPICE: `cells_L.sp`, with the same models, 0.7 V and shunt.
     - Binding: ibex was placed and routed with RVT cells. For OpenSTA, every LVT Liberty file, both shipped and generated, has the cell-name suffix `_ASAP7_75t_L` renamed to `_ASAP7_75t_R`.
     - So the placed design is read with every cell swapped to its LVT twin, with the same footprints and pins. Activity (VCD) and parasitics stay those of the RVT design, and timing is not re-closed.
- **Dry run before registration (plumbing, not scored).**
  - **IHP probe solves** (`dlhq_1`, `sdfrbpq_1`, `ebufn_2`, all states; first with the DC-only settling): all pass, including the 4 `ebufn_2` states.
    - With the final method (capture, Gear continuation, then DC), `dlhq_1` and `dfrbp_1` pass all 18 plans.
    - The continuation's end matches the DC value to 4 significant figures at every temperature.
  - **ASAP7 probe solves** with the final method (10 cells: DFFHQNx1, DHLx1, DLLx3, ICGx1, ICGx8DC, ICGx2p67DC, SDFHx4, SDFLx4, NOR5xp2, OAI31xp67).
    - The host's low-memory guard stopped the run after 73 plans, all passing. These include every ICGx8DC state, which G92b could not solve.
    - SDFHx4 and SDFLx4 were not reached with the final method. With DC seeded from the continuation, the SDFHx4 state that had flipped settled at 418.3 pW, against 418.5 pW from a 1 ms transient.
  - **Earlier method choices** (dry run, in order):
    - a long transient with a large maximum step stops at the first clock edge;
    - DC seeded from the capture's end flipped 4 SDFHx4/SDFLx4 states at 25 °C;
    - a trapezoidal continuation rang at large steps, so its last-point current was unusable. Hence Gear.
  - **Settled values against the 100 µs transients** from G92b's post-run tests, for the states whose transient had flattened (under 0.5% change from 10 to 100 µs). Final method:
    - IHP `sdfrbpq_1` Q = 1: 657.9 against 658 pW (DC-only method);
    - ASAP7 DHLx1 (!CLK·D·!Q): 157.9 against 158.59 pW;
    - ASAP7 ICGx1 (CLK·ENA·SE·!GCLK): 232.4 against 232.32 pW.
    - These states are therefore not blind in the validation part of bar (a).
- **Cases, steps, windows, thermal set-up and run IDs:** as G92b.
  - **IHP:** G53 ibex, `configs/stacks/g92_ihp.yaml`.
  - **ASAP7 RVT and LVT:** G34 ibex, `configs/stacks/g92b_asap7.yaml`. OpenSTA runs 2 at a time.
- **Pass if all hold, for each of the three kits:**
  - **(a) Library equals SPICE.**
    - G92b's (a): every state planned and solved at all five temperatures, every checked pin within 10% of VDD; unreachable states only through G92b's rule.
    - For captured states, this holds at both the 150 ns transient and the settled DC point.
    - **Cross-check:**
      - IHP: G53's 8 states.
      - ASAP7 RVT: `leak.py` INVx1_R and NAND2x1_R.
      - ASAP7 LVT: `leak.py` INVx1_L and NAND2x1_L.
      - Each must match within 1% at 25, 50, 75 and 100 °C, as in G92b.
    - **Settling validation:** the settled value of each state listed in the dry run is within 1% of its 100 µs transient at 25 °C (IHP 1 state, ASAP7 RVT 2 states, LVT none).
    - **Regression (IHP and ASAP7 RVT):** every state that is neither captured nor high-impedance, and was solved in both runs, is within 0.1% of its G92b value at every temperature. Only captured and high-impedance states should move.
  - **(b) OpenSTA plumbing.**
    - IHP and ASAP7 RVT: G92b's (b).
    - LVT: no reference run exists, so only the second part applies: dynamic power identical across the five generated sets, and design leakage strictly rising with temperature.
  - **(c) Loop:** G92b's (c), unchanged, including Amendment 1's bracket.
- **Reported, not gated:**
  - per kit: the 150 ns ÷ settled ratio over captured plans at 25 °C, and the shipped ÷ SPICE ratio over reachable states at 25 °C;
  - design leakage at 25 °C and at the fixed point against G92b;
  - leakage share and peak shift per case, ρ, the stress factor s, and wall time;
  - for LVT: the same, plus its leakage against RVT's on the same design.
- **A fail means:** as G92b. Record any fail in `failures.md`.
- **Not claimed:**
  - as G92b;
  - the LVT case is a cell swap of an RVT-closed design, not an LVT implementation;
  - SLVT is not run;
  - the high-impedance level is the isolated cell's own, not a bus-held level.
- **Output:** `gates/g92c/runs/main/{ihp,asap7,asap7_lvt}/`
