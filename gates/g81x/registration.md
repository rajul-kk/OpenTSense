# G81x registration (written 8 Nov 2026, after G81a failed and before any G81x run)

### G81x: Is G81a's gap the testbench's X injection? (RQ1/RQ2, O1) · REGISTERED → **PASS (8 Nov 2026; see README.md)**
- **Why.** G81a failed on (b): Verilator windows were lower than G72's Icarus windows by up to 1.50% in total (k3) and 3.71% in tile-map L2, while annotation was 100% and the median instance agreed to about 0.15%. The G81a dry run found one systematic difference: the testbench drives `data_rdata` to `32'hx` on every write cycle (`opentsense/power/tb/ibex_tb.v` line 30). Icarus propagates the X and records 0 → x → 0 transitions that a two-state simulator cannot make. **Hypothesis:** this X injection explains G81a's gap. It is a testbench artefact: a real memory port does not drive X.
- **What changes.** One statement. `gates/g81x/ibex_tb_hold.v` is `ibex_tb.v` with `data_rdata <= 32'hx;` removed, so on a write `data_rdata` holds its last read value. Nothing else changes: netlist, models, programs, windows (cycles 1,500–2,500), OpenSTA script, grid.
- **Runs.**
  - **Icarus** (image `opentsense:g71dev`, G72's image), G72's compiled models (`gates/g72/runs/main/sim/models_ibex`) and netlist, k0–k4:
    - with the hold testbench (the new reference);
    - with the original testbench (control).
    - Window runs end at cycle 2,500. Icarus honours `$dumpoff` at 2,500, so the VCD is the same as a run to `IBEX_MAX`.
  - **Verilator** (image `opentsense:g93a`), exactly G81a's build and flags, with the hold testbench: window runs, the `vcd_names.py` map, and function runs to `IBEX_MAX`.
  - OpenSTA power at TT with `opentsense/power/vcd_power.tcl` for all fifteen VCDs, as G72 and G81a.
- **Validity condition (if it fails, the gate is INCONCLUSIVE, not PASS or FAIL):**
  - **(v)** the Icarus control reproduces G72's stored power for k0–k4: design total within 1e-6 relative.
- **Pass if all hold:**
  - **(a) Annotation:** at least 99% of pins annotated, for both simulators, k0–k4.
  - **(b) Power equal on the same testbench:** for each of k0–k4, Verilator (hold) against Icarus (hold): total within 1%, and the 32 × 32 tile map (G72's grid and locations) within 1% relative L2. These are G81a's bars.
  - **(c) Function:** with the hold testbench, Verilator's k0–k3 produce the expected checksums and the done flag, and k4 runs to its limit.
- **Reported, not gated:**
  - the X component of G72's reference: Icarus (hold) against G72, per window, total and tile L2;
  - the share of G81a's gap closed: (Icarus hold − G72) / (Verilator G81a − G72), total and tile L2;
  - Verilator (hold) against Verilator (G81a);
  - per-instance agreement, median and p99;
  - the number of X value changes in each G72 VCD.
- **If PASS:** G81a's gap is the testbench's X injection. Verilator windows with the hold testbench replace Icarus for power. The hold-testbench Icarus numbers supersede G72's as the ibex reference, with G72's X component stated. G81b runs as registered, with the hold testbench (as an amendment).
- **If FAIL:** the X injection does not explain the gap, or not all of it. Record it in `failures.md`. G81b uses G81a's fallback: Icarus windows placed by a Verilator activity timeline.
- **Not claimed:** which `data_rdata` value on writes is physically right (hold is one defined choice; any defined value removes the X). Nothing about cva6 or the TPU.
- **Output:** `gates/g81x/runs/main/`
