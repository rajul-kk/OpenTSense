# G81e draft (written 10 Nov 2026; NOT registered: bars below are proposals for the student to fix)

### G81e: Memory-die power follows the workload (RQ2) · DRAFT

- **Why.** G50b gave the memory die random bank use (20 to 100% per draw), so memory power is independent of what the
  CPU runs (`PIPELINE.md` seam 3). G81b now has whole-program timelines for 19 Embench-IoT programs and the idle
  program. G81e turns each program's own memory requests into DRAM commands, runs DRAMPower, and maps the energy onto
  the memory die's banks per 1,000-cycle window, so the memory die's power map follows the same program as the CPU die.

- **What exists, checked 10 Nov.**
  - G81b's testbench (`../g81b/tb/`) serves a 256 KB single-cycle array and logs no requests. The G81b VCD windows
    hold the ports, but only 20 windows per program, not the whole run.
  - DRAMPower 6.3.1 and the LPDDR4-3200 x16 memspec from G50a (`../../../experiments/code/sens/g50a.py`, in WSL, not
    in the image).
  - `opentsense/power/dram.py`: the parametric bank layout used by G93a; G81e fills its `mix` and `active_W` from the
    trace instead of a Dirichlet draw.

- **Set-up (proposed).**
  1. **Request trace.** Re-run each G81b program once at RTL (Verilator, the same ibex commit, testbench and hex) with
     a trace port that writes `cycle, port (I/D), we, addr, be` for every granted request. Same core, same program, so
     the request stream is the gate-level one; validity (v1) checks that.
  2. **Memory hierarchy (stated assumption, the main design choice).** G81b's memory is ideal. Two variants, both
     reported, one gated:
     - **H1 (gated): 4 KB I-cache + 4 KB D-cache, 2-way, 64 B lines, write-back, in front of DRAM.** Misses and
       write-backs become 64 B DRAM transactions. A microcontroller-class core with a memory die.
     - **H0 (reported only): no cache.** Every request is a DRAM access; an upper bound on traffic.
  3. **Controller.** A small in-order, open-page controller (`opentsense/power/dramctl.py`): address map row:bank:col,
     LPDDR4-3200 timings from the memspec (tRCD, tRP, tRAS, tRRD, tFAW, tCCD, tWR, tRTP, tREFI/tRFCab), CPU at 1 GHz.
     Output: DRAMPower's command CSV.
  4. **Energy.** DRAMPower reports one total per trace, so windows come from its linear energy model
     (`opentsense/power/dramenergy.py`): per-command energies, background per cycle (per bank when all are closed,
     shared when any is open, an all-bank refresh counting as open for tRFCab), interface energy per cycle and per
     command. The coefficients are fitted once to DRAMPower on 4 calibration traces; each 1,000-cycle window (CPU
     cycles) then gets per-bank and interface energy from its own command counts and durations, the shared background
     split by each bank's open time. `dram.window_maps` puts bank energy on the bank areas and interface energy on the
     TSV/IO strip. Dry check (11 Nov, `dry/fit_energy.json`): fit residuals ≤ 2e-15; on 5 held-out traces the total
     is within 0.022% of DRAMPower and per-bank core energy is exact. DRAMPower's static interface energy (about 2e-5
     of the total) is not modelled.
  5. **Output.** Per program: `mem_timeline.npz` (window × bank power), summary in `result.json`, manifest.

- **Noise floor (to measure before fixing the bars; `plan.md` §2.1).** Repeat steps 3 and 4 for each program under
  5 seeds of the refresh phase and of the bank-hash XOR of the address map. The floor of each gated metric is its
  spread over those seeds.

- **Pass if all hold (proposed):**
  - **(v1) Validity, trace:** each program's RTL run ends at the same cycle as G81b's gate-level run (`run.cycles` in
    `../g81b/record/result.json`) and prints the same checksum; on the 20 G81b windows, the traced request count equals
    the count of granted requests in the gate-level VCD. If (v1) fails, the gate is INCONCLUSIVE.
  - **(v2) Validity, controller:** an independent checker finds 0 timing violations in every command trace, and on
    G50a's streaming trace DRAMPower reproduces G50a's 6.2 pJ/bit within 1% (regression of the tool set-up).
  - **(v3) Validity, energy model (proposed 12 Nov):** for every program's whole trace, the summed window energies are
    within 0.1% of one DRAMPower run on that trace (one run per program; the dry check's worst was 0.022%).
  - **(a) Memory power follows the program:** under H1, the mean memory-die dynamic power differs between programs by
    more than 3× the noise floor for at least 15 of the 19 programs against the suite median; and within programs,
    per-window DRAM power correlates with the per-window miss count at Pearson ≥ 0.9.
  - **(b) It is not G50b's random use:** the per-bank share differs from a uniform share by more than 3× the floor in
    at least one bank for at least 15 programs (the map has structure the random draw cannot reproduce on purpose).
- **Reported, not gated:** H0 against H1 traffic; idle against compute; miss rates; DRAM power against the CPU-die
  power from G81b per window (cross-die correlation, the input G81c-style recovery needs); bank maps per program.
- **A fail means:** (a) fails: under a microcontroller-class hierarchy the memory die's power is set by refresh and
  background, not the workload; record it, and the benchmark keeps the parametric die with that stated reason.
- **Not claimed:** HBM currents (LPDDR4 stand-in, as G50a); no real memory controller or DRAM layout; Embench is
  small, so traffic after the caches is mostly compulsory misses.
- **Effort:** about one week (trace testbench 1 day, controller and checker 2 days, runs and evaluation 2 days).
- **Decisions for the student before registration:** H1's cache sizes; whether DRAMPower moves into the image (needed
  for G91's reproducibility); the bar numbers after the noise floor is measured.

## Student decision (12 Nov 2026)

H1 is the gated hierarchy and H0 is reported only, as written. Bar numbers still follow the noise-floor rule of `plan.md` 2.1 where it applies.

**Dry fit rerun (16 Nov 2026, after the 12 Nov review changed controller traces).** `fit_energy.py` unchanged, record
`dry/fit_energy-rerun-20261116.json` beside the first (`dry/fit_energy.json`, kept as run): largest calibration
residual 2e-15 relative, worst held-out total error 2.21e-4 (was 2.21e-4), worst per-bank error 3e-16. The model's
numbers can be quoted as of this rerun.

## Step 1, run 1 (16 Nov 2026; `step1/`, outputs in `runs/step1-main/`, gitignored)

All 20 G81b programs ran in G81b's gate-level testbench with the request log added (`step1/build_sim.sh`; the
testbench differs from G81b's by the 8 inserted lines only). Check (v1): each run ends with G81b's result and cycle
count, and in each of G81b's 20 windows per program the trace holds exactly the requests the VCD shows.

| | Programs |
|---|---|
| v1 passed (result, cycles and every window's requests equal) | 18 |
| v1 failed | 2: md5sum, nettle-aes |

Both failures are harness faults, not testbench ones: their traces were written during the first launch, which was
interrupted (session memory guard), and the resume rule accepted them because each had a RESULT line and a gzipped
trace. nettle-aes's trace starts at cycle 272951 instead of 6; md5sum's first windows match and later ones do not. Both
ended with G81b's result and cycles. Fix: a program is skipped only with an `ok` marker written after simv exits 0 and
its trace is gzipped (`step1/run.sh`); the 18 verified programs were marked from `v1-run1.json`, the two failed
directories kept as `*.run1`, and only those two rerun. Run 1's check is kept as `v1-run1.json` and `job-run1.log`.
