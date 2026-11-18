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
| HotSpot 7 | `-o` trace (one row per power-trace row, `sampling_intvl` each); `grid_transient_file` dumps the grid after each row | Starts from `init_temp` (default 333.15 K; `to_hotspot` already sets ambient). **Every capacitance is multiplied by `C_FACTOR` = 0.333**, "fitting factor to match floworks (due to lumping)" (`temperature.h`, `RCutil.c` getcap): on a small stack HotSpot's peak rise at 12 ms read 7.77 K against 3D-ICE's 5.60 K, and 5.58 K with cv / 0.333. The transient dump prints 2 decimals (0.01 K). | Done in g94-modes: `to_hotspot` writes cv / C_FACTOR (steady results unchanged), one trace row per slot, `run_hotspot(transient=)` reads the per-row grid dumps. Image patch amendment 2 prints the transient dump with 6 decimals (built as opentsense:g94a, 16 Nov; solver tests pass in it). |
| PACT | `SPICE_transient` (`SPICESolver_transient.py`) | Calls **Xyce**, which is not in the image (ngspice is). Its power PWL holds 0 A until the first trace interval ends, so slot k's power acts during slot k+1 (a one-slot lag). The time regex `([0-9.]+)([a-zA-Z]+)` accepts no exponent: steps must be written as `100us`. Results are the last CSV rows of Xyce `.PRINT TRAN FORMAT=CSV`. | Done in g94-modes (16 Nov): `run.pact_transient` keeps PACT's own network, its conductance matrix A captured from one steady PACT run and its node capacities C = cv x cell volume as `Solid.py` sets them (the 1 nm `NoPackage` sink film is PACT's last node layer), and integrates C dT/dt + A T = P by backward Euler at the given step, from ambient, with no lag. A long constant run ends at PACT's steady solve (in-image test). Xyce and the netlist are not used. |

### Seen before registration (16 Nov 2026, small plumbing stack, not a G94 case)

Step response of `tests/test_solvers.small` (16 x 12 cells, one die, 0.5 W with a 4x hotspot), slot 1 ms, step 0.1 ms; peak rise at 1 / 2 / 4 / 12 ms: 3D-ICE 3.44 / 4.03 / 4.46 / 5.60 K, HotSpot 2.90 / 3.77 / 4.41 / 5.58 K, PACT 2.92 / 3.57 / 4.06 / 5.22 K. HotSpot and PACT agree early and 3D-ICE reads about 0.5 K higher at 1 ms; PACT ends 0.18 K below the others at steady (its steady offset, G93a). Wall time 0.1 / 0.4 / 2.9 s. These are known before the bars are fixed, and the registration must say so.

### Student decision needed before registration

Two of the three transient paths are partly ours: HotSpot with its capacitance fitting factor undone (not stock HotSpot), and PACT's network integrated by our backward Euler with capacities computed as PACT's Solid.py does (not PACT's Xyce path; not yet compared with PACT's own C array). So "three solvers agree in time" means "three discretisations agree". Options: accept that wording; or also report stock HotSpot (C_FACTOR kept) and PACT's netlist run in ngspice beside them. Before any bar is fixed, a uniform-power 1-D transient against a fine 1-D reference must say which side the 0.5 K early gap is on. G94 is not run unattended.

### Which side is right early on (16 Nov 2026, task g94-1d; `dry/one_d.py`, output `dry/one_d.txt`)

*Note (16 Nov 2026, after review):* `one_d.txt` was made in `opentsense:g93a`, whose HotSpot transient dump has 2 decimals (its HotSpot row is rounded to 0.01 K). Rerun unchanged in `opentsense:g94a` (6 decimals): `dry/one_d-g94a.txt`. HotSpot moves by at most 0.005 K (1.195 against 1.190 K at 1 ms); the other rows are identical, and nothing below changes.

Uniform 0.5 W on the small stack makes the problem 1-D, so a fine 1-D reference (each sublayer split 20 times,
Crank-Nicolson, 1 us steps) stands for the truth. Mean source-layer rise at 1 / 2 / 4 / 12 ms: reference 1.439 /
1.841 / 2.182 / 3.148 K; 3D-ICE 1.446 / 1.872 / 2.225 / 3.176 (within 2% throughout); HotSpot 1.190 / 1.710 / 2.190 /
3.160 (17% low at 1 ms, close from 4 ms); PACT 1.224 / 1.660 / 2.037 / 3.001 at a converged step (15% low at 1 ms and
still 5% low at 12 ms). PACT's step does not explain it (0.1, 0.01 and 0.001 ms agree to 0.03 K), so the early gap is
in HotSpot's and PACT's networks (node placement in thin layers), not in the integrators. 3D-ICE is the reference side
for G94's early-time bars; the registration states this before any run.
