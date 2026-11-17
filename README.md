# OpenTSense

Open testbed for recovering per-die power and temperature in 2.5D/3D chip stacks from a few on-chip sensors.

| Folder | What is in it |
|---|---|
| `opentsense/stack/` | Stack YAML (dies, layers, materials, bonds, cooling) and converters to 3D-ICE `.stk` and PACT |
| `opentsense/thermal/` | Thermal solves and the response-matrix operator builder |
| `opentsense/power/` | VCD → OpenSTA per-instance power → per-tile maps; leakage(T) from ngspice |
| `configs/stacks/` | Stack YAML files |
| `gates/` | One folder per FYP gate (G70 onwards): script, config, results JSON |
| `docker/` | Pinned tool environment (ORFS/OpenROAD, OpenSTA, Icarus, Verilator, 3D-ICE, PACT, ngspice) |
| `scripts/` | Helper scripts |
| `tests/` | pytest tests |

Plan, gates and findings: `../plan.md`, `../todo-gates.md`, `../gates.md`.

## Designs the gates use

| Name in the gates | What it is | Source |
|---|---|---|
| Ibex | RV32 CPU core (lowRISC Ibex) | ORFS `asap7/ibex` and IHP |
| TPU | One 8 x 8 int8 weight-stationary systolic matrix tile (32-bit accumulators). Its header calls it "Google-TPU-style", but it is not a TPU chip: no buffers, memory interface or activation unit. Routed die 97 x 97 um on ASAP7 | ORFS `asap7/tpu`; RTL from LogikBench (Zero ASIC, MIT) at `62fc37ec` |

A millimetre-sized "TPU die" in a stack gate is a grid of this tile's power maps (G38: 10 x 10 tiles per mm), so it
has the tile's power texture, not an accelerator's floorplan.

## Quick start
```
pip install -e .[dev]
pytest
```
