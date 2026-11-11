# G92e registration (written 8 Nov 2026, before the gated run)

### G92e: Gate-level leakage library and electro-thermal loop, stage current averaged over a window, IHP SG13G2, ASAP7 RVT and ASAP7 LVT (RQ1, O1) · REGISTERED
- **Why:** G92d failed bar (a) on IHP and ASAP7 RVT; LVT passed, and (b) and (c) passed on all three (`gates/g92d/README.md`, `failures.md`).
  - **ASAP7 RVT:** 2 of 8,576 states (`SDFHx3`, no instances in ibex) never went flat by 1 s at 25 °C. Their stage-end currents alternate by 1.9–2.6 pW (e.g. 238.11, 242.56, 240.65, 242.56, 240.65 pW), above both the 0.5% and the 2 pA · VDD floor. The stage value is the **last point** of a Gear transient taken at large steps, and that point carries step-to-step noise.
  - **IHP:** the `dfrbp_1` reference (G53's deck as one plain transient to 100 µs) was not itself flat from 10 to 100 µs (up to 1.14%), so the cross-check failed by rule.
  - **Found in G92d:** G92c had silently written shipped Liberty values for 4 unsolved cells (one of them `DFFASRHQNx1`, 1,665 ibex instances). The library generator kept "unsolved" only as a missing flag.
- **What changes from G92d:** only the library generator (`opentsense/power/leaklib.py`; registered copy `gates/g92e/leaklib_g92e_registered.py`; G92d's is `gates/g92d/leaklib_g92d_registered.py`), the `dfrbp_1` reference's length, the abort check in `leak.py`, and the scorer. The capture transient, the stages, FLAT (0.5%), the 2 pA floor, the retry, the abort check, the 10 fF shunt, the OpenSTA step, the loop, the cases and the stacks are G92d's.
  1. **Stage current averaged over a window.** A stage's supply current is the time-weighted (trapezoidal) mean of i(vdd) over the last 10% of the stage (`TAIL = 0.1`). That window holds at least 10 solver steps, because the maximum step is 1/100 of the stage. The `.ic` seeds for the next stage, the planned-level check and the seeded-DC cross-check still use the last point. With `TAIL = 0` the code reproduces G92d exactly (dry check below).
  2. **Explicit outcomes (no change of values).**
     - Per temperature, a captured plan is `settled`, `not_flat`, `level_lost`, `aborted` or `no_capture`.
     - Per plan: `settled`, `capture_failed` or `settle_failed` for captured plans; `solved`, `solved_on_retry` or `failed` for constant-input plans.
     - Per cell: `solved`, `kept_shipped` (some state not ok, so the cell's shipped values are written) or `skipped` (no SPICE subcircuit).
     - `leak_states.json` lists `kept_shipped`, and the generator prints it. G92d recorded these outcomes only as a free-text tail and a `solved` flag.
  2b. **Abort check in the `leak.py` cross-check reference.**
     - `leak.py` accepted a case once it found the right number of measurements, so an aborted analysis, which prints zeros, would have counted as solved. This is the bug leaklib fixed in G92c.
     - It now fails a case on abort text, and also when an IHP transient stopped at its first point. The outcome is recorded as `aborted` or `missing`.
     - On a clean run it changes no value (dry check below).
  3. **`dfrbp_1` reference to 1 ms.** The same deck and solver settings as G92d Amendment 2 (Gear, maximum step 1 ns), run to 1 ms. Windows are the mean over the last 5% before 150 ns, 1 µs, 10 µs, 100 µs and 1 ms. Flatness is |I(1 ms)/I(100 µs) − 1|, and the bar stays 0.5%. **Why:** the G92d values do not depend on the solver (`dry/ref_probe.log`: reltol 1e-5 and a 0.1 ns maximum step give the same numbers within 0.05%), and some still drift monotonically at 100 µs (Q = 0, 50 °C: 1,075.1, 1,078.2, 1,082.4 pW at 10, 30, 100 µs). That is slow settling, not noise, so the reference has to run longer. The library's own captured states settle at the 1 ms stage on IHP (G92d).
- **Dry runs before registration (plumbing, not scored; `dry/`).**
  - `probe2.log` (G92d's two SDFHx3 failures, 25 °C, stages to 1 s, no early stop):
    - Last point: the traces alternate as in G92d.
    - Last-10% mean: 257.47, 252.73, 253.24, 252.02, 252.45 pW and 237.07, 241.77, 242.04, 240.99, 241.96 pW. Both settle at 10 ms under G92d's FLAT and floor.
    - reltol 1e-6 also settles them, but took 4,551 s and 22,526 s for 2 plans at one temperature, so it is not used.
    - The probe's window mean did not interpolate at the window start. The registered code does, so values can differ from the probe in the last digit.
  - `check_writelib.py`: the refactored `write_lib` reproduces G92d's 55 libraries and G92c's RVT 25 libraries byte for byte from their own `leak_states.json`. It names G92c's 4 kept-shipped cells and G92d's `SDFHx3`.
  - `check_solve.py`:
    - with `TAIL = 0`, IHP `dfrbp_1` (12 plans, 4 forced and 8 captured, 5 temperatures) equals G92d exactly;
    - SDFHx3's two states at 25 °C end `settle_failed` / `not_flat` with `TAIL = 0`, and `settled` with `TAIL = 0.1`.
  - `leak.py` with the abort check, rerun for IHP and ASAP7 (`dry/leak_check_*.json`, `dry/leak_check.log`, 8 Nov): IHP 8 of 8 and ASAP7 9 of 9 cases solved, none flagged; every value equals G92d's `leak_ref.json` exactly (max relative difference 0.0), same cases
  - `ref_probe_1ms.log`: REFPROBE_RESULT
- **Cases, steps, windows, thermal set-up, binding and run IDs:** as G92d. `run.sh` defaults to 6 SPICE workers; kits run one at a time (G92d Amendment 1).
- **Pass if all hold, for each of the three kits:**
  - **(a) Library equals SPICE.**
    - G92d's (a): every state planned and solved at all five temperatures, every checked pin within 10% of VDD, and unreachable states only through G92b's rule. A constant-input state may use its one retry. A captured state must settle by 1 s.
    - **No cell kept shipped:** `kept_shipped` is empty.
    - **Cross-check within 1% at 25, 50, 75 and 100 °C:**
      - IHP: G53's 6 combinational states against `leak.py`.
      - IHP: the 2 `dfrbp_1` states against `ref_dfrbp.py`'s **1 ms** value. The reference must be flat, with |I(1 ms)/I(100 µs) − 1| ≤ 0.5% at every temperature, or the cross-check fails.
      - ASAP7 RVT and LVT: `leak.py` INVx1 and NAND2x1, as G92d.
    - **Settling validation:** as G92d, within 1% at 25 °C (IHP `sdfrbpq_1` 658.0 pW; RVT DHLx1 158.59 pW; RVT ICGx1 232.32 pW).
    - **Regression against G92d (all three kits):**
      - Every constant-input state that is neither captured, high-impedance nor retried, and was solved in both runs, is within 1e-6 at every temperature (same decks and solver).
      - **New:** every captured state solved in both runs is within max(1%, 2 · 2 pA · VDD) of its G92d value at every temperature. That is 1% for IHP above about 480 pW, and 2.8 pW for ASAP7. Only the stage current's definition changed, and the last point it replaces moves by up to the 2 pA floor per stage.
  - **(b) OpenSTA plumbing:** G92d's (b), unchanged.
  - **(c) Loop:** G92d's (c), unchanged.
- **Reported, not gated:**
  - as G92d (seeded-DC cross-check, stage settled per temperature, retries, the 150 ns ÷ settled ratio, shipped ÷ SPICE, design leakage, ρ, peak shift, the stress factor s, wall time, LVT against RVT);
  - plan outcome counts;
  - the captured-state regression's median and maximum;
  - the `dfrbp_1` reference at every window;
  - design leakage against G92d.
- **A fail means:** as G92b. Record any fail in `failures.md` and mark it in `gates.md`.
- **Not claimed:**
  - as G92d;
  - "settled" still means flat to 0.5% (or the floor) over one decade of time, now on a window mean;
  - the window mean does not remove a real drift; it only removes step-to-step noise at the last point.
- **Output:** `gates/g92e/runs/main/{ihp,asap7,asap7_lvt}/`
