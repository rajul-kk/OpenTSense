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

## Quick start
```
pip install -e .[dev]
pytest
```
