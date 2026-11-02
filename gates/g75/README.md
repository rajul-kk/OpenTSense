# G75: shortcut errors re-measured

**Verdict: INCONCLUSIVE, partial (2 Nov 2026).** Registration and Amendment 1: `registration.md`. Partial result: `result.json`. Not a pass.

| Shortcut | Status | Result |
|---|---|---|
| (1) Default vs real, IHP ibex | Done | 1.732 (recorded 1.731) |
| (1) Default vs real, cva6 | **Not run** | Stopped by host low memory at the first window |
| (1) ASAP7 ibex, TPU | Done | 3.02, 1.63, against the mean of the real windows (G72 data) |
| (2) Library vs SPICE leakage | **Could not run** in this run | Models are now in `opentsense:g75spice`. An unregistered check matches G53 exactly (`spice_check/`); a formal re-run needs Amendment 2 |
| (3) Stack peak shift | Done | 1.31 to 1.53 K, G71 3D stack in PACT |

To finish cva6, with other apps closed: run only the `cva` steps of `run.sh`, one window at a time, then `evaluate.py`. `cva6_power.tcl` now loads only the library versions G52 used.
