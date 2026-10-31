# G71: stack file → 3D-ICE and PACT, agreement within 1 K

The registration and Amendment 1 are in `fyp/todo-gates.md`, or in `fyp/gates.md` after the run.

## Run
```bash
# inputs (once, on the host; committed): the G38 maps rebuilt from _build/asap7
python gates/g71/make_maps.py ../../_build/asap7 gates/g71/inputs/maps.npz
# gate (inside the image)
docker run --rm -v "$(pwd -W):/work" -e OPENTSENSE_IMAGE=... -e ORFS_IMAGE=... opentsense:g71dev python gates/g71/run.py gates/g71/runs/main
```
Outputs in `runs/main/`: `result.json`, `<stack>_fields.npz` (3D-ICE, PACT and operator rise maps), `manifest.json`, `run.log`.

## Development check before the run (`dev_mesh.py`, synthetic maps)
Two-die 3D stack, 60 × 60 cells. Each die has a 1 mm block (6 W on the top die, 1.5 W on the bottom die) and one 0.05 W single-cell point source. Rise in K.

| Mesh (Cu, TIM, top bulk, bond, bottom bulk) | Top peak 3D-ICE / PACT | Top point 3D-ICE / PACT | Bottom peak 3D-ICE / PACT | Bottom point 3D-ICE / PACT | 3D-ICE / PACT time |
|---|---|---|---|---|---|
| L0 (1, 1, 1, 1, 1) | 56.139 / 54.44 | 29.045 / 26.35 | 50.998 / 50.20 | 36.556 / 36.46 | 0.9 s / 7 s |
| L1 (5, 2, 4, 2, 4) | 55.445 / 55.14 | 27.953 / 27.37 | 50.197 / 50.14 | 29.171 / 30.53 | 9 s / 25 s |
| **Lm (10, 3, 6, 3, 8)**, used | 55.423 / 55.28 | 27.902 / 27.55 | 50.176 / 50.15 | 28.913 / 29.56 | about 1 min / 1 min |
| L2 (20, 5, 8, 4, 16) | 55.417 / 55.35 | 27.884 / 27.65 | 50.171 / 50.16 | 28.845 / 29.11 | about 3 min / 3 min |

Reading:
- 3D-ICE's block peak is stable from L1 onwards; PACT's approaches it from below. One node per layer was the cause of the 2 to 4% gaps seen in exploratory gate G47.
- Single-cell point sources converge slowly in both tools. They are a discretisation stress test, not a feature of the real maps.
- A finer L3 mesh was not finished: it needed more memory than the host could spare.

An earlier check on a single 3 mm die (30 × 30 cells, 1 W hotspot block plus a point source) showed the same pattern. With one node per layer the peaks were 16.53 / 15.63 K; with fine sublayers they were 16.262 / 16.23 K.

Image note: the default SuperLU_MT `sp_ienv` fill factors (50×, 30×) failed at Lm ("Storage for U columns exceeded"), so the Dockerfile raises them.

## Verdict: PASS (1 Nov 2026)
Run `runs/main` used image `opentsense:g71dev` (`73335acf`) at repo commit `82bfcaa`. The manifest says `dirty` only because this README was being written, untracked, during the run. Total time 33 min.

| Stack | Worst \|Δpeak\| (K, % of peak) | Worst RMS / mean rise | Operator max error | One node per layer, seed 0 (3D-ICE / PACT peak) |
|---|---|---|---|---|
| Single 3 mm die (TPU map) | 0.422 (0.67%) | 0.45% | 0.005 K | 63.67 / 60.36 K |
| Two-die 3D (TPU top, CPU bottom) | 0.234 (0.38%); buried CPU ≤ 0.046 | 0.22% | 0.005 K | top 62.80 / 60.40, bottom 51.54 / 50.60 K |
| 2.5D chiplets on interposer | 0.237 (0.43%) | 0.28% | 0.005 K | 54.44 / 52.08 K |

Bars: \|Δpeak\| ≤ 1 K and ≤ 4%; RMS ≤ 2%; operator ≤ 0.1 K. Every die and draw met them.

Notes:
- PACT is cooler than 3D-ICE in every case: by about 0.42 K on the single die and 0.23 K elsewhere. This is what remains of the mesh-convergence gap (see the development table above).
- The hotspot cell matched in every die map except one (single die, seed 0), where two cells are within the 0.01 K output rounding of each other.
- Operator extras: uniform 100 µm bins err by up to 0.66 K and 200 µm bins by up to 1.69 K, so later gates should use the per-cell basis.
- The operator error equals PACT's output rounding (0.005 K). This check confirms indexing and superposition; because the basis is exact for these maps, it does not test binning error.
