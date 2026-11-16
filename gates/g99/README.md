# G99: ASAP7 layouts closed at TT · PASS for Ibex (1,400 ps) and the TPU (800 ps)

Registration: `registration.md` (bars fixed 13 Nov before any run; three corrections, the last one written after the
TPU run finished and labelled as such). The old layouts missed their own SDC clocks at TT, the corner every power map
uses (Ibex -416 ps at 900 ps, TPU -523 ps at 200 ps). G99 re-ran ORFS at `CORNER=TC` (ASAP7's TT libraries) with
clocks the designs meet. Run: `launch.sh <design> <ps>`, then `bar4.sh <design> <ps>`. Record: `record/<design>-<ps>/`.

| Bar | Ibex 1,400 ps | TPU 800 ps |
|---|---|---|
| 1 Setup at TT (reg-to-reg, I/O; propagated clock, routed SPEF) | met, worst reg-to-reg +21.4 ps; WNS/TNS 0 | met, worst reg-to-reg +4.9 ps; WNS/TNS 0 |
| 2 Hold at TT | met, worst +52.4 ps | met, worst +31.3 ps |
| 3 Routing DRC; LEC where ORFS runs it | 0 violations; LEC: circuits identical | 0 violations; LEC not run (config `LEC_CHECK = 0`) |
| 4 Window checksums on the new netlist (G72 testbench, own SDC clock) | k0-k3 all match | W1, W2 616/616 rows; W3 0 rows, as expected |

## Notes

- TPU resources: run under a 4.5 GB cap with 4 routing threads after two low-RAM stops in detailed routing (third
  correction). Detailed routing is expected not to depend on thread count; not verified.
- The TPU's setup margin is thin (+4.9 ps of 800 ps), so a slower corner would likely miss it; G99 claims TT only.
- IHP Ibex was checked separately: it misses 8.0 ns by 0.26 ns at typ (3%); stated as a limit, not re-run.

## What uses it

G100 (power maps on these layouts at their clocks), G96 (glitch power), G97 (static IR drop).
