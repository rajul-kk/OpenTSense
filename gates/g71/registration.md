# G71 registration (moved from fyp/todo-gates.md after the run)

### G71: Stack file to 3D-ICE and PACT, agreement within 1 K (O1) · RAN 1 Nov: PASS
- **Why:** this is the proposal's testbed criterion ("agrees with its reference tools to within 1 K"). It re-checks G47 (3.6% / 1.9%) and G35a inside the FYP code.
- **Set-up:**
  - One YAML stack format, converted to both 3D-ICE `.stk` and PACT.
  - Three stacks:
    1. single 3×3 mm die;
    2. two-die 3D stack (the G38 3D-A geometry, HTC 5e4);
    3. 2.5D: two dies on a silicon interposer.
  - Inputs are 4 real-activity power maps from the G38 CPU/TPU dies.
  - Also build the response operator and compare it with full solves.
- **Metrics:**
  - Per stack: |peak-rise difference| and RMS field difference between 3D-ICE and PACT.
  - Max error of the operator against a full solve.
- **Pass if every stack meets all of these:**
  - |Δpeak| ≤ 1 K **and** ≤ 4% of the peak rise;
  - RMS difference ≤ 2% of the mean rise;
  - operator vs full solve ≤ 0.1 K.
- **A fail means:** a converter or meshing bug, or a real solver disagreement. If it's a real disagreement, record it in `findings.md` as a solver-provenance result.
- **Effort:** 3 days · **Output:** `gates/g71/`
- **Amendment 1 (1 Nov, before the run on the test maps).** Development checks on synthetic maps, not the test maps; their scripts and outputs are in `gates/g71/`:
  - **Mesh.** With one node per layer, PACT (node at each layer's bottom face) and 3D-ICE (node at the cell centre) disagree by 0.8 to 2.7 K at hotspots on the two-die stack. When layers are split into sublayers, both tools converge to the same answer: 3D-ICE barely moves and PACT closes the gap (`dev_mesh.py`). The stacks therefore use per-layer sublayers (`n_sub`, the "Lm" level): copper 10, TIM 3, 50 µm die bulk 6, bond 3, 100 µm silicon 8. The one-node mesh is still reported as an extra.
  - **Image.** The finer mesh exceeds SuperLU_MT's fixed fill-in allocation inside 3D-ICE, so the Dockerfile raises the `sp_ienv` factors (50 to 400×, 30 to 250×). This changes allocation only, not the arithmetic. Image `opentsense:g71dev`.
  - **Maps.** The G38 draws (seeds 0 to 3) are regenerated exactly (powers match G38): single die = TPU map; 3D = TPU die on top, CPU die below, face to face (the G38 3D-A geometry); 2.5D = CPU and TPU chiplets (2 × 2 mm, 0.2 mm apart) on 20 µm micro-bumps and a 100 µm silicon interposer. 3D-ICE can't vary the material inside a layer, so the chiplet layer is silicon across the whole footprint (monolithic approximation, the same in both tools).
  - **Criteria** apply per die and per draw (worst case). The RMS bar uses 3D-ICE's mean rise for that die.
  - **Operator.** Built from PACT's own conductance matrix (captured, then factorised once). The basis is one column per active-block cell plus one for each die's uniform dark power, which is exact for these maps, so the check tests superposition and indexing rather than binning. Operators with 100 µm and 200 µm bins are reported as extras. PACT writes temperatures rounded to 0.01 K, so up to 0.005 K of any operator difference is rounding.

