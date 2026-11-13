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
