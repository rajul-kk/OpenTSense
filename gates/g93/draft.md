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
