# G96 registration (written 15 Nov 2026, before the gated run; method and dry runs in `draft.md`)

### G96: How much dynamic power does zero-delay activity miss? (RQ1, `plan.md` limit 3) · REGISTERED

- **Why.** Every activity window is zero-delay, so glitches are never simulated (limit 3). This measures the gap on
  one Ibex and one TPU window, on G99's layouts (closed at TT, so a delay-aware run at their clock latches correctly).
- **Set-up.** Per design, two Icarus runs that differ only in the netlist:
  - **zero-delay:** the routed `6_final.v`; **delay-aware:** the same netlist through `delay_netlist.py` (route (b) in
    `draft.md`) from OpenSTA's SDF of that layout (`dry/write_sdf.tcl`: TT, routed SPEF; Ibex RVT, TPU RVT LVT SLVT).
  - Same cell models (pristine ASAP7 Verilog from the pinned ORFS image with G72's functional patch), same testbench,
    same clock (half the SDC period) and the same input time `+in_ps` = the SDC's clock latency + input delay (Ibex
    161.775 + 280 → 442 ps at 1.4 ns), so the only difference is the delays.
  - Windows: Ibex matmul k0, cycles 1500-2500 (run to 16,000 cycles for the checksum); TPU W1, cycles 600-1600 (after
    G99 passes the TPU).
  - OpenSTA power at TT on the routed layout for each VCD (`opentsense/power/vcd_power.tcl`), 32 × 32 tiles as G72.
  - `run.sh <design> <ps>`; `evaluate.py`.
- **Noise floor.** Both runs are deterministic (Icarus, fixed inputs; G72 reproduced every instance's power exactly),
  so repeat spread is 0. The decision threshold below is therefore not limited by noise; the stated bias is the model's.
- **Pass (validity) if all hold, per design:**
  - **(a)** Both runs reproduce the window's reference result (Ibex k0 checksum `00031a38` with `done`; TPU W1 616 rows,
    all equal to the reference).
  - **(b)** The converter maps every SDF instance and cuts every output it names (its own counts: 0 missing, 0
    unparsed).
  - **(c)** Annotation ≥ 99% of pins in both VCDs.
- **Measured (the result):** glitch share = (P_dyn,delay − P_dyn,zero) / P_dyn,delay for the window total, where P_dyn is
  OpenSTA internal + switching power; the same per tile (32 × 32 map, tiles with ≥ 0.1% of the total); total toggles
  in each VCD.
- **Decision rule (fixed now).** If the glitch share of the total is below 5% on both designs, limit 3 is closed as
  "measured and small" and the zero-delay windows stand. At 5% or above on either design, the limit stays, the share
  is reported with every power result that uses that design, and the student decides whether delay-aware windows
  replace zero-delay ones.
- **Validity.** INCONCLUSIVE if (a), (b) or (c) fails for a reason other than the delays (for example a tool crash);
  a delay-aware run that latches wrong values at a clock G99 met is a FAIL of route (b) and is recorded in
  `failures.md`.
- **Reported, not gated.** Per-tile share map; where the largest shares are (cell types); route (a) (Icarus
  `$sdf_annotate`) only if it runs, as a cross-check.
- **Not claimed.** The bias of route (b) is towards less glitch power: a pin pair with several arcs uses its slowest
  (39,634 variants on the old Ibex, median 1.6 ps slower), input offsets use the mean of rise and fall, and OpenSTA
  counts every toggle as full swing. One corner (TT), one window per design.
- **Code and output.** `run.sh`, `evaluate.py`, `delay_netlist.py`, `dry/`; output in `runs/<design>-<ps>/` (VCDs in
  `_build/g96/`), records in `record/<design>-<ps>/`.

Amendments go below, dated, each with the reason. Never re-run until it passes.

## Run 1 (15 Nov, `runs/ibex-1400`): INCONCLUSIVE on (c)

(a) and (b) held (checksum `00031a38` in both runs; converter 0 missing, 0 unparsed). (c) failed: the delay-aware VCD
annotated 95.5% of pins (65,251 of 68,306) against 100% zero-delay; raw glitch share 19.2%. Kept as run, unchanged.

## Amendment 1 (15 Nov 2026, AFTER run 1; found by investigating the (c) failure)

- **Cause.** OpenSTA takes pin activity only from the cell-instance scopes of the VCD (a nets-only VCD annotates just
  the 264 port pins). In the delay netlist a cell's own output pin is the signal *before* its inertial delay, so it
  carries pulses the delay filters (biasing glitch power high), and the multi-output cells are split into copies
  `<name>_g96_<pin>` that match no instance (the 3,055 unannotated pins: 678 adder cells' A, B, CI, CON, SN).
- **Fix.** A view of the delay-aware VCD for OpenSTA (`delay_netlist.py view`, `sta_view`): every output pin variable
  points at the net it drives, after the delay (228 outputs that drive one bit of a vector net get a 1-bit variable
  taken from the vector's changes), and the copies are merged back under their instance name. Value changes are copied
  unchanged; the simulation is not re-run. `run.sh` runs the view; the raw VCD's power is reported as `delay_raw`.
- **Validation.** The same netlist with every delay removed (`#` delays dropped, transport copies made plain assigns),
  simulated, put through the view with the delay netlist's assigns (18,608 outputs re-pointed, 228 vector bits, 678
  copies merged) and read by OpenSTA, equals the zero-delay run: same total (4.46855044 mW), max per-instance
  difference 3e-21 W over 48,800 instances, annotation 100%. A first version of the view gave every bit of a vector
  the same new variable (16.8 mW); this test and the per-instance comparison caught it before any result was taken.
- **Bars unchanged.** The decision is unchanged too: run 1's raw share (19.2%) and the amended share are both above 5%,
  so limit 3 stays either way.
- **Re-evaluation** of the same VCDs: `runs/ibex-1400-a1`.
- **Not comparable across gates:** G96's zero-delay baseline uses `+in_ps=442` (inputs at the SDC time); G100's k0 uses
  0, and finishes one cycle earlier, about 0.5% different in total power. G96 is self-consistent.
- **Threshold note.** The 5% threshold was fixed in this registration on 15 Nov; the run started before the student
  had replied to the offer to change it.

## Result, Ibex 1400 ps (Amendment 1, `runs/ibex-1400-a1`): valid on (a), (b), (c)

| | Zero-delay | Delay-aware (view) | Delay-aware, raw VCD (reported) |
|---|---|---|---|
| Dynamic power, k0 window | 4.466 mW | 5.235 mW | 5.531 mW |
| Annotation | 100% | 100% | 95.5% |
| Glitch share of dynamic power | | **14.7%** | 19.2% |

Value changes in the simulator's VCD: delay-aware 1.72× zero-delay. Per tile (325 tiles with ≥ 0.1% of power):
median 7.9%, max 79%. 14.7% is above the 5% threshold, so **limit 3 stays** (decision rule); the TPU (W1) follows.

**Amendment 2 (15 Nov 2026, after the ibex-1400-a1 evaluation; review fix).** Validity bar (b) now also requires that
`view.log`'s re-pointed output pins equal `convert.log`'s outputs cut. An output pin left un-re-pointed keeps its
pre-delay activity while annotation still reads 100%. ibex-1400-a1 was re-evaluated from its saved outputs (no
re-simulation): 18,608 = 18,608, and every summary field is unchanged (glitch share 14.7%). `sta_view` now fails
loudly on a driven net it cannot find. Its synthesised ids come from a counter, and a regenerated view is
byte-identical to the one scored.
