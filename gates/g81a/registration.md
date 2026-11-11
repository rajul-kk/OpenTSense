# G81a registration (written 8 Nov 2026, before any gated run)

### G81a: Verilator power windows equal Icarus power windows on the routed ASAP7 ibex (RQ1/RQ2, O1) · REGISTERED
- **Why.** Real activity is the testbed's weakest input (see "Activity gap" below). Fixing it needs gate-level traces of whole programs: millions of cycles, with real phase timing. Icarus runs the routed ASAP7 ibex at about 32 cycles/s (G72: 30,000 cycles in 930 s), so a 2-million-cycle Embench run would take about 17 h per benchmark. Verilator runs the same netlist about 90× faster and matches Icarus to 0.2% of toggles (G49). But its VCDs annotate only 77,847 of 418,528 pins in OpenSTA, and its window power is 8% off (cva6 in G52, `_build/g52/pw_verilator/pw_k0.txt`: 93.6 against 86.4 mW). G81b (long programs) and G81c (real timelines in the recovery testbed) both need Verilator windows that OpenSTA reads as it reads Icarus's.
- **Activity gap (the reason for G81a–c).**
  - The recovery experiments' power comes from 4 short ibex kernels (about 1,000-cycle windows) and 3 TPU stimuli. These are tiled onto 13 × 13 and 10 × 10 core grids by a random phase generator (`experiments/code/sens/g42.py` `phase_maps`).
  - Phase durations are drawn at random (log-uniform, about 1–200 ms) and CPU/TPU pairing is random.
  - The kernels move ibex dynamic power by only 11% (`goals.md` §2b). There are no idle (WFI) phases, and memory power does not follow the workload.
- **What is built.**
  - A Verilator gate-level build of the routed ASAP7 ibex: the G72 netlist and testbench, with the G49 Verilator-compatible ASAP7 models (UDP cells replaced by behavioural equivalents).
  - Every cell-pin net is made visible in the trace (public nets and/or no inlining). The flags are chosen in a dry run on window k0 only.
  - A name map from Verilator's VCD scope to the `tb/dut` instance names OpenSTA expects, if one is needed.
  - Run on G72's five windows: ibex k0–k4, cycles 1,500–2,500, same plusargs and `IBEX_MAX`.
  - OpenSTA power at TT with `opentsense/power/vcd_power.tcl`, exactly as G72 step 3.
- **Reference.** G72's stored Icarus results (`gates/g72/runs/main/power/ibex_k*.txt`), produced from the same netlist, models and windows. They are not rerun.
- **Image.** `opentsense:g93a` (Verilator 5.032, Icarus) for simulation; the pinned ORFS image (`docker/versions.env`) for OpenSTA. Both image ids are recorded in the manifest.
- **Pass if all hold:**
  - **(a) Annotation:** for each of k0–k4, OpenSTA reports at least 99% of pins annotated from the Verilator VCD (Icarus: 100%).
  - **(b) Power equals Icarus:** for each of k0–k4:
    - total power within 1% of G72's;
    - the 32 × 32 tile map (`maps.tile_map`, G72's grid and locations) within 1% relative L2 of G72's.
    - Per-instance agreement is reported, not gated. G49 found 0.2% of toggles differ between the two simulators (zero-delay event ordering), so exact per-instance equality is not expected.
  - **(c) Function:** k0–k3 produce the expected checksums (`workloads.ibex_expected`) and set the done flag. k4 (sleep) runs to its cycle limit, as in G72.
- **Reported, not gated:**
  - Verilator cycles per second and its speed-up over Icarus on this netlist;
  - build time and memory;
  - the flags and name map used;
  - window k0, used in the dry run, reported apart from k1–k4, which were not seen while choosing flags.
- **A fail means:** Verilator windows cannot replace Icarus for power on this netlist with the flags tried. Record it in `failures.md`. G81b then falls back to Icarus windows placed by a Verilator activity timeline: fewer windows, the same bars.
- **Not claimed:** anything about cva6 or the TPU (same method, separate check); timing-accurate activity (both simulators are zero-delay functional, as in G72).
- **Output:** `gates/g81a/runs/main/`

**Amendment 1 (8 Nov 2026, before the scored run; no bar changed). Method fixed in the dry run on window k0 (`dry/`, `dry/dry.log`).**
- **Flags.** `--trace-underscore`. Verilator leaves out of its trace every net whose name starts with `_`, which is most of Yosys's internal nets: 3,529 nets at the `dut` level against Icarus's 20,392. `--public-flat-rw` changed nothing (the same 21% annotation) and is not used.
- **Window runs end at the window end** (`+max = win_start + win_len`). Verilator ignores the testbench's `$dumpoff`, so a run to `IBEX_MAX` dumps every cycle after the window start. On k0, power was then averaged over 28,500 cycles, most of them after the program had finished: −7.4%. The checksum and done flag (bar c) come from a second run of the same binary to `IBEX_MAX`, with its VCD discarded. The testbench is unchanged.
- **Name map** (`vcd_names.py`, header only). An instance name containing a backslash, the ALU's hierarchical Han–Carlson adder, is written with its backslash doubled (`\\`), as Icarus writes it. Escaped net names get their leading backslash back. Without it, all 1,252 pins of that adder were unannotated.
- **Dry-run values on k0, seen before scoring.** 70,206 of 70,206 pins annotated; total power 7.0738 mW against G72's 7.0887 mW (−0.21%). The tile map was not computed. k0 stays in the scored set, as the registration already says, and is reported apart from k1–k4.
- **Found in the dry run (reported, not gated).** Icarus's reference VCD carries 0 → x → 0 transitions that Verilator, a two-state simulator, cannot produce. The testbench drives `data_rdata` to `x` on every write cycle, and Icarus propagates it. On k0 this is about 1.7% of toggles on common nets (Verilator / Icarus = 0.983). G72's reference power therefore includes a small X-transition component.
