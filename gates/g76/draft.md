# G76 draft (17 Nov 2026): sensor representativeness on the FYP benchmark · DRAFT, not registered; bars for the student

### G76: Does the estimate survive sensors that read their own spot, not their cell's average? (RQ2, RQ3)

- **What is already known (pre-FYP experiments, `experiments/results.md`, Rounds 65 and 68; labelled exploratory).**
  - G55b (FAIL): the hottest 12.5 um patch of a 50 um cell sits 1-3 K (p95) above the cell average.
  - G56 (FAIL on its bars, which expected a large effect): a sensor at its cell's centre reads within 0.04 +/- 0.05 K
    of the cell average (worst 0.17 K); at random positions single offsets reach 2.6 K, but worst-die peak error
    rises only from 0.59 K to 0.58-0.70 K (at most about 18%), and BAE recovers up to 14% of that.
  - So the 1-3 K bounds a single reading at a hotspot, not the recovery error. `findings.md` section 3 still calls
    representativeness "the biggest unmodelled error": that line predates G56 and should be corrected by the student.
- **What G76 adds.** The same question on the FYP benchmark (G84's case set, G102's realistic sensors), so the
  benchmark's stated sensor model includes position inside the cell.
- **The blocker: fine truth.** G84's cases are PACT fields at 50 um (60 x 60 per die) from coarse power: the CPU die's
  power is a 1 mm block filled from 4 x 4 activity regions, so there is no structure inside a 50 um cell to read.
  A real offset needs (i) power below 50 um and (ii) a solve at about 12.5 um near each sensor.
  - Power: the routed Ibex is 76.7 um square (`gates/g100/runs/ibex-1400/maps.npz`, die_um), with per-cell power and
    locations (`power/ibex_k*.txt`, `ibex_loc.csv`, 48,798 cells). A 1 mm block is about 13 x 13 Ibex footprints, so
    any fine texture in it is a modelling choice (tiled copies of real cells, or random draws of them), to state.
  - Solve: the whole G71 stack at 12.5 um is 240 x 240 per sublayer, about 34 sublayers, about 2 M nodes: above
    what PACT or HotSpot fit here (G93 size probe). A local refinement fits: a 3 x 3-cell window (150 um) around each
    sensor at 12.5 um with the coarse solution as its boundary (sub-modelling), 16 windows per case.
- **Proposed design.**
  1. Offset model per sensor site: offset = T(sensor spot) - T(cell average), from windowed fine solves of the
     training cases; split into a fixed part per site and a workload part (variance over cases).
  2. Readings: G102's `ring_osc` chip model applied to cell average + offset, at three sensor positions per cell:
     centre, random (seeded), hottest (worst case).
  3. Score as G102, chips 6-15.
- **Proposed bars (to fix after the cost probe and a dry run; G102's interval test):**
  - (a) centre and random positions: field_model's interval below the average's in at least 8 of 10 chips, both dies;
  - (b) a stated plumbing check: the windowed solve with uniform power in the window reproduces the coarse cell
    average to 0.01 K.
  - Reported: the ratio of RMSE and peak error to G102's `ring_osc` values, per position.
- **First step: cost probe** (one window, one case, 3D-ICE and PACT at 12.5 um; wall time and RAM), then the dry run.
- **Decisions for the student.** (1) Fine power texture: tiled real Ibex cells or random draws of them. (2) Whether
  G76 is worth its cost given G56's result, or whether G56's numbers, quoted as exploratory, are enough for the
  thesis with G76 dropped.
- **Lints checked:** A3 (one grid: offsets defined on G84's 50 um cells), A21 (the window solve is ours inside the
  solvers' path: plumbing check (b)), A22 (12.5 um divides 50 um exactly), A10 (cost probe before any run), A25.

## Status (17 Nov 2026)

**DROPPED** by the student on 17 Nov: G56 is quoted as exploratory evidence instead (see `todo-gates.md`).
