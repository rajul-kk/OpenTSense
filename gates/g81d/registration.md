# G81d registration (written 9 Nov 2026, after the K = 2 plumbing dry run and before any main run; bars fixed now)

### G81d: sustained CPU→accelerator offload on a real SoC: looped Gemmini kernels without CPU checks (RQ2) · REGISTERED

- **Why.**
  - G51 measured CPU and accelerator phases on Chipyard (Rocket + Gemmini). Rocket retirement and Gemmini busy were strongly anti-correlated (r = −0.98 over 1,000-cycle windows). But each program ran its kernel once: 37k to 4.3M cycles, at most about 4 ms at 1 GHz. That is too short for a die to heat up (G44's phases are 1–200 ms).
  - Real accelerator use repeats a kernel (layers, batches, frames) with no CPU check in between. G81d measures what the two dies do over that sustained offload, rather than assuming it, so that later families can use measured duty cycles and cross-die correlation.
- **Set-up.**
  - G51's simulator, unchanged: `~/g51/chipyard`, commit `157dd69`, `GemminiRocketConfig`, Verilator, with G51's `act_mon` counters (instructions retired by Rocket; Gemmini `io_busy`, per 1,000 cycles). Fast preload, as in G51 technical note 3.
  - Three looped copies of G51's workloads, written by `make_src.py` without changing the originals: `tiled_matmul_ws_perf` (K = 100), `conv_perf` (K = 4) and `mlp1` (K = 3). Each wraps the original compute region in a K-iteration loop ending in `gemmini_fence()`. It records `rdcycle` at every iteration start and after the last iteration, and prints the stamps only once, at the end. Data are as in G51 (the tests' zero-initialised arrays); Gemmini's timing does not depend on data values.
  - Built by `build.sh 100 4 3 g81d/main` and simulated by `sim.sh` with a cap of 30M cycles. Binary hashes are recorded in `sha256.txt`.
  - Dry run (`~/g81d/dry`, K = 2, matmul only): stamps at 27,296 / 64,500 / 101,709, so iterations of 37,204 and 37,209 cycles; rc 0; 2,000 cycles/s.
- **Validity (v):** iteration 1 of each looped test takes within 1% of the cycles G51 recorded for the unlooped test: matmul 37,227; conv 2,197,389; mlp1 4,314,792 (the sum of the per-layer counts). If (v) fails, the gate is INCONCLUSIVE (the loop changed the workload).
- **Pass if all hold:**
  - **(a) Complete runs:** all three exit with rc 0, print `G81D_DONE K` and all K + 1 stamps, and at least 99% of the expected `ACT` windows for both counters parse. Some lines are interleaved with program output, so a few can be lost.
  - **(b) Steady state is periodic, so it can be extended:** the durations of iterations 2..K each lie within 1% of their median; and per iteration, the Gemmini busy fraction and the Rocket retire fraction (from overlap-weighted windows) each lie within 0.01 (absolute) of their median over iterations 2..K. For conv and mlp1, K − 1 = 3 and 2 iterations are compared.
- **Reported, not gated (predictions where stated):**
  - Steady-state duty cycles per workload. **Prediction:** Gemmini busy ≥ 0.9 and Rocket retire ≤ 0.1 for conv and mlp1 (G51: mlp1 was busy in 4,316 of 4,361 windows); matmul lower, because the CPU issues commands for small tiles.
  - Window-level Pearson r(retire, busy) in steady state, per workload. **Prediction:** negative for conv and mlp1, as G51 found.
  - Iteration 1 against the steady state (cold-start effect).
  - Gaps between iterations (loop overhead plus fence) as cycles and as a fraction of the iteration.
  - The deliverable, not a bar: per-workload steady-state timelines (1,000-cycle windows, one period) in `runs/main/timelines.npz`, for the family that uses them (G81c-style F5, to be registered separately).
- **A fail means:** record it in `failures.md`. If (b) fails, steady state is not periodic at this length, and a timeline cannot be extended by repetition; it would have to be simulated in full.
- **Not claimed:**
  - power or temperature: the activity-to-power mapping and the thermal run belong to the family gate that uses these timelines;
  - Rocket ≠ ibex and Gemmini ≠ the ASAP7 TPU of G36; that is the same stand-in as G51;
  - memory-system activity (G81e);
  - an OS or a full application.
- **Note (9 Nov, after the registration and before the main run; no bar or prediction changed):** testing `evaluate.py` on the K = 2 dry log gave matmul iteration 1 −0.06% from G51, steady-state busy 0.992, retire 0.022 and r = −0.96. So the "matmul lower" prediction, written before this, already looks wrong; it is left as registered.
- **Code and output:** `make_src.py`, `build.sh`, `sim.sh`, `run.sh`, `evaluate.py`; logs in `~/g81d/main/`, copied to `runs/main/` with `result.json`.
