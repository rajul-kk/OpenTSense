# G97: static IR drop on the TT-closed Ibex layout · valid; the nominal-VDD power maps stand

Registration: `registration.md` (fixed 16 Nov before any IR number; Amendment 1 after the blind dry run on default
activity, before the main run; Amendment 2 after the main run, scoring fixes from code review, decision unchanged;
no bar changed). Run: `bash gates/g97/run.sh main` then `evaluate.py`. Record:
`record/`. OpenROAD PDNSim (pinned ORFS image) on G99's ASAP7 Ibex at 1,400 ps, TT, with G100's windows k0-k4.

| Window | Power | Worst VDD drop | Worst VSS rise | Worst tile squeeze | Mean squeeze | Spearman (squeeze, power) |
|---|---|---|---|---|---|---|
| k0 | 4.45 mW | 1.37 mV | 1.24 mV | 2.40 mV | 0.40 mV | 0.82 |
| k1 | 4.82 mW | 1.29 mV | 1.30 mV | 2.55 mV | 0.43 mV | 0.84 |
| k2 | 4.70 mW | 1.33 mV | 1.24 mV | 2.38 mV | 0.42 mV | 0.83 |
| k3 | 4.39 mW | 1.44 mV | 1.24 mV | 2.53 mV | 0.39 mV | 0.82 |
| k4 | 1.69 mW | 1.01 mV | 1.03 mV | 1.89 mV | 0.15 mV | 0.76 |

Validity: grids connected on VDD and VSS, no error files; OpenSTA totals equal G100's to 1e-6; PDNSim's total power
within 1% of them; every located instance has a voltage; the five windows' maps differ (the activity was used).

**Decision.** The worst squeeze in any tile holding at least 0.1% of the power is 2.55 mV, 0.36% of VDD, against
the registered 2.5% (17.5 mV). By the dynamic-power scaling (2d/VDD) that is at most a 0.7% local power change, so
the maps computed at nominal VDD stand; the limit is stated with this figure.

## Notes

- Over the whole map, squeeze follows power (Spearman 0.76-0.84, tiles holding an instance). Among the tiles that
  carry power it is weaker (0.32-0.41 before Amendment 2): there, distance to the grid's straps matters as much as
  local power.
- The BUMPS source model wrote the same voltages as FULL in this image (Amendment 1), so there is no package-level
  bracket; a chip-level grid above this block would add its own drop.
- Limits: static only (no dynamic IR); grid resistance at the tech file's temperature; no feedback into power or
  timing; one small block (76.7 um square).

## TPU part (16 Nov 2026, Amendment 3) · valid; the nominal-VDD power maps stand

G99's ASAP7 TPU at 800 ps with G100's windows W1-W3 (RVT, LVT, SLVT at TT), `bash gates/g97/run.sh tpu`, record
`record/tpu-800/`. All validity bars hold in every window; the three windows' voltage maps differ.

| Window | Power | Worst VDD drop | Worst VSS rise | Worst tile squeeze | Mean squeeze | Spearman (squeeze, power) |
|---|---|---|---|---|---|---|
| W1 | 19.66 mW | 2.69 mV | 2.61 mV | 5.02 mV | 0.92 mV | 0.67 |
| W2 | 17.56 mW | 2.67 mV | 2.56 mV | 4.98 mV | 0.81 mV | 0.69 |
| W3 (idle) | 12.90 mW | 2.54 mV | 2.45 mV | 4.70 mV | 0.58 mV | 0.69 |

**Decision.** Worst tile squeeze 5.02 mV, 0.72% of VDD, against the registered 2.5% (17.5 mV): at most about a 1.4%
local power change by the 2d/VDD scaling, so the TPU's nominal-VDD maps stand. About twice Ibex's squeeze at about
four times its power. BUMPS again equals FULL. The idle window still draws 66% of W1's power (the clock tree runs) and keeps 94% of its squeeze.
