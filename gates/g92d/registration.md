# G92d registration (written 5 Nov 2026, before the gated run)

### G92d: Gate-level leakage library and electro-thermal loop, staged-continuation settling, IHP SG13G2, ASAP7 RVT and ASAP7 LVT (RQ1, O1) · REGISTERED
- **Why:** G92c failed bar (a) on all three kits; (b) and (c) passed (`gates/g92c/README.md`, `failures.md`).
  - **IHP:** the `dfrbp_1` cross-check missed G53 by −18.7% at 25 °C. G53's reference is `leak.py`'s 150 ns window, the unsettled value G92c set out to replace. G92c's own 150 ns value matches G53 (683.9 against 685.0 pW); the settled value is 567.2 pW. This was a registration error: the reference was not settled.
  - **ASAP7 RVT:** 7 captured states failed the settling test.
    - 6 missed by 1.06–1.29%: the seeded DC value against the 10 ms continuation's end, at 25 °C.
    - 1 (DFFASRHQNx1) flipped to the other stored value in the seeded DC solve.
    - A 100 ms continuation flipped a different state in DC (31% off). Seeded DC on a bistable cell is not a reliable steady state at 25 °C.
    - The G92b regression also failed (max 15%). The claim that the 10 fF shunt cannot move a constant-input value was wrong: these values are 8 ns transient averages, and the 25 °C solve is ill-conditioned. 4,291 of 8,125 states moved by more than 0.1%, 53 by more than 1%; the library total moved by 0.04%.
  - **ASAP7 LVT:** `AOI311xp33_L` with all inputs low, at 125 °C. The transient stopped at its first point (one data row) without printing any abort text, so its measurements read 0.
- **What changes from G92c:** only the library generator (`opentsense/power/leaklib.py`; the registered copy is `gates/g92d/leaklib_g92d_registered.py`, and G92c's is `gates/g92c/leaklib_g92c.py`) and the scorer. The OpenSTA step, the loop, the cases and the stacks are G92c's.
  1. **Staged continuation (captured states).**
     - The capture transient is G92c's, unchanged.
     - At each temperature, with every input constant at its final level, the transient continues (`.ic`, `uic`, Gear) in stages ending at 0.1 ms, 1 ms, 10 ms, 100 ms and 1 s after the capture. Each stage starts from the previous one's end, with a maximum step of 1/100 of its length.
     - **Settled** at the first stage end where |I − I_prev| ≤ max(0.5% · I_prev, 2 pA · VDD). The state's value is the supply current there.
     - Every planned output must hold its level (within 10% of VDD) at every stage end. A lost level, an abort, or no flat stage by 1 s fails the plan.
     - **The 2 pA floor:** the ASAP7 supply current at 25 °C moves in steps of about 0.9 pA (0.635 pW at 0.7 V) from stage to stage. abstol 1e-15 and 1e-16 and vntol 1e-9 leave the steps unchanged (dry run). Two steps are treated as noise. This is about 0.4–0.9% of a 150–250 pW flip-flop state at 25 °C; at 50 °C and above the 0.5% term dominates.
     - **Seeded DC is kept only as a cross-check:** it is seeded from the settled point and reported (agreement and flips), but it is not part of `ok`.
  2. **One retry for constant-input states.** A forced or combinational state whose solve fails is solved once more without its `.nodeset` output hint. The output-level check still applies. Retried states are listed.
  3. **Abort check.** A transient that ends with 0 or 1 data rows now fails the plan, as an abort does.
  4. **The shunt stays at 10 fF** (G92c). G92d's regression is therefore against G92c, which used the same decks.
- **Dry run before registration (plumbing, not scored).**
  - **DFFLQNx1** (RVT, all 10 plans), FLAT 0.5%, no floor: all ok, and no seeded-DC flips. Most temperatures settle by 1 ms; 25 °C settles by 10–100 ms.
  - **DFFASRHQNx1 and DFFLQNx1**, FLAT 0.2%, stages to 10 s (`dry/probe_flat002.log`): 1 of 20 and 3 of 10 captured plans never went flat at 25 °C. Their traces step by about 0.6 pW. For example, DFFLQNx1 reads 152.16 / 153.43 / 153.43 / 152.16 / 153.43 / 154.07 pW from 0.1 ms to 10 s. Hence the floor.
  - **LVT `AOI311xp33_L`**, all inputs low, 125 °C (`dry/probe_stop.py`): as written, with Gear, with a 1 ps step, and with Gear plus gmin, it fails each time. Without the `.nodeset` it gives 12,355 pW with Y held at 0.6999 V. Hence the retry.
  - **Not done:**
    - the probe of the final settings (FLAT 0.5% with the 2 pA floor) on the G92c failures and the validation states;
    - the reltol 1e-6 test;
    - the 100 µs `dfrbp_1` reference.
    The host's low-memory guard stopped all three on 5 Nov. The first gated step for each kit therefore also serves as this check, and the bars below do not depend on its numbers.
- **Cases, steps, windows, thermal set-up, binding and run IDs:** as G92c. `run.sh` defaults to 6 SPICE workers.
- **Pass if all hold, for each of the three kits:**
  - **(a) Library equals SPICE.**
    - G92c's (a): every state planned and solved at all five temperatures, every checked pin within 10% of VDD, unreachable states only through G92b's rule. A constant-input state may use its one retry.
    - For captured states: the 150 ns capture and the staged continuation both succeed, and the state is settled by 1 s.
    - **Cross-check, within 1% at 25, 50, 75 and 100 °C:**
      - IHP: G53's 6 combinational states against `leak.py`.
      - IHP: the 2 `dfrbp_1` states against `ref_dfrbp.py`'s 100 µs value. `ref_dfrbp.py` runs G53's own deck with the clock's 100 ns repeat removed, as one plain transient (no continuation, no `.ic`). It runs as a step of `run.sh`. The reference must itself be flat, with |I(100 µs)/I(10 µs) − 1| ≤ 0.5% at every temperature. If it is not, the cross-check fails.
      - ASAP7 RVT and LVT: `leak.py` INVx1 and NAND2x1, as G92c.
    - **Settling validation:** as G92c, within 1% at 25 °C:
      - IHP `sdfrbpq_1` Q = 1, against 658.0 pW;
      - RVT DHLx1 (!CLK·D·!Q), against 158.59 pW;
      - RVT ICGx1 (CLK·ENA·SE·!GCLK), against 232.32 pW.
    - **Regression against G92c (all three kits):** every state that is neither captured, high-impedance nor retried, and was solved in both runs, is within 1e-6 of its G92c value at every temperature. The decks and solver are the same, so only captured and retried states may move.
  - **(b) OpenSTA plumbing:** G92c's (b), unchanged.
  - **(c) Loop:** G92c's (c), unchanged.
- **Reported, not gated:**
  - the seeded-DC cross-check over captured plans: flips, and the median and maximum |DC/settled − 1|;
  - the stage at which each temperature settled;
  - the retried states;
  - the 150 ns ÷ settled ratio at 25 °C;
  - the shipped ÷ SPICE ratio;
  - design leakage against G92c;
  - ρ, peak shift, the stress factor s and wall time per kit;
  - LVT against RVT on the same design;
  - for the 25 °C ill-conditioned constant-input states (for example `OA333x2`: transient 112 pW against DC 44 pW at 1 fF, and 129 pW against 13,098 pW at 10 fF), the library value is the transient average as before. The size of that spread is stated, not fixed.
- **A fail means:** as G92b. Record any fail in `failures.md` and mark it in `gates.md`.
- **Not claimed:**
  - as G92c;
  - "settled" means flat to 0.5% (or the 2 pA floor) over one decade of time, not a proven steady state;
  - the 25 °C value of the ill-conditioned constant-input states is solver-dependent at the level noted above.
- **Output:** `gates/g92d/runs/main/{ihp,asap7,asap7_lvt}/`

**Amendment 1 (6 Nov 2026, procedure only; no bar, method or setting changed).**
- **The first run was stopped.** On 6 Nov the host's low-memory guard stopped the first gated run during the IHP `ref_dfrbp.py` step. By then the IHP library and the `leak.py` reference had finished and were written: 84 cells, 645 states, 0 not ok.
- **`run.sh` can now resume.** With `RESUME=1` it keeps a library and `leak.py` reference that were written on completion, instead of recomputing them. It also skips `ref_dfrbp.py` when its output exists.
- **Reference workers.** `REF_J` sets the reference's number of parallel workers (2 instead of 4). Each transient is unchanged.
- **One kit at a time.** The kits run separately to fit in memory.
- **Not scored.** The interrupted run's library was not scored or inspected beyond its completion line before this amendment.

**Amendment 2 (6 Nov 2026, the reference's solver setting; no bar changed).**
- **Why.** `ref_dfrbp.py` as registered ran `tran 20p 100000n` with no maximum step. ngspice then caps the step at the 20 ps print step: 5 million steps per transient. After 49 minutes neither of the first two transients had finished, and the 8 were projected to need 10 h or more. The run was stopped (with the user's permission). No reference value had been produced.
- **Change.** The transient may now step up to 1 ns once the edge has passed (`tran 20p 100000n 0 1n`). It uses Gear (`.options method=gear`), because the trapezoidal rule rings at large steps (G92c). The deck, the clock change, the four averaging windows and the bar are unchanged: flat to 0.5% from 10 to 100 µs, and the library within 1% of the 100 µs value.
- **Value seen before the gated run (timing check).** One transient, Q = 0 at 25 °C, took 27 s: 566.0 / 479.1 / 469.2 / 470.4 pW at 150 ns / 1 µs / 10 µs / 100 µs, flat 0.24%. The scored library value was not looked at.
- **Note.** This deck's 150 ns value (566.0 pW, with Gear and a 1 ns maximum step) differs from G53's `leak.py` 150 ns value (685.0 pW, trapezoidal, 20 ps). So at 150 ns the solver setting matters as well as the window. The 150 ns value is not gated.
