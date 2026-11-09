# G93a registration (written 7 Nov 2026, before the gated run)

### G93a: Three thermal solvers (3D-ICE, PACT, HotSpot) and the extended stack format (O1) · REGISTERED
- **Why.** HotSpot becomes a primary third solver, and the stack format gains lateral material regions, a bottom
  heat sink and die footprints (`gates.md`, image and pipeline change of 7 Nov). Before the complex stacks of G93,
  this gate checks that (i) the change did not move G71's answers, (ii) HotSpot agrees with the two established
  solvers on G71's stacks and maps, and (iii) the new features give three-way agreement on real maps.
- **Image:** `opentsense:g93a` (HotSpot 7 `f18831e` with the 6-decimal dump patch; PACT label patch; every other
  tool, model and Python package identical to `g75spice`).
- **Inputs:** G71's maps (`gates/g71/inputs/maps.npz`, seeds 0 to 3), G71's stack configs and sublayer mesh.
- **Development before registration (plumbing, not the gate's stacks or maps):** small 16 × 12 stacks in
  `tests/test_solvers.py`. Two HotSpot package work-arounds were found there and are fixed in `to_hotspot.py`:
  package layers 1.001 × the chip's longer side (an exactly chip-sized package is singular and HotSpot silently
  prints power as temperature), and r_convec = (2/3)/(h·s²) (detailed-3D HotSpot counts the sink's convection
  1.5 times). With them HotSpot equalled 3D-ICE to 0.001 K on those stacks. No G71 stack or map was run in HotSpot
  before this registration.

**Parts and bars (all must hold):**
- **(a) Regression.** On G71's three stacks (single die, two-die 3D, 2.5D) and four seeds, the new code in the new
  image reproduces G71's stored 3D-ICE and PACT rise fields (`gates/g71/runs/main/*_fields.npz`).
  Bar: max |difference| ≤ 1e-9 K on every die, seed and solver (both tools' outputs are rounded and deterministic,
  so any change is a real change).
- **(b) HotSpot on G71's stacks.** Same stacks, mesh and maps. HotSpot against 3D-ICE, and HotSpot against PACT,
  per die and seed, with G71's bar applied to each pair (3D-ICE's rise is the reference for the relative bars):
  |Δpeak| ≤ 1 K and ≤ 4% of the peak rise; RMS difference ≤ 2% of the mean rise.
- **(c) New features on real maps.** Two new configs, both from G71's maps and mesh:
  1. `g93a_25d_regions`: G71's 2.5D stack with the chiplet layer's monolithic-silicon approximation removed. The
     layer's base material is underfill (k = 0.7 W/m·K, cv = 1.8e6 J/m³·K, Thermo's underfill value), with silicon
     regions at the two chiplet footprints (x 0.1 to 2.1 and 2.3 to 4.3 mm, y 0.5 to 2.5 mm, as G71's maps).
  2. `g93a_3d_bottom`: G71's two-die 3D stack, with the heat sink on the bottom face instead of the top (a solver
     check of the bottom boundary, not a realistic package).
  Bar: the same pairwise bar as (b), for all three pairs (3D-ICE–PACT, HotSpot–3D-ICE, HotSpot–PACT), every die and
  seed.
- **Reported, not gated:**
  - one node per layer (seed 0) for all three solvers on every stack, as G71's extra;
  - a refined mesh (every n_sub doubled) for the two-die 3D stack, seed 0: each solver's peak rise and the pairwise
    differences;
  - (c)1 against G71's monolithic 2.5D result: how much the underfill gap moves the peak;
  - wall time per solver.
- **A fail means:** (a) a regression in the converters or image, to be found and fixed before anything else;
  (b) or (c) a converter bug or a real solver disagreement (recorded in `findings.md` as solver provenance either
  way). No bar is changed after the run.
- **Not claimed:** accuracy against a measured or finite-element reference; anisotropic TSV conductivity (all three
  use isotropic materials); HotSpot's own package model (it is reduced to a per-cell HTC here).
- **Output:** `gates/g93a/runs/main/` · **Run:** `gates/g93a/run.sh main`

## Amendment 1 (7 Nov 2026, after an aborted first run; no bar changed)
- **What happened.** The first `main` run (image `sha256:f6a5cd88…`, started 14:18) finished the single-die stack
  (all four seeds within the bar, regression 0) and then stopped on the two-die 3D stack, seed 0: HotSpot exited with
  `error: line too long`. HotSpot reads its power trace line into a fixed buffer of `LINE_SIZE` = 65,536 characters
  (`util.h`); the trace has one value per cell of every source layer, about 16 characters each, so two 60 × 60 dies
  need about 115,000. The run produced no verdict; its log and outputs are kept in `runs/aborted1/` and are not
  scored.
- **Change.** The image's HotSpot patch (`docker/patches/hotspot-f18831e.patch`) also sets `LINE_SIZE` to 1,048,576.
  Buffer size only: no change to the model or the solver. `to_hotspot.py` now refuses, with a message, a trace line
  longer than that. Rebuilt image `opentsense:g93a` = `sha256:76e2685256694157a3b1937008377de4f8554be7b712776f88dbbde878716e98`
  (previous image kept as `opentsense:g93a-pre1`); pip freeze, 3D-ICE, ngspice and PACT sources checked identical.
- **Rerun.** The whole gate is rerun from the start in `runs/main` with the rebuilt image. Bars, stacks, maps and
  seeds are unchanged.
