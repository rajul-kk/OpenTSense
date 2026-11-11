# G81a: Verilator power windows against Icarus's (routed ASAP7 ibex) · FAIL on (b)

Registration: `registration.md` (with Amendment 1, fixed in the dry run on k0). Run: `run.sh main`, 8 Nov 2026, 506 s (build 259 s, simulation and power 236 s). Output: `runs/main/` (`result.json`, `manifest.json`, `power/`, `sim/`).

## Verdict

| Bar | Result |
|---|---|
| (a) annotation ≥ 99%, k0–k4 | **PASS**: 70,206 of 70,206 pins annotated in every window |
| (b) total within 1% and tile map within 1% rel. L2 of G72, k0–k4 | **FAIL**: k2 tile L2 1.69%; k3 total −1.50% and tile L2 3.71% |
| (c) checksums k0–k3, k4 to its cycle limit | **PASS** |

| Window | Verilator (mW) | G72 Icarus (mW) | Total | Tile rel. L2 | Per-instance rel. diff, median / p99 | Function-run speed-up |
|---|---|---|---|---|---|---|
| k0 (dry run) | 7.0738 | 7.0887 | −0.21% | 0.69% | 0.16% / 17% | 36× |
| k1 | 7.7433 | 7.7458 | −0.03% | 0.48% | 0.13% / 0.55% | 39× |
| k2 | 7.5140 | 7.5594 | −0.60% | **1.69%** | 0.13% / 43% | 36× |
| k3 | 6.8922 | 6.9968 | **−1.50%** | **3.71%** | 0.19% / 100% | 39× |
| k4 (sleep) | 2.5666 | 2.5782 | −0.45% | 0.22% | 0.07% / 0.10% | 349× |

## What it means

- Verilator traces are now fully readable by OpenSTA (G52's 19% annotation is fixed: `--trace-underscore`, the window end and the backslash name map) and run 36–39× faster than Icarus on active kernels.
- The power disagreement is not spread evenly. The median instance agrees to about 0.15%, but in k2 and k3 a set of instances differs by up to 100% (Verilator lower everywhere), and that set is concentrated enough in space to move the tile map by 1.7–3.7%.
- **Not yet diagnosed.** The leading candidate is the X-transition component found in the dry run: the testbench drives `data_rdata` to `x` on write cycles, Icarus propagates 0 → x → 0 transitions and Verilator (two-state) cannot. That would make Verilator lower, and worse on store-heavy windows. This is a hypothesis, not a measured cause.
- Per the registration, G81b falls back to Icarus windows placed by a Verilator activity timeline, with the same bars, unless a follow-up gate (registered first) shows the gap is the testbench's X injection and that Icarus without it agrees with Verilator.
