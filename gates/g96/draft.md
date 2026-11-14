# G96 draft (13 Nov 2026; NOT registered): the glitch power that zero-delay activity misses (RQ1, plan.md limit 3)

### G96: How much dynamic power, and which tiles, does zero-delay gate-level activity miss? · DRAFT

- **Why.** Every activity window (G72 Icarus, G81 Verilator) is zero-delay: no cell delays, so no glitches. Stated as
  limit 3 in `plan.md`. This gate measures the gap on one Ibex and one TPU window.
- **Routes (dry first).**
  - (b, main) Delay-annotated netlist (`delay_netlist.py`), simulated with the same testbench and zero-delay cell
    models. Each cell output: inertial delay = the cell's fastest arc into it (so pulses shorter than the cell's own
    delay are filtered). Each cell input: transport delay = wire delay to that pin + how much slower its arc is than
    the fastest. A cell with several outputs (adders) is written once per output. Checked on the old Ibex SDF (95,219
    arcs): every single-output arc equals OpenSTA's arc + wire exactly (mean of rise and fall).
    Approximations: (1) a pin pair with several arcs (conditions on other inputs, edges) uses its slowest: 39,634
    faster variants, median 1.6 ps, p99 19.7 ps slower than OpenSTA's state-dependent value, which narrows glitch
    windows slightly (bias: glitch power low); (2) input offsets use the mean of rise and fall; (3) one corner (max of
    each min::max pair). Cost on Ibex: 9.5 s, 55 MB; 19,558 outputs, 50,290 input delays.
  - (a, cross-check) Icarus `$sdf_annotate` with `dry/ibex.sdf`. Icarus lacks interconnect and conditional delays and
    timing checks, and the ASAP7 models' flip-flops depend on timing-check `delayed_*` nets (`power/asap7_models.py`),
    so (a) may not run at all; if it runs, it must agree with (b) on the same window.
- **Metric.** OpenSTA dynamic power (TT) from delay-aware against zero-delay activity of the same window at the same
  clock: total ratio, per-tile ratio map (32 x 32), and toggles per net. Functional check: the window's checksum must
  be correct in both runs.

## Dry findings (13 Nov)

- **SDF:** written from the routed Ibex (`dry/write_sdf.tcl`, ORFS image, 6_final.{odb,sdc,spef}, TT RVT): 17 MB,
  timescale 1 ps, interconnect and cell IOPATH delays.
- **The routed designs do not meet their own clocks at TT** (`dry/reg2reg.tcl`, propagated clock, routed SPEF):

  | Design | SDC clock | Worst reg-to-reg slack, TT (TNS: all paths) | ORFS's own final report (ASAP7 default corner BC = FF libraries) | Clock its reg-to-reg paths meet at TT (I/O not checked here; G99 checks all) |
  |---|---|---|---|---|
  | ASAP7 ibex | 900 ps | -416 ps (TNS -555 ns) | WNS -45.7 ps, TNS -22 ns | about 1.32 ns |
  | ASAP7 TPU | 200 ps | -523 ps (TNS -680 ns) | WNS -351 ps, TNS -425 ns | about 0.72 ns |

  Hold is met (worst +30 to +52 ps). Worst paths: Ibex's `minstret` counter (an asynchronous-reset flop,
  DFFASRHQNx1); the TPU's processing-element partial sums.
- **Why the difference:** ORFS closed timing at its ASAP7 default `CORNER ?= BC` (fast, FF libraries; platform
  `config.mk`), while every power run here uses TT. Even at FF, Ibex misses by 46 ps and the TPU by 351 ps. IHP not checked yet.
- **Consequence for G96:** a delay-aware simulation at the SDC clock would latch wrong values, so both runs (zero-delay
  and delay-aware) must use a clock the design meets at TT (Ibex 1.4 ns, TPU 0.8 ns, proposed), and the comparison is
  per cycle at that clock.
- **Consequence beyond G96 (for the student):** every power map since G72 is OpenSTA power at the SDC clock, which the
  routed designs cannot reach at TT. Per-cycle activity is unaffected, but dynamic power scales with frequency, so
  dynamic power is overstated by about 1320/900 = x1.47 (Ibex) and 720/200 = x3.6 (TPU) against what these layouts
  could run at TT. Leakage is unaffected. Downstream: thermal peaks and leakage-loop margins (G92e, G95) are computed
  at the higher dynamic power, so they are conservative (hotter, smaller margins); estimator results (RQ2) depend on
  the power pattern more than on its level. To decide: state it and rescale, or re-close timing (see goals.md).

## Proposed bars (to fix after route (b)'s dry run on one window)

- (v) Both runs reproduce the window's checksum; route (b)'s delays equal OpenSTA's arc delays (spot check).
- Reported, not gated, is the main output (a measurement, not a pass/fail claim): total and per-tile glitch share.
- Possibly gated: if the glitch share is below a registered threshold (for example 5%) on both designs, limit 3 is
  closed as "measured and small"; above it, the windows need delay-aware activity.
