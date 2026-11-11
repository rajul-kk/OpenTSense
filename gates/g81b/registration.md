# G81b registration (written 8 Nov 2026; bars fixed now; unblocked by G81x PASS; Amendment 1, 9 Nov, below)

### G81b: Whole-program power timelines on the routed ASAP7 ibex: Embench-IoT plus scripted idle phases (RQ2/RQ3, O1) · REGISTERED, BLOCKED on G81a
- **Why.** See G81a, "Activity gap". The testbed's CPU power comes from 4 short kernels with an 11% power spread and no idle phases. G81b replaces them with whole real programs, measured as power against time on the routed core.
- **Programs.**
  - Embench-IoT at pinned commit `09c2ed8c3b70`, all 19 benchmarks, rv32imc.
  - Built in a pinned compiler container (`gcc-riscv64-unknown-elf` from Ubuntu 24.04; its version is recorded) with a board support package for the G72 testbench:
    - start and stop markers;
    - Embench's own `verify_benchmark()` result written to 0x8000;
    - the done flag at 0x8004.
  - `LOCAL_SCALE_FACTOR` is set per benchmark so that each run is 0.5–3 million cycles. The factors are fixed in the dry run and recorded.
  - **Idle program** (new): alternating compute and `wfi`. Phases are 20,000 cycles of a G30 kernel, then 20,000 cycles asleep, woken by a testbench timer interrupt, repeated 10 times.
- **Testbench.** G72's ibex testbench with the memory enlarged to 256 KB and a timer-interrupt line driven at the programmed cycles. Everything else is unchanged.
- **Simulation and power.** Verilator, with the flags G81a passed, simulates each program to completion.
  - **Power windows:** OpenSTA power (as G72) on 1,000-cycle windows starting every W cycles. W is chosen so that each program has 20 windows, plus every phase boundary of the idle program.
  - **Activity timeline:** per-module toggle counts in every 1,000-cycle interval over the whole run, from the same simulation.
- **Pass if all hold:**
  - **(a) Correct programs:** every Embench benchmark's `verify_benchmark()` returns success on the gate-level core, and the idle program's checksum equals its host model.
  - **(b) Annotation:** at least 99% of pins annotated in every power window.
  - **(c) Timeline is consistent with power:** for each program, the window dynamic power predicted from the module toggle timeline agrees with OpenSTA's window power, with a Pearson correlation of at least 0.95. The prediction is a least-squares fit of window power on per-module toggle counts, fitted on half the windows and tested on the other half. This is what lets G81c use the timeline between power windows.
- **Reported, not gated:**
  - **The prediction to check:** the spread (max/min) of window dynamic power across the suite is wider than the G30 kernels' 1.11×.
  - The idle phases' power relative to compute, and the leakage share in idle windows.
  - Per-benchmark cycles, wall time and Verilator speed.
  - Per-module power shares.
  - The default-activity ratio (as G75) for every benchmark.
- **A fail means:** record it in `failures.md`. If (a) fails, the benchmark is dropped and the cause recorded, but the gate still fails. If (c) fails, G81c cannot interpolate between power windows and must use window power only.
- **Not claimed:**
  - an operating system, caches or a memory hierarchy (ibex with single-cycle memory, as G72);
  - absolute power density (the testbed scales magnitude, as before);
  - the TPU or other dies (separate gates).
- **Output:** `gates/g81b/runs/main/`

## Amendment 1 (9 Nov 2026, before any scored run; G81a's block lifted by G81x PASS)
Method changes from building and dry-running the gate (`dry/`, not scored). The pass bars (a), (b) and (c) keep their thresholds.
1. **Simulation.** Verilator with G81a's flags and **G81x's hold testbench** (`data_rdata` holds its value on writes; no X injection), which G81x passed against Icarus. Verilator ignores `$dumpoff`, so a C++ harness (`tb/main.cpp`) opens one VCD per window at the window's start cycle and closes it 1,000 cycles later. It exits with an error if the windows overlap, are unsorted, or any window is missing or truncated. Each VCD's names are fixed with G81a's `vcd_names.py` before OpenSTA.
2. **Testbench registers** moved from 0x8000/0x8004 to the top 256 bytes of the 256 KB memory (0x3FF00 result, 0x3FF04 done, plus timer set and clear, start/stop and phase markers; `tb/ibex_tb_g81b.v`), because programs need the low memory. The vector table is at 0 (ibex vectored `mtvec` = boot address), the timer interrupt at entry 7 and reset at 0x80. A run that ends without `done=1` counts as a failure of (a).
3. **Activity timeline per placement region, not per module.** The routed netlist is flat (no module names survive), so nets are grouped by their driver cell's location on a 4 × 4 grid of the die (`regions.py`: 20,334 nets; the 2 hierarchical adder blocks are not counted). Toggles are counted at each falling clock edge and summed per 1,000-cycle interval. The first sample only primes the counters. The last, partial interval is written with a negative cycle and never used.
4. **Fit for (c).** Window dynamic power (OpenSTA internal + switching) is fitted by least squares on an intercept plus the 4 quadrant (2 × 2) toggle sums of the window's own timeline row. Windows start on multiples of 1,000, so each is exactly one row. Windows are in time order; the even-numbered ones are the training half and the odd-numbered the test half. Pearson ≥ 0.95 on the test half, per program, with no exception for programs whose power hardly varies (a constant prediction counts as a fail). The relative RMS error is reported.
5. **Embench build.** `GLOBAL_SCALE_FACTOR=1`, `WARMUP_HEAT=0` and `CPU_MHZ=1` (in board support; not used for timing). Compiler: `gcc-riscv64-unknown-elf` 13.2.0-11ubuntu1+12, binutils 2.42-1ubuntu1+6 and picolibc 1.8.6-2 from the Ubuntu 24.04 apt snapshot 20261031T000000Z, with `-march=rv32imc_zicsr -mabi=ilp32 -O2`.
6. **Scale factors** (`scale.txt`) = round(1,000,000 / cycles per iteration at LSF 1), with a minimum of 1. All 19 benchmarks verified at LSF 1 in the dry run.
   - Resulting runs are 0.83–1.50M cycles, except **xgboost**: one iteration is 4.98M cycles, so it cannot be brought under 3M. It runs at LSF 1 (about 66 min). This is the one exception to the 0.5–3M range.
7. **Windows** (`windows.py`).
   - **Embench:** 20 windows, one per equal stratum of the first 95% of the predicted loop (start marker + LSF × dry-run cycles per iteration). The 5% margin is for loops that are not exactly linear in LSF. Windows lying outside the real start/stop markers are reported, not failed.
   - **Idle:** one window in the middle of each of the 20 phases and one holding each of the 19 interior phase boundaries (39), placed from a first pass without windows.
8. **Idle program.** The compute phase is G30's `k_crc` kernel (bitwise CRC-32 over 96 bytes), carried into `sw/idle.c` for the G81b memory map, run **2 passes** (about 16,900 cycles; one pass is 8,449). Each sleep is 20,000 cycles (measured 20,037). The host-model checksum is printed by the build.
9. **Fixes from the hidden-state check, made before scoring:**
   - the timer raise is ordered so a clear in the same cycle wins;
   - the counters' first-sample burst and the last partial interval;
   - the harness's window checks;
   - the build fails if `LOCAL_SCALE_FACTOR` is not substituted.
10. **Reported items.** The default-activity ratio (as G75) is deferred, to be computed afterwards from the same window VCDs. "Per-module power shares" become per-region (4 × 4) shares. The suite spread is reported both on program means and on single windows.
