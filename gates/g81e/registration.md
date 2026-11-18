# G81e registration (written 16 Nov 2026, before the gated run)

### G81e: Memory-die power follows the workload (RQ2) · REGISTERED

- **Why.** G50b gave the memory die random bank use, so memory power is independent of what the CPU runs
  (`PIPELINE.md` seam 3). G81e turns each G81b program's own memory requests into DRAM commands and energy per
  1,000-cycle window, so the memory die's power map follows the program the CPU die runs. Draft and its history:
  `draft.md`.

- **Set-up.**
  - **Requests (step 1, done before registration):** each of the 19 Embench-IoT programs and the idle program re-run
    at RTL (Verilator, G81b's ibex commit, testbench and hex) with a trace port; `step1/`, outputs in
    `runs/step1-main/<program>/req.txt.gz`.
  - **Hierarchy:** H1 (gated) is a 4 KB I-cache plus a 4 KB D-cache, 2-way, 64 B lines, write-back
    (`opentsense/power/cache.py`); H0 (no cache) is reported only (student, 12 Nov).
  - **Controller:** `opentsense/power/dramctl.py`, in-order open-page, LPDDR4-3200 x16 (the memspec DRAMPower
    reads; checked equal at start), CPU at 1 GHz.
  - **Energy:** the linear model fitted to DRAMPower 6.3.1 (`dry/fit_energy-rerun-20261116.json`,
    `opentsense/power/dramenergy.py`), per window of 1,000 CPU cycles. **Dynamic** energy = ACT, PRE, RD, WR
    (core) plus interface energy per command and per burst; **total** adds background, refresh and interface
    energy per cycle.
  - **Seeds:** per program, under H1, the nominal schedule (no bank hash, refresh phase 0) and 5 seeds s = 1..5
    with bank-hash salt s and refresh phase 997 s mod tREFI. H0 runs the nominal schedule only.
  - Code: `step2/run.py` (compute), `step2/g50a_check.py`, `step2/evaluate.py` (bars). Laptop host, DRAMPower in
    WSL; one heavy slot of 2 GB (H0 on xgboost about 1.4 GB, extrapolated from crc32).

- **Noise floor (student, 16 Nov 2026).** Each gated value is the **mean over seeds 1-5**; its floor is the
  **range (max - min) over those 5 seeds**, measured in the gated run itself. The nominal schedule is reported
  only (on crc32 it reads outside the seeds' spread, so it is not mixed into the floor).

- **Pass if all hold.** "Programs" means the 19 Embench-IoT programs; idle is reported only.
  - **(a1) Memory power differs by program:** with m_p the mean dynamic power of program p (W), at least 15 of 19
    programs have |m_p - median(m)| > 3 × max(floor_p, floor_med), where floor_med is the floor of the program
    whose m is the median.
  - **(a2) It follows the misses (student, 16 Nov: dynamic power against fills):** at least 15 of 19 programs have
    a Pearson correlation >= 0.9 between per-window dynamic energy and per-window cache fills (misses; write-backs
    not counted) in **every** seed 1-5. A program with no variance in either series does not count.
  - **(b) The bank map has structure (student, 16 Nov: sorted shares):** a program's bank shares of dynamic core
    energy, sorted high to low and averaged over seeds, are S_1 >= ... >= S_8, with floor_k the range of the k-th
    sorted share over seeds. The program counts if some k has |S_k - 1/8| > 3 × floor_k. At least 15 of 19 count.
    Sorted shares do not depend on which bank index the hash picks.

- **Validity (any failing makes G81e INCONCLUSIVE).**
  - **(v1) Trace:** met in step 1 before registration (run 2: 20 of 20 programs end at G81b's cycle, print its
    checksum, and match the request counts of the 20 G81b windows).
  - **(v2) Controller:** 0 violations from `dramctl.check` in every command trace (all seeds, H1 and H0); and G50a's
    streaming trace reproduces its recorded pJ/bit within 1% (`g50a_check.py`).
  - **(v3) Energy model:** per program, the nominal H1 trace's summed window energy is within 0.1% of one DRAMPower
    run on that trace.

- **Reported, not gated.** Dynamic share of total power per program; nominal against seed mean; H0 against H1
  traffic and power; idle against compute; miss and write-back counts; bank maps per program (`<program>_H1.npz`).
  The cross-die correlation with G81b's CPU-die power is left to the case sets that use these maps.

- **A fail means.** (a1) or (a2) fails: under a microcontroller-class hierarchy the memory die's workload-driven
  power is too small or too uncorrelated to set its map; the benchmark keeps the parametric die with that reason.
  (b) fails: the bank map is as flat as G50b's random use, so per-bank structure is not a claim.

- **Not claimed.** HBM currents (LPDDR4 stand-in, as G50a); no real memory controller or DRAM layout; Embench is
  small, so traffic after the caches is mostly compulsory misses, and dynamic power is a small share of the total
  (seen on crc32 below); the total is dominated by background and refresh, which do not follow the program.

- **Code and output.** `step2/`; output in `runs/main/`; after the run, `python scripts/record_gate.py G81e`.

### Seen before registration (declared)

- Dry fit and its rerun (`dry/`): calibration residual 2e-15, held-out total error 2.21e-4.
- Step 1 (v1): see `draft.md`, runs 1 and 2.
- G50a check, 16 Nov: 6.2187 pJ/bit now and recorded (difference 0).
- crc32 under H1, a smoke test of the runner on 16 Nov: 25 DRAM transactions; mean dynamic power 0.0745 mW at
  nominal and 0.0757 mW in each of seeds 1-5; total 42.60 to 42.62 mW; nominal bank shares 0.905 in bank 0 and
  0.095 in bank 7; v3 error 2.6e-4; Pearson of per-window **total** energy against per-window transactions 0.254.
  The student fixed the floor population, (a2)'s pairing and (b)'s statistic after this was seen (questions put
  in terms of the problem, not the values).
- xgboost timing run: 4,666,319 requests; H1 85,064 transactions (I-cache 10 misses, D-cache 83,312 misses,
  1,742 write-backs), 196,712 commands, 0 violations. crc32 under H0: 799,281 requests, 803,501 commands.

### Fixed by code review before the run (16 Nov 2026, still before any gated output)

- **Bank hash.** `dramctl.map_address` added the salt before a 7-bit shift, so salts 1-5 moved under 3% of rows and
  the floor measured little but the refresh phase. The salt now enters a multiplicative hash of the row (about 7/8
  of rows change bank between any two salts; tested). The crc32 smoke numbers above were made with the old hash.
  The dry fit's held-out traces used the old hash too; they test the energy model, which does not depend on it.
- **Windows.** Windows now end at the trace's END (the last one partial), not at the next multiple of 1,000 cycles,
  which booked up to ~1,600 DRAM cycles DRAMPower never simulates into v3. A controller backlog past the program's
  end (H0) gets its own windows, and mean powers divide by the trace's length.
- **Floors of zero.** A bar also needs |S_k - 1/8| > 1e-6 for (b) and a difference above 1e-6 of the median power
  for (a1), so a zero floor cannot pass a rounding difference.
- **G50a check.** DRAMPower's earlier `~/g50/out.json` is removed first; G50a's script reads it without checking
  DRAMPower's exit. Rerun after the fix: see the run's `g50a.json`.
- Dynamic energy is now `dramenergy.DYNAMIC` (the model owns the split), and refresh's own commands (PREA, REFA)
  and the banks a PREA closes are background, as the set-up says; a refresh-only trace has zero dynamic energy
  (tested). Window count follows the program's end, so a program ending on a window edge gets no sliver window.
- Per-program results record the hashes of their code, trace and DRAMPower binary and memspec; a resume from other
  inputs stops. (Last review, 16 Nov.)

Amendments go below, dated, each with the reason. Never re-run until it passes.
