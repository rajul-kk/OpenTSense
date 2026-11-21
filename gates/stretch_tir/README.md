# Goal 14 (stretch, ungated): Ibex's timing and IR drop at its temperature in the two-die 3D stack

Not a gate: no bar was registered, so this reports a measurement, not a verdict. Run (17 Nov 2026):
`derate_probe.py` in `opentsense:g94b` (ngspice, ASAP7 TT BSIM-CMG models), then `bash gates/stretch_tir/run.sh`
(OpenSTA and PDNSim in the pinned ORFS image) and `evaluate.py`. Outputs: `runs/derate.json`, `runs/cases.txt`,
`runs/<case>/sta_ir.log` and voltage files, `runs/result.json`. `runs/` is git-ignored (about 28 MB, mostly the
voltage maps); `record/` keeps a copy of everything above except the voltage files, so each `runs/...` path below
is also at `record/...`.

## Inputs

- **Design.** G99's routed ASAP7 Ibex at 1,400 ps (TT, RVT), G100's activity window k3 (G97's worst VDD drop), the
  same loading as G96/G97 (`gates/g96/dry/load_routed.tcl`).
- **Temperatures.** Ibex is the bottom die of G93a's two-die 3D stack (TPU over Ibex). From G93a's 3D-ICE fields
  (`gates/g93a/runs/main/3d_fields.npz`, worst of seeds 0-3, ambient 300 K): peak 79.77 C, mean 58.01 C
  (`runs/cases.txt`). The whole die is set to one temperature: OpenSTA and PDNSim take no per-cell temperature, so
  the peak case is a bound and the mean case a middle estimate.
- **Cell delay against temperature.** ASAP7's Liberty has one temperature per corner (TT is 25 C), so the delay
  factor is measured: fan-out-4 chains of INVx1 and NAND2x1 in ngspice at 0.7 V, TT, 0 to 125 C (`runs/derate.json`).
  Delay rises with temperature (no temperature inversion at this voltage): x1.054 at the peak, x1.034 at the mean
  (the larger of the two cells, interpolated). FO4 delay at 25 C: 9.5 / 9.8 ps (INVx1 rise / fall); not yet compared
  with the library's INVx1 table at the same slew and load (unverified calibration; only the ratio is used). Applied with `set_timing_derate -cell_delay` and `-cell_check` (early and late; the flops' setup and hold times were
  not characterised, so taking the gate factor for them is a stated approximation).
- **Metal.** rho(T) / rho(25 C) = 1 + 0.0039 (T - 25), bulk copper's coefficient: an upper bound, since narrow lines'
  larger residual resistivity lowers the relative coefficient. Applied to wire delay (`set_timing_derate -net_delay`)
  and to every tech layer's resistance before PDNSim.

## Controls (both pass, `runs/result.json`)

- The 25 C case reproduces G97's recorded k3 numbers (worst VDD drop 1.440 mV, VSS rise 1.241 mV) to 1 uV.
- Doubling every layer's resistance doubles the drop (x2.000), so PDNSim reads the scaled values.

## Result (`runs/result.json`)

| Case | T (C) | Cell x | Wire x | Setup WNS (ps) | Change | Hold WNS (ps) | Worst VDD drop (mV) | Worst VSS rise (mV) |
|---|---|---|---|---|---|---|---|---|
| Library, 25 C | 25.00 | 1 | 1 | +19.99 | | 52.41 | 1.440 | 1.241 |
| Stack peak | 79.77 | 1.0542 | 1.2136 | -64.51 | -84.50 | 55.28 | 1.747 | 1.506 |
| Stack mean | 58.01 | 1.0337 | 1.1287 | -31.71 | -51.70 | 54.19 | 1.625 | 1.401 |
| Peak, cells only | 79.77 | 1.0542 | 1 | -49.50 | -69.49 | 55.24 | 1.440 | 1.241 |
| Peak, wires only | 79.77 | 1 | 1.2136 | +6.40 | -13.59 | 52.45 | 1.747 | 1.506 |

- **Timing.** Closed at 25 C with 20 ps of setup slack, Ibex fails setup at the stack's temperature: by 32 ps at the
  die's mean and 65 ps at its peak. The slower cells account for 69 of the 85 ps at the peak, the warmer wires for 14
  (the two do not add exactly: the worst path changes). Hold slack grows (slower data), so hold is not at risk.
- **IR drop.** Static drop scales with the wire factor: +21% at the peak (1.747 mV, 0.25% of VDD), still far below
  G97's 2.5%-of-VDD limit, so G97's conclusion (nominal-VDD power maps stand) holds at the stack's temperature.
- **What this means for the project.** Single-corner sign-off at 25 C is not safe for a die in this stack: either
  close timing at a hot corner (the stated limit until now) or keep about 85 ps of margin at 1,400 ps (6%).

## Limits

One uniform temperature per die (no per-path temperature); delay factor from two cell types at one slew and load;
bulk-copper alpha (upper bound); Ibex's maps in G93a are G38's power maps, not the k3 window's; static IR only;
leakage power's own temperature rise (G92) is not fed back here.

## Earlier runs (kept, not used above)

- `runs_v1/` derated cell delays but not the flops' setup and hold check times (found by code review). Derating
  those too moved setup WNS by at most 0.2 ps (stack peak -64.32 -> -64.51 ps) and hold WNS by up to 0.8 ps.
- `runs_v2_partial/`: the first attempt at the current run, stopped part-way when the machine ran low on memory.

Both are kept on the work machine only (git-ignored); their result, derating factors and logs are in
`record/earlier/v1/` and `record/earlier/v2_partial/`.
