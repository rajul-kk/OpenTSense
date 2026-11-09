# G81d2 registration (written 10 Nov 2026, after G81d's INCONCLUSIVE and before any G81d2 run; bars fixed now)

### G81d2: G81d with G51's data layout kept · REGISTERED

- **Why.** G81d was INCONCLUSIVE on (v): the added static stamp array moved conv's data buffer onto a 64-byte boundary, and Gemmini's DMA then did about 9% less work than in G51 (`../g81d/README.md`). G81d2 repeats G81d with the cause removed and nothing else changed.
- **Changes from G81d (only these):**
  - stamps on the stack (`make_src.py --stack`);
  - `.text` padded so that every DMA buffer lands exactly 4,096 bytes above its address in G51's binary (`build.sh 100 4 3 g81d/main2 --stack`, two passes; pads mm 4,032, conv 4,000, mlp1 4,000 bytes);
  - a build check, `layout.py --check`: all 18 DMA buffers (mm `full_A–D`; conv `heap`; mlp1 `weights0–5`, `inter_results0–5`, `input_mat`) shifted by exactly 4,096. Verified at registration: LAYOUT_OK.
- **Unchanged from G81d:** simulator, workloads, K = 100 / 4 / 3, the 30M-cycle cap, `evaluate.py`, and the bars and predictions below (copied from G81d).
- **Validity (v):** iteration 1 of each looped test takes within 1% of the cycles G51 recorded for the unlooped test (matmul 37,227; conv 2,197,389; mlp1 4,314,792). If (v) fails, the gate is INCONCLUSIVE.
- **Pass if all hold:**
  - **(a)** all three runs exit with rc 0, print `G81D_DONE K` and all K + 1 stamps, and at least 99% of the expected `ACT` windows parse for both counters;
  - **(b)** the durations of iterations 2..K each lie within 1% of their median, and per iteration the Gemmini busy fraction and the Rocket retire fraction each lie within 0.01 of their median.
- **Reported, not gated:**
  - steady-state duty cycles, window-level r(retire, busy), iteration 1 against steady state, and gaps between iterations;
  - `timelines.npz` (one steady period per workload);
  - G81d's predictions, kept as registered there: Gemmini busy ≥ 0.9 and retire ≤ 0.1 for conv and mlp1; matmul lower; r negative for conv and mlp1. G81d's INCONCLUSIVE run already showed matmul at 0.993 busy; this is disclosed here and the prediction is not changed.
  - **New for G81d2:** iteration-1 cycles of G81d (wrong alignment) against G81d2 per workload, as the measured alignment sensitivity.
- **A fail means:** record it in `failures.md`. If (b) fails, a timeline cannot be extended by repetition.
- **Not claimed:** as G81d (no power or temperature; Rocket/Gemmini are stand-ins for ibex/TPU; no memory system; no OS).
- **Code and output:** `../g81d/{make_src.py,build.sh,layout.py,sim.sh,evaluate.py}`, `run.sh` here; output in `runs/main/`.
