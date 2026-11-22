# G93 draft (written 12 Nov 2026; NOT registered): consumer-sized stacks across three solvers (goals.md goal 4)

### G93: Do the three solvers still agree on stacks at consumer area and power? (O1/RQ1) · DRAFT

- **Why.** Today's dies are 3 x 3 mm at 6 to 8 W. Power density and peak rise already sit in consumer ranges, but
  lateral spreading changes with die size, and a buried die under a large hot die is the case the testbed is for.
- **Stacks (proposal).** Four stacks, each defined by published area, thickness and power. Each power map is built
  from tiled routed ibex maps (G81b) scaled so that both the total watts and the density match the figure.

| Stack | Geometry | Power | Ported from (Thermo, read only) |
|---|---|---|---|
| S1 cache-on-logic | logic die 80.7 mm2 (Zen 3 CCD) under a 41 mm2 SRAM die, structural silicon over the rest, hybrid bond, both thinned | about 105 W package TDP, one CCD; SRAM die a few W | geometry2 (2-die 3D) |
| S2 HBM-style | logic base plus 8 DRAM dies at about 110 mm2, dies about 30 to 50 um | 20 to 32 W per stack; DRAM die maps from G81e when ready, else G50's random traffic | geometry5 (2-die HBM), extended to 9 dies |
| S3 2.5D accelerator | logic about 800 mm2 beside 4 HBM stacks (S2) on an interposer, mould between | logic 300 to 700 W | geometry5 (2.5D) |
| S4 3-tier buried die | three logic dies at about 100 mm2, middle one buried, hybrid bond | 30 to 60 W in total | geometry2 plus a tier |

- **Figures and sources (each must be confirmed from a primary source before registration).**

| Figure | Value | Source found 12 Nov | Status |
|---|---|---|---|
| V-Cache SRAM die area | 41 mm2 (gen 1), 36 mm2 (gen 2) | Tom's Hardware / WikiChip summaries of ISSCC 2022 paper 26.4 (Wuu et al.) and Hot Chips 2023 | confirm in ISSCC 26.4 |
| Zen 3 CCD area | 80.7 mm2 (Zen 4 CCD 66.3 mm2) | same | confirm in ISSCC 26.4 / AMD |
| CCD and cache die thinning | reported "below 10 um" to expose TSVs | Tom's Hardware teardown report | doubtful as a die thickness (likely the TSV reveal depth); find the real thickness |
| HBM3E stack heat | up to 32 W (8 or 12 high, 24 Gb dies) | heise, quoting KAIST Teralab | confirm in the KAIST roadmap or a vendor paper |
| HBM die thickness | 30 um in the 12-high stack | AnandTech, quoting SK hynix | confirm from SK hynix |
| HBM die area | not found | none | needed: JEDEC JESD238 footprint or a teardown |
| Accelerator logic die | about 814 mm2 at 700 W (H100 SXM) | general knowledge, not yet sourced | find a datasheet |

- **Solvers and size.** All three solvers as in G93a (same image, same converters). Grid: cells of about 0.25 to 0.5
  mm (S3: about 64 x 64 over the interposer), sublayers as G93a. Check RAM on S3 first: the WSL limit is 12 GB,
  PACT's matrix is the largest, so a one-off size probe runs before the gate.
- **Bars (proposal; the student fixes them).** G93a's pairwise bar for every pair, die and stack: |Δpeak| ≤ 1 K and
  ≤ 4% of the peak rise; RMS difference ≤ 2% of the mean rise. The buried die (S1 logic under SRAM, S2 base, S4
  middle) reported separately. Mesh stability: halving the cell moves each solver's peak by ≤ 2% (reported, gated
  only if the student wants it).
- **A fail means.** The solvers' agreement at 3 x 3 mm does not carry to consumer size; the report then states
  which solver pair and stack, and the benchmark keeps to the sizes that passed.
- **Not claimed.** Package and board beyond a heat-sink coefficient; transient (G94); measured silicon temperatures.
- **Waits on.** G92e finishing (WSL); the student's yes on the four stacks; the primary sources above.

## Student decision (12 Nov 2026)

Yes on the four stacks. The HBM die area is flagged in the table until a primary source is found. Bar numbers still follow the noise-floor rule of `plan.md` 2.1 where it applies.

## Sources checked (12 Nov 2026, goal 4 step "primary sources")

| Figure | Value to use | Source | Grade |
|---|---|---|---|
| V-Cache SRAM die (L3D) | **41 mm2** | AMD's ISSCC 2022 26.4 slides (Wuu et al.), slide 11: "64MB L3 Cache Extension ... 41mm2" (AMD's SlideShare upload) | primary |
| Zen 3 CCD | **81 mm2** | same slides, slide 10: "CCD ... TSMC 7nm technology ... 81mm2". The widely quoted 80.7 mm2 is consistent; a die-shot measurement gives 83.7 mm2 (includes scribe) | primary |
| TSV pitch, CCD to L3D | 9 um minimum | same slides, slide 16 | primary |
| CCD and L3D thickness after thinning | **not published** | the slides say only "thinned CCD" and "support silicon added to match 2D CCD Z-height" (slides 12, 17) | assumption: state it and sweep it (e.g. 20, 50, 100 um) |
| HBM3E stack heat | up to 32 W | KAIST Teralab roadmap (June 2025), as reported by heise and 3DInCites | secondary (a research roadmap, not a vendor figure) |
| HBM DRAM die thickness | about 30 um (12-high) | SK hynix press release, April 2023, via AnandTech and KED Global | vendor statement, secondary report |
| HBM die area | **not found** | Choi et al., JSSC 2023 ("A 192-Gb 12-High 896-GB/s HBM3 DRAM ...") is the likely primary source (paywalled); the stack package is 11 x 11 mm, and a later paper quotes the base die as about 121 mm2 | assumption: core dies at the 11 x 11 mm footprint (121 mm2), an upper bound, flagged |
| Accelerator logic die | 814 mm2, 700 W (H100 SXM5) | consistent across AnandTech, Tom's Hardware, TechPowerUp; NVIDIA's datasheet not read here | secondary; confirm in NVIDIA's H100 datasheet before registration |

Two figures need the student's library access (Choi et al. JSSC 2023 for the HBM die area; NVIDIA's datasheet is
public). Everything else needed to register is in hand; the thickness is a stated, swept assumption.


## Realism options (16 Nov 2026, task g93-realism; commit "stack realism")

The stack model now has three options that package-level studies use. Which of them G93 uses is set in its
registration; the proposal is all three on every stack, with each solver given what it can represent.

| Option | Model key | 3D-ICE | PACT, HotSpot | Checked (image, `tests/test_solvers.py`) |
|---|---|---|---|---|
| Bump, TSV and hybrid-bond layers as columns in a fill | `bond_material(k_metal, k_fill, fraction, ...)` -> k (vertical, parallel rule), k_lateral (Maxwell-Garnett) | both directions | vertical k (isotropic) | direction order read right; k_lateral = k equals the isotropic material |
| Silicon k falling with temperature | material `k_T_exp` (silicon about 1.3), `thermal.run.solve_kT` | yes | yes | settles in 3-4 solves in all three; HotSpot = 3D-ICE within 0.01 K; +0.4% peak on the small test stack, where TIM and sink hold most of the resistance |
| Heat path down through package and board | heat_sink `opposite_htc` | yes | refused (one convective face) | equals the exact 1-D answer to 5e-6 |

Consequences for G93: the three-solver bars apply to stacks without `opposite_htc`; with it, 3D-ICE alone, against
its own run without it, reported as the bottom path's effect. The isotropic approximation that PACT and HotSpot make
for bond layers is measured by 3D-ICE (directional against vertical-only k) and reported. S3's logic die should be a
stated floorplan (TPU-tile compute blocks, low-power SRAM, PHY strips facing the HBM stacks) rather than a pure grid of
the 97 um tile. Limits: one k per layer in the k(T) loop (a hotspot's own lower k is not modelled); effective bond
values from fill fraction, not a resolved bump array.

## Floorplans (16 Nov 2026, task g93-floorplans)

The millimetre-scale dies take block floorplans from published layouts (`opentsense/stack/floorplan.py`,
`configs/floorplans/`), as HotSpot's ev6.flp was taken from a die photo, instead of grids of one routed tile. Every
block carries its source and a grade (primary, secondary, assumption); `total_W` scales all blocks by one factor.

| Die | Floorplan | Area | Total | Blocks | Main assumptions |
|---|---|---|---|---|---|
| S1 logic | `zen3_ccd` | 81.0 mm2 (AMD ISSCC 2022, primary) | 85 W | uncore strip 13 mm2 (81 - 68 mm2 CCX, primary), 8 cores of 4 mm2 in two rows, central L3 band 36 mm2 | aspect ratio; core area (forum pixel count); densities 2.2 / 0.25 / 0.5 W/mm2 before scaling |
| S2 base | `hbm3_base` | 121 mm2 (JSSC 2023 HBM3, quoted) | 8 W | PHY strip facing the host, central TSV band, logic | strip widths; densities |
| S3 logic | `gh100_class` | 814 mm2 (NVIDIA's Hopper blog, primary), snapped to 28.5 x 28.5 mm (-0.2%) for a 0.5 mm grid | 700 W (press; NVIDIA's table not yet read verbatim) | HBM PHY strips on the two long sides (package photos), I/O PHY top and bottom, two compute halves at our TPU tile's 2.07 W/mm2 (G100 W1), L2 band between | band and strip widths; L2 position; densities |

S2's DRAM dies keep `power.dram` (bank grid around a TSV strip, G59). S4 (three logic dies) has no published layout;
it reuses `zen3_ccd` per tier unless the registration says otherwise. Densities are uniform per block: at 0.25 to
0.5 mm cells the 97 um texture of a routed tile averages out inside a cell. G100's tile maps are kept in its record
(`gates/g100/record/*/maps.npz`) so the TPU density is traceable.

## Solver limits that shape the stacks (16 Nov 2026)

- **HotSpot units.** HotSpot 7 holds at most 8192 units per floorplan and per power trace (`MAX_UNITS`) and allocates an n_units^2 wire-density matrix per floorplan (`flp.c`), so one unit per cell cannot reach S3 (about 620 MB per layer). `to_hotspot` now writes rectangles of equal material and power (a few dozen units per layer for block floorplans), with the same per-cell result; no image change is needed for S3.
- **Grid alignment.** Die rectangles must lie on the cell grid, so S3 uses 0.5 mm cells: logic 57 x 57, HBM 22 x 22.
- **What is gated.** Only physics all three solvers represent: isotropic bond k (vertical value), no `opposite_htc`; k(T) allowed. Anisotropy, the bottom path and the thickness sweep are reported from 3D-ICE, not gated.
- **S4 power.** `zen3_ccd` at 85 W per tier would give 255 W; S4 sets total_W per tier so the stack is 30 to 60 W, as the draft states. Block floorplans have no seeds: the case set is per stack the nominal floorplan plus stated density variants (to be fixed in the registration).
- **Bars.** Written as the noise-floor rule (mesh halving per solver), not G93a's 1 K, which does not transfer to 700 W. The size probe (uniform power; nodes, RAM, wall time only, no pairwise differences) runs before registration.

## Size probe, partial (16 Nov 2026; `dry/size_probe.jsonl`, uniform power, 2.5 GB cap per container)

| Stack | Grid, sublayers, nodes | 3D-ICE | HotSpot | PACT |
|---|---|---|---|---|
| S1 V-Cache | 42 x 31, 26, 34k | 1.9 s, 0.17 GB | 7.8 s, 0.53 GB | 8.0 s, 0.33 GB |
| S4 3-tier | 42 x 31, 27, 35k | 2.3 s, 0.18 GB | 8.1 s, 0.54 GB | 8.7 s, 0.34 GB |
| S2 HBM | 44 x 44, 48, 93k | 21 s, 0.80 GB | 55 s, 2.03 GB | 36 s, 1.05 GB |
| S3 2.5D | 107 x 59, 53, 335k | not finished | | |

The probe was stopped during S3 by the session's low-memory guard (machine at about 3 GB free), not by the cap or an
error. HotSpot's memory grows fastest (2 GB at 93k nodes), so S3 at 335k nodes likely needs a coarser HotSpot grid or
more free RAM; S3 is to be probed alone when the machine has room.

### S2 and S3 on a Kaggle CPU session (16 Nov 2026; `dry/kaggle_probe.py`, output `dry/size_probe_kaggle.jsonl`)

Kaggle has no Docker, so the script builds 3D-ICE, HotSpot and PACT from the pinned commits and our patches (system
libraries are Kaggle's, not the image's snapshot) and runs `tests/test_solvers.py` first: 11 passed. S2's peak memory
matches the local image's to within 0.02 GB in every solver (times are about 2x the local ones).

| Stack | Nodes | 3D-ICE | HotSpot | PACT |
|---|---|---|---|---|
| S2 HBM, 250 um | 93k | 39 s, 0.80 GB | 111 s, 2.03 GB | 66 s, 1.07 GB |
| S3 2.5D, 500 um | 335k | 534 s, 5.1 GB | 2082 s, 15.6 GB | 614 s, 7.0 GB |

S3 runs in all three solvers, but HotSpot needs 15.6 GB, more than this machine's 15.7 GB total: S3 runs on Kaggle
(about 30 GB) or with a coarser HotSpot grid. Before any gated G93 result from Kaggle, one small stack is compared
against the image's temperatures (architecture lint A18); this probe printed none.

## Interface resistances (16 Nov 2026, goal 10; before registration)

The parallel-rule bond layers left out contact resistance: they gave 0.05 mm2 K/W for the hybrid bond and 2.9 for a
micro-bump layer. Bonded layers now take k = t / R'' from measured area resistances (`stacks.py`, cited via the SMTA
2025 hybrid-bonding review), graded and swept:

| Interface | R'' (mm2 K/W) | Source | Grade | Sweep |
|---|---|---|---|---|
| Hybrid Cu/oxide bond (S1, S4), 2 um | 1.2 | Oprins et al., ITherm 2016 (imec, measured); 2.49 simulated by Han and Kawano, EPTC 2021 | secondary | 1.2 to 2.5 |
| Micro-bump layer, solder in underfill (S2, S3), 10 um | 10 | Colgan et al., SEMI-THERM 2012 (IBM, measured 8 to 15) | secondary | 8 to 15 |
| TIM1, 50 um | 12.5 | assumed polymer TIM1 (as G93a, 4 W/m K) | assumption | 5 to 20 |

By hand (flux x R''): about 1.3 K across S1's bond at 85 W (was 0.05 K), and about 1.7 K per micro-bump layer at
S2's full flux, so several K over the HBM stack. TSV columns are not added: at about 1% of a silicon die's area they
raise its vertical k by about 2%. All three solvers represent these (isotropic layers), so they stay in the gate.

After review (16 Nov 2026): only the L3D is hybrid-bonded; the structural silicon over the cores is oxide-bonded
(AMD slide 14), so S1's bond layer is `oxide_bond` (ASSUMED 1.43 mm2 K/W: 2 um of oxide at 1.4 W/m K, the bonded
interface itself small by TDTR, arXiv 2601.03106; swept to 2.9) with a `hybrid_bond` region over the L3D, snapped to
the grid. Interface thicknesses and R'' are build parameters (`stacks.build(name, cell, **interfaces)`), so a sweep
keeps k = t / R'' in every bonded layer (tested at a sweep point).

### Seen before registration (declared)

- 16 Nov 2026, a solver-acceptance check of the oxide-bond region: S1 at 500 um cells, uniform-in-block nominal
  power, all three solvers. Peak rise over ambient: 3D-ICE 59.22 K (CCD) / 55.34 K (L3D), HotSpot 58.86 / 54.98,
  PACT 59.04 / 55.18 (spread 0.36 K, 0.6%). The registration's bars must be set without reference to these numbers;
  the gated runs are at the registered cells and sweep points, not this one.

### To settle in the registration

- S3 places the 700 W logic die as silicon regions inside the HBM layer columns and its power on the `hbase` source
  layer, so "die hbase" mixes the logic die with the four HBM base dies, and k(T) takes one temperature per layer
  over all its silicon. Report S3 per region (logic, each HBM column), not per die, and give k(T) per region or
  state the averaging (found by code review, 16 Nov).

## Package: lid and cooler (17 Nov 2026; before registration)

Until today the spreader was exactly die-sized under h = 5e4 W/(m2 K), so heat could spread sideways only within the
die outline: a large weakness against package-level papers (student's question, 17 Nov). `stacks.py` now builds
S1, S2 and S4 under a square lid wider than the dies, with the dies centred, air beside them under the lid, and the
cooler as a stated thermal resistance spread over the lid top, h = 1 / (r_sink x lid area). S3 is lidless (an
SXM-class module, cold plate on the dies), so its spreader stays the interposer outline with r_sink set.

| Stack | lid_um | r_sink (K/W) | Status |
|---|---|---|---|
| S1 V-Cache, S4 3-tier | 30,000 | 0.12 (large tower or AIO cooler) | ASSUMED, not sourced: for the student to fix or sweep |
| S2 HBM (stand-alone) | 15,000 | 0.5 (its share of a shared plate) | ASSUMED |
| S3 2.5D | none (interposer outline) | 0.03 (liquid cold plate) | ASSUMED |

Both are build parameters (`stacks.build(name, cell, lid_um=..., r_sink=...)`), so a sweep keeps one code path.
Consequences:
- **Size.** At 250 um cells S1 and S4 grow to about 380k nodes (34k before), above S3's 335k, where PACT needed
  15.6 GB, more than the machine has; at 500 um they are about 95k (S2 43k). The registration's cell size must be
  chosen against a new size probe, written beside the old one (`dry/size_probe_lid.jsonl`), not over it.
- **Superseded.** The size-probe table above and the "Seen before registration" S1 numbers describe the die-sized
  stacks; they stay as the record of what was seen, and do not describe the stacks that will be registered.
- **Air.** No solver has yet run a layer with a k = 0.026 region beside silicon; the new probe runs all three.

### Size probe, lidded stacks (17 Nov 2026, `dry/size_probe_lid.jsonl`)

500 um cells, uniform power, opentsense:g94b, each solver alone in a 3 GB container (`dry/size_probe_lid.sh`):

| Stack | Nodes | 3D-ICE s / GB | HotSpot s / GB | PACT s / GB |
|---|---|---|---|---|
| S1 | 93,574 | 11.4 / 0.72 | 55.0 / 2.52 | 26.5 / 1.05 |
| S2 | 43,200 | 2.5 / 0.24 | 10.1 / 0.76 | 8.9 / 0.40 |
| S4 | 97,173 | 14.0 / 0.77 | 55.8 / 2.72 | 34.2 / 1.10 |

All nine finished, so all three solvers accept the air regions (this probe reads no temperatures, so whether they
treat air alike is the gate's own comparison). HotSpot is the binding cost: 2.72 GB at 97k nodes, close to a 3 GB cap,
so 500 um is the largest of the tried cell sizes that fits; 250 um (about 380k nodes) does not.

## Sensitivity outside the gate: BEOL and a board path (goal 11, 17 Nov 2026; 3D-ICE only, not gated)

`sens/beol_board.py` via `sens/run.sh` (opentsense:g94b, 500 um cells, steady, nominal power, silicon k(T));
outputs `sens/runs/<stack>_500um_<variant>.json`. Change of each die's peak rise (inside its powered silicon) against
the stack as G93 built it before 17 Nov (no BEOL layer; now `stacks.build(..., beol_um=0)`), in K; the base column is the base peak rise. BEOL: 10 um on each die's source face under
its powered silicon, vertical k 2 W/(m K) (range 1 to 6), lateral 15; board: h = 1 / (R_jb x die footprint), R_jb 2
(lo) or 8 (hi) K/W. All BEOL and R_jb values ASSUMED from secondary sources (`beol_board.py` docstring).

| Stack, die | Base | BEOL iso | BEOL aniso | BEOL k_v 1 | BEOL k_v 6 | Board R_jb 2 | Board R_jb 8 |
|---|---|---|---|---|---|---|---|
| S1 L3D (top) | 62.38 | -0.21 | -0.25 | -0.46 | -0.11 | -12.06 | -3.64 |
| S1 CCD (buried) | 66.49 | +10.48 | +10.43 | +20.83 | +3.44 | -12.75 | -3.86 |
| S2 die 0 (top) | 15.53 | -0.21 | -0.23 | -0.40 | -0.10 | -4.86 | -1.74 |
| S2 die 7 | 31.09 | +6.51 | +6.40 | +12.61 | +2.11 | -10.67 | -3.73 |
| S2 HBM base (bottom) | 32.81 | +7.29 | +7.18 | +14.24 | +2.37 | -11.56 | -4.04 |
| S4 top | 30.78 | -0.21 | -0.24 | -0.42 | -0.10 | -5.33 | -1.61 |
| S4 mid | 31.78 | +2.78 | +2.74 | +5.41 | +0.91 | -5.60 | -1.69 |
| S4 bottom | 32.18 | +3.94 | +3.89 | +7.64 | +1.30 | -5.86 | -1.77 |

- **Vertical BEOL resistance is first order for buried dies:** +3 to +21 K on S1's CCD across the published k_v
  range, growing with depth in S2 (+1 K at die 1 to +7 K at the base, k_v 2). A die whose heat leaves without
  crossing its own BEOL (the top die of each stack) barely moves (-0.1 to -0.5 K).
- **Lateral anisotropy does not matter at this resolution:** isotropic and anisotropic BEOL differ by at most 0.11 K
  (S2 base), so a three-solver gate with isotropic BEOL would lose almost nothing at 500 um cells. Finer cells, where
  lateral spreading near hotspots matters, were not tested.
- **A board path cools every die:** -1.6 to -4.0 K at R_jb 8 K/W and -4.9 to -12.8 K at 2 K/W, so the adiabatic bottom
  overstates rises by up to about 20% (S1 CCD at 2 K/W: 12.75 of 66.49 K). Part of this is the air beside the dies
  (the coefficient covers the whole bottom face, `beol_board.py`, a stated limit of about +10% on 1 / R_jb in S1).
- **Gradients** move with the peak (S1 CCD 23.5 to 34.8 K/mm with BEOL); per-die values are in the JSON files.
- **What this means for G93.** Leaving BEOL out makes buried dies read several K cool, which is larger than the
  three-solver agreement G93 tests (G93a: 0.41 K), so the gated stacks should carry an isotropic BEOL layer (every
  solver can represent it) or state the bias. That is the student's call before registration. S3 (2.5D, 335k
  nodes) was not run: it needs a larger container than this machine gives 3D-ICE beside other jobs.
- **Possible overlap:** G93's hybrid-bond and micro-bump layers already carry their own conductivities; whether the
  sources behind them include BEOL was not checked, so part of the BEOL effect may be counted twice.

## BEOL in the gated stacks (17 Nov 2026, student's decision after goal 11)

`stacks.build` now gives every die an isotropic BEOL layer (10 um, k 2 W/(m K), cv 2e6; all ASSUMED, `stacks.BEOL`)
on its source face (over its powered silicon where the layer is made of regions); `beol_um=0` builds the stacks
without it (goal 11's base). The recorded `sens/runs/` JSONs carry cache key 7c93f5c6d274ff12, from stacks.py
before this change; the key now differs (it hashes stacks.py), so `sens/run.sh` would recompute them rather than
skip. The stacks are the same: re-solving S2's and S4's base with the new code (17 Nov) gave every die's peak rise
and gradient identical to the recorded JSONs. One more sublayer per die: +7.2k nodes on S1, +8.1k on S2, +10.8k on S4 and
+56.8k on S3 (nine dies on a 107 x 59 grid) at 500 um cells, so S3 needs its own size probe, and HotSpot's 2.72 GB on S4 (`dry/size_probe_lid.jsonl`) may pass a 3 GB cap; the size probe is to be
repeated with BEOL before the cell size is registered.

### Size probe with BEOL: S3 and S2 on a Kaggle CPU session (17 Nov 2026; `dry/kaggle_probe_beol.py`, output `dry/size_probe_kaggle_beol.jsonl`, log `dry/size_probe_kaggle_beol.log`)

Same build as the 16 Nov Kaggle probe (solver tests: 11 passed), stacks now with their BEOL layer, 500 um cells.

| Stack | Nodes | 3D-ICE | HotSpot | PACT |
|---|---|---|---|---|
| S2 | 51,300 | 7.6 s / 0.30 GB | 40.2 s / 0.91 GB | 24.4 s / 0.48 GB |
| S3 | 391,406 (334,589 without BEOL) | 740 s / 6.40 GB | 4,483 s / 25.55 GB | 817 s / 8.29 GB |

S3's nine BEOL sublayers add 17% nodes but take HotSpot from 15.63 to 25.55 GB (+63%), close to a Kaggle CPU
session's 30 GB: S3 at 500 um in HotSpot runs on Kaggle with little margin, and not at all on this machine. The
S2 line is the parity check against this machine's `size_probe_beol.jsonl` (node count must match; RAM and time are
the machine's).

## Sensitivity: the cooler's resistance (17 Nov 2026, ungated, `sens/cooler.py`, `sens/cooler_runs/`)

3D-ICE, 500 um cells, the gated stacks (BEOL included), steady, nominal power, k(T); r_sink at 0.5x, 1x and 2x its
PACKAGE value. Per die: peak rise / spread inside the powered silicon (peak minus coolest cell) / largest gradient.

| Stack, die | 0.5x | 1x | 2x |
|---|---|---|---|
| S1 ccd (88 W) | 67.4 K / 39.0 K / 34.6 K/mm | 77.0 / 40.1 / 35.0 | 91.1 / 41.2 / 35.7 |
| S1 l3d | 52.7 / 26.2 / 16.5 | 62.2 / 27.2 / 16.8 | 76.2 / 28.3 / 17.3 |
| S2 base (20 W) | 34.8 / 20.6 / 7.9 | 40.1 / 21.1 / 8.0 | 50.4 / 21.5 / 8.2 |
| S4 bot (45 W) | 31.4 / 19.3 / 14.4 | 36.1 / 19.7 / 14.4 | 43.1 / 20.1 / 14.6 |

From 0.5x to 2x (a 4x range in r_sink) the peaks move by 12 to 24 K (S4 bot 11.7, S1 ccd 23.7), but the spread by at
most 2.3 K (S1 ccd; at most 8% relative, S1 l3d) and the gradient by at most 1.1 K/mm (S1 ccd; at most 5%
relative, S1 l3d): a uniform cooler shifts the field, it
barely reshapes it. The shape the sensors must reconstruct is set by the
power map and the spreading path; the cooler sets the level (which matters for k(T), leakage and the limits). Not
covered: a cold plate's inlet-to-outlet gradient or any non-uniform coefficient, which would reshape the field. The
S4 2x solve took 2,745 s for the same 3 k(T) iterations as the others (machine contention, not a solver result).

## Sensitivity: leakage that grows with temperature (goal 15, 18 Nov 2026, ungated, `sens/leak.py`, `sens/leak_runs/`)

3D-ICE, 500 um cells, the gated stacks, steady, k(T). Each cell's nominal power is taken as its power at 85 C and
split into dynamic (1 - share) and leakage (share), the leakage scaled by our own ASAP7 LVT curve (G92e
`runs/main/asap7_lvt/leak_ref.json`, about 3.3 %/K, doubling every 21 K; `stacks.leakage`); solved to the joint
k(T)-leakage fixed point (`run.solve_kT`, 0.01 K), stopped as a runaway once any cell passes ambient + 400 K.
Ambient 26.85 C in every stack. Peak rise / spread, K; total power against nominal:

| Stack, die | share 0 | 0.1 | 0.25 | 0.4 |
|---|---|---|---|---|
| S1 ccd (88 W nominal) | 77.0 / 40.1 | 83.8 / 46.1, 1.04x | runaway (5,052 K after 8 solves) | runaway (1,040 K after 5) |
| S1 l3d | 62.2 / 27.2 | 67.2 / 31.3 | - | - |
| S2 base (20 W) | 40.1 / 21.1 | 37.6 / 20.0, 0.93x | 33.4 / 18.0, 0.81x | 28.5 / 15.6, 0.69x |
| S4 bot (45 W) | 36.1 / 19.7 | 33.8 / 18.5, 0.93x | 29.8 / 16.4, 0.82x | 25.4 / 14.1, 0.69x |

Seen:
- The sign depends on where a stack runs against the 85 C reference. S1's CCD peaks near 104 C (77 K over 26.85 C),
  so leakage adds power where it is hottest: the peak rises 6.8 K and the spread 6.0 K at a 10% share, and at 25%
  the loop runs away. S2 and S4 run below 85 C, so the same model takes power away and both level and spread fall.
- Unlike the cooler, leakage reshapes the field in S1 (spread +15% at 10%). At a 25% or 40% share the
  fixed-point loop diverged from the nominal start; the figures it stopped at (5,052 K, 1,040 K) only mark the
  divergence, since they extend the curve far past its 125 C end. This is evidence of a thermal runaway, not a
  proof: the spectral-radius test of `thermal/runaway.py` (from ambient) was not run here.
- What is ASSUMED: nominal power stands for 85 C, and every cell has the same share. The student decides whether
  the gated stacks carry leakage, at what share, and at what reference temperature.

## Sensitivity: a liquid cold plate (goal 19, 18 Nov 2026, ungated, 3D-ICE only, `sens/coldplate.py`, `sens/coldplate_runs/`)

3D-ICE's two-resistance microchannel model on the lid (under a 500 um cover), in place of the uniform cooler:
copper, 1 mm tall, 100 um channels and walls, water at 1.5e4 W/(m2 K) top and bottom (laminar, Nu about 4.5; all
ASSUMED), inlet at ambient, flows 1 L/min (a pump of an all-in-one cooler) and 0.25 L/min (weak). The same script
runs the uniform cooler as the baseline (`*_uniform.json`), because a floorplan tilts the field by itself; tilt is
the mean rise of the last third of the die minus the first third, along the flow (y). Plate minus baseline:

| Stack, die | Coolant rise | Peak | Spread | Tilt from the coolant (baseline's own tilt) |
|---|---|---|---|---|
| S1 ccd, 1 L/min | 1.3 K | -16.1 K | -2.0 K | -0.1 K (+4.2) |
| S1 ccd, 0.25 L/min | 5.1 | -12.5 | -1.0 | +0.9 |
| S2 base, 1 L/min | 0.3 | -7.3 | -0.9 | +0.8 (-14.8) |
| S2 base, 0.25 L/min | 1.2 | -7.0 | -1.1 | +0.9 |
| S4 bot, 1 L/min | 0.6 | -8.0 | -0.9 | -0.0 (+1.8) |
| S4 bot, 0.25 L/min | 2.6 | -6.1 | -0.4 | +0.5 |

Seen:
- The coolant's inlet-to-outlet warming tilts the dies by at most about 1 K, even at the weak flow: the water
  takes up 0.3-5 K over the whole plate. The tilts seen in the plated runs (S2 base -14 K) are the floorplan's,
  present with the uniform cooler too.
- The plate acts as a stronger cooler (peaks 6-16 K lower) and, like a smaller r_sink, barely reshapes the field.
  For the sensors the cooler's type is a level, not a shape: the uniform coefficient of the gated stacks is
  adequate. The first plated runs (`sens/coldplate_runs_v1/`, no baseline) are kept as run.
- HotSpot and PACT refuse a cold plate (`model.check_one_sink`); this is a 3D-ICE-only check.
