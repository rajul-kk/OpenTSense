# OpenTSense pipeline: every tool, what it takes, what it gives, and what reads it (8 Nov 2026)

Status: **Done** = gated (gate named); **Building** = registered or under way; **Planned** = draft gate; **Exploratory** = works but lives in `experiments/code`, not yet in the package.

## The data path, end to end

```
 RTL ─(1)ORFS─► routed netlist + .odb/.spef + instance locations
                     │
 programs ─(2)─► hex/stimulus ─(3)Icarus/Verilator gate-level sim─► VCD windows (+ toggle timeline, G81b)
                     │                                                      │
                     └──────────────────────(4)OpenSTA──────────────────────┘
                                              │  per-instance power at each library temperature
 SPICE models ─(5)ngspice: leak.py / leaklib.py─► per-T Liberty ──────────────┘
                                              │
                                   (6)maps.py: per-tile power maps per die (+ dram.py for memory dies)
                                              │
 stack YAML ─(7)model.py─► to_3dice / to_pact / to_hotspot ─(8)3D-ICE / PACT / HotSpot─► temperature maps
                                              │                    │
                                              │      (9)pact_capture + response.py ─► linear operator R (K per W)
                                              │                    │
                                  (10)electrothermal: T = T_amb + R·(P_dyn + P_leak(T))  ◄─ leakage loop
                                              │
             (11)sensors at chosen pixels (+ noise) ─► estimators (field_model, Kalman, …) ─► per-die power/temperature
                                              │
                         (12)scoring, calibration, conformal margins ─► gate result JSON + manifest ─► gates.md / findings.md
```

## Every tool

| # | Stage | Tool (file) | Status | Takes | Gives | Read by |
|---|---|---|---|---|---|---|
| 0 | Environment | `docker/Dockerfile`, `versions.env`, `requirements.lock`, `patches/` (HotSpot dump + line buffer, PACT labels) → images `opentsense:g93a` (Icarus, Verilator 5.032, ngspice + OpenVAF models, 3D-ICE, PACT, HotSpot) and pinned `openroad/orfs` | Done (G70, G93a) | Pinned versions | Reproducible tool images | Every step |
| 0 | Provenance | `opentsense/manifest.py` | Done | Image ids, tool versions, git commit | `manifest.json` per run | Every gate |
| 1 | Physical design | `scripts/orfs_flow.sh`, `power/extract.tcl` (ORFS/OpenROAD + Yosys) | Done (G70; ibex sky130/IHP/ASAP7, TPU ASAP7, cva6 ASAP7 builds in `_build/`, used read-only) | RTL, PDK | Routed netlist, `.odb/.sdc/.spef`, `inst_loc.csv` | 3, 4, 6 |
| 2 | Workloads | `gates/g72/inputs/ibex_sw` (4 G30 kernels + sleep), `power/workloads.py` (checksums, TPU stimulus W1–W3) | Done (G30, G72) | C kernels, numpy seeds | `.hex` programs, TPU stimulus + reference rows | 3 |
| 2 | Workloads | **Embench-IoT (19) + compute/WFI idle program**, pinned compiler container | **Building (G81b)** | Embench at a pinned commit | Whole-program hex, verified results | 3 |
| 3 | Activity | `power/asap7_models.py` (Icarus-ready ASAP7 models), `power/tb/{ibex,tpu}_tb.v`, `gates/g72/sim.py` (Icarus) | Done (G72) | Netlist, models, program | 1,000-cycle VCD windows, checksums | 4 |
| 3 | Activity | **Verilator gate-level sim** (`gates/g81a/vl_models.py`, `dry/build.sh`) | **Done (G81x, 8 Nov)**: with the hold testbench (no X on `data_rdata`), Verilator windows equal Icarus's within 0.45% total / 0.51% tiles, 100% annotation, about 37× faster. G81a's fail was the testbench's X injection | Same as Icarus | Whole-program VCD windows + per-module toggle timeline | 4, 11 (timelines) |
| 4 | Power | OpenSTA via `power/vcd_power.tcl` (ASAP7), `gates/g92*/power.tcl` (per-T libraries) | Done (G72, G75, G92) | `.odb/.spef`, Liberty, VCD | Per-instance internal/switching/leakage power | 6, 10 |
| 5 | Leakage(T) | `power/leak.py` (ngspice spot checks; now with abort detection) | Done (G53, G75); fix 8 Nov | SPICE models | Leakage of named cell states at 25–125 °C | Cross-check for 5 |
| 5 | Leakage(T) | `power/leaklib.py` (every state of every cell, staged settling, explicit outcomes) | **Building (G92e)**; G92–G92d failed on narrow points | Shipped Liberty, SPICE models | One Liberty per temperature (25…125 °C), `leak_states.json` | 4 → 10 |
| 6 | Maps | `power/maps.py` | Done (G72) | OpenSTA report, locations | Per-tile power maps (ny, nx) | 8, 9, 10 |
| 6 | Maps | `power/dram.py` (parametric DRAM die) | Done (stated assumption; G93a/G93) | Bank layout, currents | DRAM-die power map | 8 (G93) |
| 6 | Maps | **DRAMPower from real memory traffic** | Planned (G81e) | Memory requests from G81b runs | Workload-following memory power | 8 |
| 7 | Stack | `stack/model.py` + `configs/stacks/*.yaml` | Done (G71, G93a: regions, either sink side) | YAML | Stack object | 8, 9 |
| 7 | Converters | `stack/to_3dice.py`, `to_pact.py`, `to_hotspot.py` | Done (G71, G93a) | Stack + power maps | `.stk/.flp/.lyt`; PACT CSVs; HotSpot config/lcf/ptrace | 8 |
| 8 | Thermal solve | `thermal/run.py` (`run_3dice`, `run_pact`, `run_hotspot`) | Done; three solvers agree to ≤ 0.41 K (G93a) | Converted inputs | Per-die temperature maps | Truth for 11; checks |
| 8 | Complex stacks | HBM-style, 2.5D + HBM, 3-tier, mixed die sizes | Planned (G93) | Thermo geometries (read-only) | New stack YAMLs | 8–11 |
| 9 | Operator | `thermal/pact_capture.py` + `thermal/response.py` | Done (G71/G92) | One PACT run | Linear operator R from PACT's own matrix | 10, 11 |
| 10 | Electro-thermal | `thermal/electrothermal.py` (LeakModel, fixed point, ρ, amplification) | Done (G74, G92 (c) passes) | R, dynamic maps, per-T instance leakage | Coupled temperature, ρ, peak shift | Design numbers, 11 |
| 11 | Estimation | `estimate/field_model.py` (Gaussian prior / gappy POD), `placement.py` (QDEIM, greedy A/D), `calibrate.py` (conformal bands, OOD score) | Done: unit-tested, run on IC-ThermBench; not yet on our stacks | Training fields, sensor pixels | Posterior field, sensor sets, calibrated bands | 12 |
| 11 | Estimation | `estimate/icthermbench.py`, `ood_check.py` | Done | IC-ThermBench (CC BY 4.0) | External benchmark split, cross-package OOD check | 12 |
| 11 | Estimation | Stack recovery: Bayesian cross-die recovery, Kalman / transient (G44), conformal margins (G57, G66–G69), placement (G58), coupling (G54, G61) | **Exploratory** (`experiments/code/sens`); to be ported as G76–G80 | Phase-generator power + 3D-ICE truth | Per-die power/temperature recovery, margins | 12 |
| 11 | Activity → sequences | `phase_maps` / sequence generators (`sens/g42.py`, `g44.py`, `g63p.py`, `g66.py`) | **Exploratory, being replaced** (G81c) | 4 kernels, 3 TPU stimuli, random phase timing | Power sequences for recovery | 11 |
| 11 | Sensor model | Sensor representativeness / error classes | Planned (G76, G86) | Fine FEM, sensor classes | Sensor offsets and noise | 11 |
| 12 | Scoring | Per-gate `evaluate.py` + `run.sh`; benchmark scorer | Done per gate; **one-command scorer planned (G84)** | Run outputs | `result.json`, verdicts | `gates.md`, `findings.md` |
| — | Side tool | `fyp/tools/iceforge` (copy of Thermo's): build/check/snap/run/diff 3D-ICE models; HotSpot and PACT second opinions; `refsolve` reference | Done (Thermo commit `ffa7e46`; PACT added 7 Nov) | Hand-written `.stk` models | Checked models, solver disagreement reports | Not in the data path: checks hand-built 3D-ICE models (G93 geometries) |
| — | Release | pip/Docker install, reproduce one result per RQ | Planned (G91) | Everything above | Clean-machine reproduction | — |

## Seams (where the pipeline is not yet one piece)

1. **Activity → sequences (stage 2/3 → 11).** Recovery runs on 4 short kernels tiled by a random phase generator. G81a → G81b → G81c replace this with whole programs, measured timelines and a suite split.
2. **Estimation is split.** The package (`estimate/`) is checked on IC-ThermBench. The stack recovery experiments are exploratory scripts. G76–G80 and G84 port them and give one scorer.
3. **Memory and accelerator power** do not follow the CPU workload: SRAM uses `fakeram` models, DRAM uses random traffic, CPU and TPU phases are paired at random. G81d and G81e address this.
4. **Toolchain outside the image.** The RISC-V compiler is in WSL only. G81b pins it in a container.
5. **Exploratory ORFS builds** in `_build/` are used read-only. Rerouting is not part of any gate yet. G91 decides what the release rebuilds.
