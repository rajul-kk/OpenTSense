# G92 registration (written 4 Nov 2026, before any code for it ran)

### G92: Gate-level leakage library and electro-thermal loop (RQ1, O1) · REGISTERED
- **Why:**
  - G75 found the shipped 25 °C IHP library is 2 to 17× low at 75 to 100 °C.
  - The loops so far (G31/G31b, G74, G75 (3)) scale whole tiles by a few representative cell curves.
  - This gate builds the leakage side as a reusable tool and checks it. Every instance gets the leakage of its own cell and input state, at its own tile's temperature, from SPICE.
  - The research survey of 4 Nov found no open tool that closes this loop at gate level.
- **Design:** routed IHP SG13G2 ibex from G53, typ 1.2 V. Its real windows k0 to k3 are the G53 waveforms that G75 reused.
- **Steps:**
  1. **Library generator** (`opentsense/power/leaklib.py`). For every cell in the IHP typ library and every `leakage_power` state, ngspice solves the leakage at 25, 50, 75, 100 and 125 °C with the pinned PSP103 models. A state with an internal value (Q of a flop or latch) is first set by a capture sequence, then held. A cell without states (tie, decap) is solved once. Five `.lib` files are written. Each equals the shipped file except the leakage values. `cell_leakage_power` is scaled by the cell's mean ratio of new to old state values.
  2. **Per-instance leakage.** For each window and each temperature library, OpenSTA (`report_power -instances`) gives each instance's leakage, weighted by the window's state probabilities.
  3. **Loop** (`opentsense/thermal/electrothermal.py`).
     - The die is gridded 32 × 32 under the `single_die` stack (copper spreader, TIM, 50 µm die), resized to the 617.5 µm die. Its linear operator R comes from PACT's own matrix (`thermal/response.py`).
     - Each instance's leakage is interpolated log-linearly in T between the five libraries and evaluated at its tile's temperature. Above 125 °C it extends the last segment.
     - Tile power is dynamic power (from the same OpenSTA run) plus the summed instance leakage.
     - The iteration T ← T_amb + R·P(T) runs until the largest change is below 1e-10 K, or 500 iterations.
- **Cases (per window k0 to k3):**
  - **nominal:** ambient 300 K, HTC 5e4;
  - **hot:** ambient 358.15 K (85 °C), HTC 5e4;
  - **stress (synthetic, labelled as such):** nominal, with every instance's leakage multiplied by one factor s. s is found by bisection so that ρ at the fixed point is 0.5 ± 0.05. It exists only to test the loop's prediction where the feedback is large, because IHP 130 nm leakage is about 0.02% of power at 25 °C.
- **Pass if all hold:**
  - **(a) Library equals SPICE.**
    - Every state of every cell solves.
    - Every sequential state is verified reached: the state output is within 10% of VDD of its intended level at the end of the measurement.
    - The 8 G53 states, re-solved by the separate hand-written decks in `leak.py`, match the generator within 1% at 25, 50, 75 and 100 °C.
  - **(b) OpenSTA plumbing.**
    - With the shipped library, OpenSTA's design leakage for each window equals G75's run `main` to 6 significant figures.
    - Across the five generated libraries, every instance's dynamic power is identical, and the design leakage rises strictly with temperature.
  - **(c) Loop.**
    - Every nominal and hot case converges to 1e-10 K.
    - On a 1 × 1 grid of the same stack, the loop's fixed point equals an independent scalar root-find (`brentq` on T = T_amb + R·P(T)) within 1e-9 K.
    - For one window (k0, nominal), a full PACT solve at the converged power matches the operator's peak within 0.02 K (PACT writes 0.01 K).
    - For every case including stress, the measured amplification (T* − T_u) ÷ (T_1 − T_u) on the peak tile is within 25% of 1/(1 − ρ). Here ρ is the spectral radius of R·D at the fixed point, D = diag(∂P_leak/∂T) by ±0.5 K central difference, T_u is the fixed-25 °C-leakage solution and T_1 is one iteration from T_u. This is G74's bar (b), unchanged.
- **Reported, not gated:**
  - library ÷ SPICE over every state at 25 °C, extending G53's 8 states to the whole library;
  - leakage share and peak shift per case;
  - design leakage at the fixed point against the shipped 25 °C library;
  - s for the stress case;
  - wall time.
- **A fail means:**
  - (a): the generator mis-sets or mis-measures a state, so fix the sequence and record it.
  - (b): the library edit or OpenSTA's state weighting is not what we assume.
  - (c): the loop or the ρ prediction is wrong at this scale. Record it in `failures.md`.
- **Not claimed:**
  - Internal (switching) power is held at the 25 °C library's values, because IHP ships no other temperature at 1.2 V.
  - Silicon accuracy rests on the PSP103 models.
  - ρ near 1 is not tested, as in G74.
- **Output:** `gates/g92/`

## Amendment 1 (4 Nov 2026, before the gated run)
- **Stack.** The `single_die` geometry is used at the die size, split into sublayers as G71's single stack (spreader 10, TIM 3, die bulk 6), so hotspots converge. File: `configs/stacks/g92_ihp.yaml`.
- **Dry run before the gate (plumbing, not scored).** The generator ran on 4 cells (`dfrbpq_1`, `dllrq_1`, `nand2_1`, `tiehi`; 34 states). The state check first used `find ... at=<end>`, which ngspice skips at some temperatures because the last time point does not land exactly at the end. It now uses the average of the state output over the measurement window. After that fix, all 34 states were reached. Those 4 cells are therefore not blind in (a); the other cells are.
- **Windows.** k0 to k3 are G53's `w0.vcd` to `w3.vcd`, scope `tb/dut`, as G75.
- **G53 states in (a).** `leak.py ihp` re-solves G53's cases: `inv_1` A = 0, 1; `nand2_1` and `nor2_1` 00, 11; and `dfrbp_1` with Q = 0, 1 (CLK low after one capture, D = Q, RESET_B high). Each is matched to the one library state with the same pin values.
- **Instances.** Only instances with a placement in `inst_loc.csv` enter the loop, as in G75's tile maps. Their count is recorded.
- **Stress bisection.** This is over log10 s in [0, 8], at most 60 steps, with up to 5000 iterations per solve. A solve that does not converge counts as ρ too high.

## Amendment 2 (4 Nov 2026, after an aborted start, before any measurement)
- **What happened.** The first launch of `run.sh main` stopped while building decks, before any SPICE solve. The library has a state the parser rejected: one `a221oi_1` state is a sum of products. The script then carried on to OpenSTA on libraries that did not exist. Those outputs are kept in `runs/aborted_1/` and not scored.
- **Sum-of-products states.** The state is expanded into its minterms over the cell's inputs. Each minterm is solved, and the state's value is the mean over them. This is the only such state (1 of the library's 645; "637" was an estimate, corrected after the run), in `a221oi_1`, which has 277 instances.
- **Q and Q_N together.**
  - When a state names both and they are complementary, Q is set and checked.
  - Some latch and flop states have Q = Q_N, which cannot occur. Each such state takes the value of the reachable state with the same Q, and is flagged `q_n_conflict`.
  - OpenSTA weights `when` terms with independent pin probabilities, so these states do receive weight in its sum.
  - None of these cells (`dfrbp`, `dllr`, `dlhr`, `sdfbbp`, `sdfrbp`) is in the ibex netlist. The flagged count is reported.
- **Checked offline before relaunch.** All 650 decks, including minterms, are generated without error.
- **The bars are unchanged.**

## Amendment 3 (4 Nov 2026, after a second aborted start, before any library was written)
- **What happened.**
  - **Hang.** The relaunch was stopped by the host's low-memory guard. The SPICE container kept running, but stalled for over an hour on `a21oi_1`.
  - **Cause.** The library names a combinational cell's output in its states (e.g. `!A1&!A2&!B1&Y`). The generator took that output for a stored state, so it used the 150 ns sequential run for every combinational state.
  - **Orphaned script.** `run.sh` survived the guard. Once the container was stopped it started `leak.py`, which was then stopped too.
  - **Not scored.** No library, OpenSTA output or score was written. The folder is kept as `runs/aborted_2/`.
- **Fix.** A combinational cell uses the 8 ns run, as G53 did. Its named output is still checked against the level its state requires, within 10% of VDD. This is the same check as for flop Q, applied to more states. Only cells with an `ff` or `latch` group use the capture sequence and 150 ns.
- **Robustness.** `run.sh` now stops if the generator or `leak.py` did not finish, instead of continuing to OpenSTA.
- **The bars are unchanged.**

## Amendment 4 (4 Nov 2026, third start stopped for speed, before any library was written)
- **What happened.** The third start ran at about 4 minutes per state, against about 1 second for a state run alone. ngspice starts 8 busy-waiting worker threads per job, so 10 parallel jobs starved each other on 12 cores. It was stopped after about 50 of 650 states, and nothing was written. The folder is `runs/aborted_3/`.
- **Fix.** The generator's ngspice calls set `num_threads=1`. A test state gave the same leakage, to every printed digit, with the default threads and with 1. `leak.py` (the G53 cross-check, 2 jobs) is unchanged.
- **The bars are unchanged.**
