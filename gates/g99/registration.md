# G99 draft (registered 13 Nov 2026, before any G99 run): layouts closed at the corner the power runs use (plan.md limit 4, fix forward)

### G99: Do the benchmark designs meet setup and hold at TT, at the clock their power is computed for? · REGISTERED

- **Why.** G96's dry run found that the ORFS ASAP7 layouts were closed at ORFS's default `CORNER ?= BC` (FF libraries),
  while every power map uses TT, so they miss their SDC clocks at TT (Ibex -416 ps at 900 ps, TPU -523 ps at 200 ps;
  `gates/g96/draft.md`). The student chose to fix forward (13 Nov): re-close at TT, regenerate the windows, use the
  new layouts from the benchmark on. Recorded gates keep the old layouts (limit 4).
- **What changes, and only that.** Same ORFS image (`openroad/orfs:latest`, id 55266bc72fd6), same design configs
  (`designs/asap7/{ibex,tpu}/config.mk`), same RTL. Two overrides: `CORNER=TC` (ASAP7's typical corner, `*_TT_nldm` libraries; see correction), and `SDC_FILE` = a copy of the stock
  constraint with `clk_period` changed. New `WORK_HOME` (`_build/g99/asap7-<design>`), so old layouts stay untouched.

  | Design | Old clock | Met at TT on the old layout | G99 clock  | Fallback, once, if setup fails |
  |---|---|---|---|---|
  | ASAP7 ibex | 900 ps | about 1,320 ps | 1,400 ps | 1,550 ps |
  | ASAP7 TPU | 200 ps | about 720 ps | 800 ps | 900 ps |
  | IHP ibex (checked, not re-run) | 8.0 ns | ORFS report at typ: WNS -0.26 ns (3%) | stays; stated | none |

  Reference: ORFS ships its own `pos_slack` Ibex variant at 1,468 ps (at BC), so 1.4 ns at TT is plausible, not certain.
- **Cost.** About 3.5 h serial compute (old runs: Ibex detailed routing 2 h 08 min, TPU about 1 h in all; peak RAM 3.8 GB
  Ibex, 6.7 GB TPU, both in detailed routing), one heavy slot per design (see corrections).

## Bars (per ASAP7 design)

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

## Procedure (fixed)

- `launch.sh <design> <ps>` (host; runs `run_g99.sh` in the ORFS image), one design at a time, a heavy slot of 4.5 GB
  (Ibex) or 7.5 GB (TPU) and the same container cap; `make` has a 4 h timeout.
- Order: Ibex 1,400 ps, then TPU 800 ps. A design whose bar 1 (setup) fails is re-run once at its fallback clock; that
  run is the result. A slower clock cannot fix hold, so a bar 2 (hold) failure, or a failed fallback, makes G99 FAIL
  for that design and the student decides.
- Bars 1-3 read from the run's own reports plus `reg2reg.tcl` (TT, RVT for Ibex; RVT LVT SLVT for the TPU). Bar 4
  runs after windows are regenerated on the new netlist.

## Correction before any result (13 Nov, 16:10)

The first launch used `CORNER=TT`, which ASAP7's `platform config.mk` does not define (its corners are BC, TC and WC);
yosys stopped in its first second with an empty library list, producing no layout or timing. The typical corner is
`TC`, which loads the `*_TT_nldm` libraries the power runs use. `run_g99.sh` now passes `CORNER=TC`; nothing else
changed. The empty work folder `asap7-ibex-1400` was deleted before the re-run.

## Correction, memory (13 Nov)

The draft's "peak RAM at most 1.4 GB" was wrong: the old runs' detailed routing peaked at 3.8 GB (Ibex, 2 h 08 min)
and 6.7 GB (TPU, 19 min). The first Ibex run under a 1.6 GB container cap was killed in detailed routing (70%,
before any final layout or timing existed); stages up to global routing were kept and `make` resumes from there.
Slots from here: Ibex 4.5 GB, TPU 7.5 GB, container caps the same. No bar changes.

## Correction, review (13 Nov, before any result)

/code-review of the gate folder: the override line, cost and slot lines above now match the corrections; the
fallback applies to setup only (hold was listed by mistake: a slower clock cannot fix it); `run_g99.sh` checks its
arguments, writes a summary row on every exit and has a 4 h timeout; inst_loc.csv and power come from the package's
`opentsense/power/extract.tcl` (with `OUT_DIR`), not an older copy; `launch.sh` copies both into the build folder so
what ran is what is in the repo. No bar changed.
