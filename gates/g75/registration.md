# G75 registration (copied from fyp/todo-gates.md before the run)

### G75: Shortcut errors re-measured in the FYP testbed (RQ1) · REGISTERED
- **Why:** these are the first RQ1 numbers to count as FYP results. They reproduce the exploratory findings in the clean code.
- **Set-up:**
  - **Designs:** ASAP7 ibex, ASAP7 TPU, IHP SG13G2 ibex, and cva6 if G52's build ports in time.
  - **Shortcuts tested:**
    - (1) default activity against real activity, on total and per-tile power;
    - (2) library leakage against SPICE leakage at 25, 75 and 100 °C;
    - (3) fixed 25 °C leakage against the coupled loop, on the stack peak.
- **Pass if all hold (this is a reproduction gate):**
  - every ratio is within 10% of its exploratory value: cva6 default/real 2.1 to 2.2×, IHP 1.73×, IHP library leakage 0.89 to 1.5× of SPICE;
  - the per-tile errors are reported as a new number;
  - the stack-peak shift is recorded.
- **A fail means:** an earlier result doesn't reproduce. That is itself a finding; investigate and record it.
- **Effort:** 2 to 3 days · **Output:** `gates/g75/`

## Amendment 1 (2 Nov 2026, before the run)
- **The IHP library-leakage figure in the bar is wrong.** "0.89 to 1.5× of SPICE" leaves out `nor2_1_11` at 4.23×. G53's record is 0.89 to 4.23×, median 1.03. The registered summary came from a partial reading; `findings.md` and the proposal text should be corrected.
- **cva6 is required, not optional.** Its routed database, SPEF and waveforms all exist.
- **"Within 10%" of a range** means inside [0.9 × low, 1.1 × high]:
  - cva6 default ÷ each busy window k0 to k2: 1.89 to 2.42;
  - IHP default ÷ mean of k0 to k3: 1.558 to 1.904 (G53's definition, typ 1.2 V 25 °C).
- **Corner.** G52's numbers used ORFS's default ASAP7 **FF** libraries, while G34/G36 and G72 use TT. G75 repeats FF for cva6 so it is a true reproduction. The difference is recorded, not corrected: cva6 and ibex power are not on the same corner.
- **Reuse, as in G72.** Rerouting is not part of the gate, and neither is re-simulation: the IHP and cva6 waveforms from G53 and G52 are reused. Those are the checksummed simulations those gates accepted. Only the pinned-image power step, tile maps and ratios are re-run. ASAP7 ibex and TPU come straight from G72's clean run.
- **Per-tile metrics (new numbers).** For default against each real window, on 32 × 32 tiles: relative L2 error; the same after scaling default to the real total (pattern error alone); worst tile ratio.
- **Shortcut (2) cannot be fully re-run within the current working boundary.** G53's SPICE needs the IHP device models, which are only in the WSL home folder (outside `D:\Work\FYP-search`, the only place this work may touch), and the testbed image has ngspice but no OSDI models, contrary to `plan.md`. The ASAP7 cell decks are also in WSL. Only the library half is re-read from the pinned image. **So (2) is COULD NOT RUN, and it cannot support a PASS.** If everything else holds, the gate's verdict is INCONCLUSIVE, recorded in `failures.md`, and it is not to be re-scored against the old SPICE numbers.
- **Shortcut (3)** runs on the clean G71 3D stack in PACT, seeds 0 to 3: per-cell leakage shares 0.4% (TPU) and 0.035% (CPU) at 25 °C, G41's curves without the 125 °C row, iterated until the peak moves < 0.02 K (PACT writes 0.01 K). The peak shift is recorded; there is no bar.
- **Host memory.** cva6 runs alone, last, in a container capped at 10 GB. An out-of-memory kill of a cva6 window makes (1) COULD NOT RUN for cva6, not a fail.
