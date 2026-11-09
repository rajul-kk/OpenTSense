# G93a: three thermal solvers (3D-ICE, PACT, HotSpot) and the extended stack format · PASS (7 Nov 2026)

Registration and Amendment 1: `registration.md`. Run: `gates/g93a/run.sh main` in `opentsense:g93a` =
`sha256:76e2685256694157a3b1937008377de4f8554be7b712776f88dbbde878716e98` (HotSpot 7 `f18831e` with the 6-decimal dump and
the `LINE_SIZE` patch; PACT label patch). Output `runs/main/` (`result.json`, `manifest.json`, `run.log`, per-stack
`*_fields.npz`). Wall time 3 h 32 min (12,728 s), sharing the machine with the G92e dry-run probes.

**Amendment 1 (before the scored run, no bar changed).** The first run stopped on the two-die 3D stack: HotSpot's power
trace line (one value per source cell, two 60 × 60 dies, about 115,000 characters) exceeded its 65,536-character line
buffer (`error: line too long`). The patch raised the buffer to 1,048,576; everything else in the image is identical.
The aborted run is kept in `runs/aborted1/` and not scored. The rerun reproduced its single-die results exactly.

## Verdict: PASS on (a), (b) and (c)

Bars: (a) max |difference| to G71's stored fields ≤ 1e-9 K; (b), (c) per die and seed, |Δpeak| ≤ 1 K and ≤ 4% of the
peak rise, RMS difference ≤ 2% of the mean rise.

| Stack | Part | Regression vs G71 (3D-ICE, PACT) | Worst \|Δpeak\| | Worst \|Δpeak\| / peak | Worst RMS / mean rise | Verdict |
|---|---|---|---|---|---|---|
| single 3 mm die | a, b | 0 K (exact) | 0.414 K | 0.67% | 0.45% | PASS |
| two-die 3D (TPU over CPU) | a, b | 0 K (exact) | 0.226 K | 0.37% | 0.23% | PASS |
| 2.5D chiplets on interposer | a, b | 0 K (exact) | 0.234 K | 0.42% | 0.28% | PASS |
| 2.5D, underfill with silicon regions | c | — | 0.246 K | 0.45% | 0.37% | PASS |
| two-die 3D, heat sink on the bottom | c | — | 0.229 K | 0.35% | 0.17% | PASS |

Per pair (worst over dies and seeds):
- **HotSpot vs 3D-ICE: ≤ 0.009 K** on every stack and seed (RMS ≤ 0.04% of the mean rise). The two solvers are
  numerically the same model here: same grid, same cell-to-ambient film once HotSpot's 1.5× convection count is
  compensated, both with one cell-centred node per sublayer.
- **HotSpot vs PACT and 3D-ICE vs PACT: 0.02 to 0.41 K**, the same gap G71 found between 3D-ICE and PACT (PACT always
  slightly cooler). It is PACT's node placement: PACT puts each layer's node on the face away from the sink, the others
  at the centre (measured for iceforge's PACT backend the same day, `fyp/tools/iceforge/README.md`).
- Buried dies agree more closely than exposed ones: CPU die under the TPU ≤ 0.04 K, and ≤ 0.03 K with the sink on the
  bottom (there the CPU die is next to the sink).

## Reported, not gated

**One node per layer (seed 0, peak rise K).** 3D-ICE and HotSpot stay together (≤ 0.008 K); PACT moves away by 0.5 to
3.3 K, as in G71:

| Stack | Die | 3D-ICE | PACT | HotSpot |
|---|---|---|---|---|
| single | die0 | 63.668 | 60.36 | 63.661 |
| 3d | top / bot | 62.798 / 51.539 | 60.40 / 50.60 | 62.790 / 51.531 |
| 25d | chiplets | 54.440 | 52.08 | 54.437 |
| 25d_regions | chiplets | 54.908 | 52.48 | 54.905 |
| 3d_bottom | top / bot | 66.350 / 37.041 | 66.84 / 36.57 | 66.344 / 37.036 |

**Refined mesh (3d, every n_sub doubled, seed 0, peak rise K).** 3D-ICE 61.813 / 50.487 (top / bottom; −0.011 /
−0.005 K from the registered mesh), HotSpot 61.805 / 50.478, PACT 61.73 / 50.48. PACT closes from 0.23 K to 0.08 K below
3D-ICE: its gap is the vertical discretisation and shrinks with the mesh. Wall time: 3D-ICE 336 s, PACT 441 s, HotSpot
2,855 s (8.3 GB resident at its peak: SuperLU fill grows fast with the layer count).

**Underfill gap vs G71's monolithic 2.5D layer (3D-ICE peak rise, seeds 0 to 3).** 54.005, 56.809, 55.186, 56.418 K
against 53.558, 56.327, 54.714, 55.940 K: the 0.2 mm underfill gap between the chiplets (k = 0.7 instead of silicon)
raises the peak by 0.45 to 0.48 K (about 0.85%). G71's monolithic approximation was a small error on this stack.

**Bottom sink.** With the sink under the CPU die, the CPU's peak rise falls from 50.5–52.9 K to 36.2–37.9 K and the TPU's
rises from 61.8–64.7 K to 64.2–67.4 K; all three solvers agree on both (a solver check of the bottom boundary, not a
realistic package).

**Mean wall time per solve (s), registered mesh.** single: 3D-ICE 20, PACT 58, HotSpot 73; 3d: 58, 104, 214;
25d: 149, 176, 392; 25d_regions: 104, 169, 377; 3d_bottom: 44, 95, 209. HotSpot is the slowest everywhere.

## What this does and does not show

- The converter and image changes of 7 Nov moved none of G71's 3D-ICE or PACT answers.
- HotSpot is a working third solver on these stacks, with lateral material regions and either sink side.
- Not shown (as registered): accuracy against measurement or FEM; anisotropic materials; HotSpot's own package model.
  HotSpot and 3D-ICE agree so closely partly because the translation makes them the same discretisation; their
  agreement is a check of the converters and boundary handling, not two independent physics models. PACT, with its
  different node placement, is the more independent of the three.
- HotSpot's memory and time on the refined mesh (2,855 s, 8.3 GB) matter for G93's bigger stacks: plan for the
  registered mesh, or watch memory.
