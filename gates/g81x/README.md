# G81x: G81a's gap is the testbench's X injection · PASS

Registration: `registration.md`. Run: `run.sh main`, 8 Nov 2026, 24.6 min. Output: `runs/main/` (`result.json`, `manifest.json`).

The one change: `ibex_tb_hold.v` = `opentsense/power/tb/ibex_tb.v` without `data_rdata <= 32'hx;` on write cycles (the port holds its last read value).

| Window | Verilator hold vs Icarus hold: total | tile rel. L2 | inst. p99 | X component of G72 (Icarus hold vs G72): total | tile L2 | G81a gap closed (total / tile L2) |
|---|---|---|---|---|---|---|
| k0 | −0.03% | 0.51% | 1.1% | −0.17% | 0.44% | 82% / 27% |
| k1 | −0.03% | 0.48% | 0.55% | 0 | 0 | (no gap) |
| k2 | −0.03% | 0.49% | 0.69% | −0.51% | 1.51% | 85% / 57% |
| k3 | −0.03% | 0.51% | 0.41% | −1.46% | 3.64% | 98% / 86% |
| k4 | −0.45% | 0.22% | 0.10% | 0 | 0 | (no gap) |

- (v) control: Icarus with the original testbench equals G72 to the printed digits in all five windows. (a) 100% annotation for both. (b) all within 1%. (c) checksums correct, k4 runs to its limit.
- **Meaning.** The 0 → x → 0 transitions Icarus records on `data_rdata` write cycles were a testbench artefact worth up to 1.5% of total power and 3.6% of the tile map on store-heavy windows. Without them, Verilator and Icarus agree to the remaining ~0.5% tile-level floor (zero-delay event ordering, as G49). The residual tile L2 (0.2–0.5%) is the same in every window, X or not.
- **Consequences.** Hold-testbench Icarus values supersede G72's as the ibex reference. Verilator windows on the hold testbench are used from G81b on.
- Icarus still records 80–114 k X value changes per window (the same with both testbenches on k1 and k4): never-reset state shown as X at the dump start. They do not affect power agreement here.
