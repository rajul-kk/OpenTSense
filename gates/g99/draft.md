# G99 draft (13 Nov 2026; NOT registered): layouts closed at the corner the power runs use (plan.md limit 4, fix forward)

### G99: Do the benchmark designs meet setup and hold at TT, at the clock their power is computed for? · DRAFT

- **Why.** G96's dry run found that the ORFS ASAP7 layouts were closed at ORFS's default `CORNER ?= BC` (FF libraries),
  while every power map uses TT, so they miss their SDC clocks at TT (Ibex -416 ps at 900 ps, TPU -523 ps at 200 ps;
  `gates/g96/draft.md`). The student chose to fix forward (13 Nov): re-close at TT, regenerate the windows, use the
  new layouts from the benchmark on. Recorded gates keep the old layouts (limit 4).
- **What changes, and only that.** Same ORFS image (`openroad/orfs:latest`, id 55266bc72fd6), same design configs
  (`designs/asap7/{ibex,tpu}/config.mk`), same RTL. Two overrides: `CORNER=TT`, and `SDC_FILE` = a copy of the stock
  constraint with `clk_period` changed. New `WORK_HOME` (`_build/g99/asap7-<design>`), so old layouts stay untouched.

  | Design | Old clock | Met at TT on the old layout | G99 clock (proposed) | Fallback, once, if WNS < 0 |
  |---|---|---|---|---|
  | ASAP7 ibex | 900 ps | about 1,320 ps | 1,400 ps | 1,550 ps |
  | ASAP7 TPU | 200 ps | about 720 ps | 800 ps | 900 ps |
  | IHP ibex (checked, not re-run) | 8.0 ns | ORFS report at typ: WNS -0.26 ns (3%) | stays; stated | none |

  Reference: ORFS ships its own `pos_slack` Ibex variant at 1,468 ps (at BC), so 1.4 ns at TT is plausible, not certain.
- **Cost.** About 3 h serial compute (old runs: Ibex longest stage 54 min, TPU 30 min; peak RAM at most 1.4 GB), one
  medium slot per design, heavy lock.

## Proposed bars (per ASAP7 design)

1. Setup: worst reg-to-reg and I/O slack >= 0 at TT on the final routed layout (`gates/g96/dry/reg2reg.tcl` and ORFS's
   `6_finish.rpt`, propagated clock, routed SPEF).
2. Hold: worst slack >= 0 at TT.
3. Routing DRC: 0 violations (`5_route_drc.rpt`); LEC passes where ORFS runs it (Ibex; the TPU config sets
   `LEC_CHECK = 0`).
4. Function: the gate-level window simulation (G72 testbench) reproduces the reference checksum on the new netlist.
5. Reported, not gated: area, cell count, utilisation, and power at the new clock against the old layout's power at
   its old clock and at the new clock (the size of limit 4's effect).

## After G99 (separate gate, G72's procedure)

Regenerate the activity windows and power maps on G99's layouts at their clocks; G96 measures glitch power on them.
