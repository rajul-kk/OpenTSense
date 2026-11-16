# G100 registration (written 15 Nov 2026, before the gated run)

### G100: Activity windows and power maps regenerated on the G99 layouts · REGISTERED

- **Why.** G99 re-closed the ASAP7 layouts at TT (limit 4 in `plan.md`). Everything from the benchmark on, and G96,
  uses them, so their activity windows and power maps must be regenerated with G72's checked procedure, at each
  layout's own clock.
- **Set-up.** G72's pipeline, unchanged apart from the layouts and the clock:
  - layouts: `_build/g99/asap7-ibex-1400` (passed G99 bars 1-4) and `_build/g99/asap7-tpu-<ps>` once G99 passes it;
  - `gates/g72/sim.py` (Icarus, pristine cell models from the pinned ORFS image with the functional patch); the
    testbench clock is half the layout's SDC period (Ibex 700 ps); same windows (Ibex k0-k4, cycles 1500-2500; TPU
    W1-W3, cycles 600-1600), programs and TPU stimulus (seed 36) as G72;
  - OpenSTA power at TT in the pinned ORFS image (`opentsense/power/vcd_power.tcl`), one job at a time;
  - 32 × 32 tile maps binned by instance centre (`opentsense/power/maps.py`), as G72.
  - Run per design (`run.sh <design> <ps>`), Ibex now, TPU after G99; the verdict needs both.
- **Noise floor.** The pipeline is deterministic: G72 reproduced every instance's power exactly (max difference 0 W),
  so the repeat spread is 0. The bars are G72's, which are not numeric comparisons against a noisy reference.
- **Pass if all hold, per design:**
  - **(a)** Ibex: kernels 0-3 report `done` with the host-reference checksum. TPU: W1 and W2 each give 616 result rows,
    all equal to the reference; W3 gives none.
  - **(b)** Annotation ≥ 99% of pins in every VCD window.
  - **(c)** Every 32 × 32 map (windows and default activity) sums to within 0.1% of OpenSTA's design total.
- **Validity.** INCONCLUSIVE if a run is cut short by memory or a tool crash (re-run after fixing the host, recorded
  as an amendment); a wrong checksum is a FAIL, not a crash.
- **Reported, not gated.** Per window: total power, density, leakage share, peak-over-mean tile power, die area, set
  against G72 (old layout at its old clock). This is G99's bar 5 and limit 4's finding: how much the old layouts
  overstated power.
- **A fail means.** The new layouts or the pipeline cannot give checked windows; G96 and the benchmark wait, and the
  student decides.
- **Not claimed.** Zero-delay activity (limit 3; G96 measures it). One corner (TT, 25 °C).
- **Code and output.** `run.sh`, `evaluate.py`; output in `runs/<design>-<ps>/`, records in `record/<design>-<ps>/`.

Amendments go below, dated, each with the reason. Never re-run until it passes.

**Note (15 Nov 2026, review fix, no bar affected).** The reported `leak_share` and `n_inst` now count only placed leaf
instances, which are the ones the tile map uses. The hierarchical adder rows were double-counting their children.
On ibex-1400, k0's leakage share goes from 0.055% to 0.053%. Bars and verdict are unchanged (PASS). The record is
re-evaluated from the saved outputs.
