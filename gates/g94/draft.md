# G94 draft (written 11 Nov 2026; NOT registered): transient agreement across 3D-ICE, PACT and HotSpot (goals.md U6)

### G94: Do the three solvers agree in time, not only at steady state? (O1, RQ2/RQ3) · DRAFT

- **Why.** Steady fields agree within 0.41 K across the three solvers (G93a). The only transient comparison is
  exploratory: a finite-volume plant against 3D-ICE disagreed by 11–14% (G28). G79 (Kalman with an identified
  plant), G44-style recovery in time, the transient leakage loop and any governor study (`ambitions.md` 4, 5) all rest
  on transient truth. G94 runs before G79.
- **Pipeline state, checked 11 Nov.** Steady only: `to_3dice` writes `solver: steady`, `to_pact` sets
  `transient = False`, `run_hotspot` reads the steady grid file. All three solvers have a transient mode:
  - 3D-ICE: `solver: transient step S, slot T;` with `power values` per floorplan element, one value per slot;
  - PACT: only through its `SPICE_transient` solver (ngspice in the image), with `step_size`,
    `total_simulation_time` and `ptrace_step_size`;
  - HotSpot 7: one power-trace row per sampling interval and `-o` for the transient trace; our floorplan is one
    block per cell, so the block trace is the cell grid.
- **Build (before registration).** A transient mode in `to_3dice`, `to_pact`, `to_hotspot` and `thermal/run.py`:
  input = a power sequence `{die: (n_slots, ny, nx)}` and the slot length; output = per-die fields per slot. Unit
  tests on a small stack: a constant power trace reaches the steady field of the existing steady path.
- **Cases (proposed).** The G93a stacks (3D two-die, 2.5D regions, 3D sink below), G71 seed-0 power maps:
  1. **Step:** power on at t = 0, held for at least 5 × the slowest time constant;
  2. **Pulse:** 10 ms on, then off;
  3. **Real timeline:** CPU die driven by a G81b program's window powers (scaled as in G84), TPU die constant.
- **Time-step convergence first (noise floor, `plan.md` §2.1).** For each solver, halve the step until the peak
  rise at every output time changes by less than the floor; the floor is the change between the last two halvings.
  The gated runs use the converged step. Record the floor per solver.
- **Pass if all hold (proposed; numbers fixed after the convergence runs):**
  - **(a) Steady end:** the end of every step case equals each solver's own steady solve within 0.01 K (internal
    consistency of the transient path).
  - **(b) Time constants:** per die, the time to 63% of the step's final rise agrees between every solver pair within
    max(3 × floor, 5%).
  - **(c) Trajectories:** per die, the peak-rise error against time, max over the run, within max(3 × floor, 0.5 K)
    for every pair, on all three cases.
- **Reported, not gated:** RMS error over time per pair; wall time per solver; the G28 finite-volume plant against
  the three, to say whether its 11–14% was the plant or 3D-ICE.
- **A fail means:** transient truth depends on the solver. G79 and any time-domain result must then name its
  solver and carry the measured disagreement as a model error (G87).
- **Not claimed:** HotSpot and 3D-ICE share a discretisation here (G93a), so their agreement checks converters and
  boundaries more than physics; PACT is the independent node placement.
- **Effort.** About 3–4 days: converters and runners 2 days (PACT's SPICE path the riskiest), convergence runs and the
  gate 1–2 days. Laptop CPU; run alone, not alongside G92e.

## Inside the image (16 Nov 2026, task g94-image; opentsense:g93a)

| Solver | Transient path | Found | Consequence for the converters (g94-modes) |
|---|---|---|---|
| 3D-ICE 4.0 | `transient step S, slot T`, Tmap at each slot | One map per slot is appended to the Tmap file, each after a `%` header line: `read_tmaps` reads it as is. The parser turns step and slot into integers by multiplying both by 10 until whole, then divides as `uint32` (`stack_description_parser.y`, `types.h`). Step 3e-4 / slot 1.5e-3 needs 10^20 as doubles, overflows, and runs with a wrong slot length and no error (peak at 1.5 ms read 300.63 K against 301.41 K at 1 ms). | `to_3dice.steps_per_slot` mirrors that arithmetic and refuses such pairs; (0.1, 0.3) is accepted (3 steps), as 3D-ICE computes it. Probe: 1 ms peaks 301.41 / 301.45 K and 3 ms 302.04 to 302.08 K across steps 1e-4 to 5e-4 s; 40 slots of 10 ms end within 1.0 mK of the steady solve. |
| HotSpot 7 | `-o` trace (one row per power-trace row, `sampling_intvl` each); `grid_transient_file` dumps the grid per step | Starts from `init_temp`, default 333.15 K, not ambient. | Set `init_temp` to the stack's ambient (or pass `-init_file`); `sampling_intvl` = slot. Confirm `grid_transient_file` in g94-modes. |
| PACT | `SPICE_transient` (`SPICESolver_transient.py`) | Calls **Xyce**, which is not in the image (ngspice is). Its power PWL holds 0 A until the first trace interval ends, so slot k's power acts during slot k+1 (a one-slot lag). The time regex `([0-9.]+)([a-zA-Z]+)` accepts no exponent: steps must be written as `100us`. Results are the last CSV rows of Xyce `.PRINT TRAN FORMAT=CSV`. | Recommended: keep PACT's own RC network (the independent discretisation G94 needs) and run the netlist it writes with ngspice, after dropping the Xyce-only `.OPTIONS` lines, printing with `wrdata`, and writing the current sources without the lag. Alternative: add Xyce (and Trilinos) to the image, a long build. Either way the change is stated before registration. |
