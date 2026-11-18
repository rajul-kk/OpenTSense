# G97 registration: static IR drop on the TT-closed Ibex layout

Registered 16 Nov 2026, before any IR-drop number exists (the student asked on 15 Nov to register G97 and run it
after G99). A measurement gate, like G96: validity bars, the measured quantities, and one decision threshold set
from what would change a power map, not from data.

## Question

OpenSTA computes every power map at nominal VDD. How large is the static IR drop on the layout the maps come from,
and is it large enough to change those maps?

## Cases (fixed)

- Layout: G99's ASAP7 Ibex at 1,400 ps (`_build/g99/asap7-ibex-1400`, checksums in `gates/g99/record/ibex-1400`).
- Activity: G100's windows k0, k1, k2, k3, k4 (`gates/g100/runs/ibex-1400/sim/ibex/k*.vcd`, scope `tb/dut`).
  The default-activity case (`def`) is the dry run's input, so it is not a gated case.
- Corner TT, RVT libraries, routed SPEF, as G100 (`gates/g96/dry/load_routed.tcl`). Supply voltage from the
  Liberty operating conditions (0.7 V); not overridden.
- Nets: VDD (drop below VDD) and VSS (rise above 0 V), each analysed.
- TPU: only after G99 and G100 close for the TPU, as an amendment naming its windows.

## Source model (fixed)

Primary: `FULL`, every node of the block's top power-grid layer is an ideal source. A block inside a chip is fed by
the chip's grid over it, whose drop is outside this layout; FULL measures the drop this layout's own grid adds,
which is the part the layout controls. Reported as a bracket, not gated: `BUMPS` with PDNSim's default bump pitch
(a package-level model the block does not define). If the pinned image lacks `-source_type`, its default is used
and named in an amendment before the main run.

## Validity bars (all must hold, per window)

V1. `check_power_grid` reports no error on VDD and on VSS.
V2. The session's `report_power` total equals G100's recorded total for the window to a relative 1e-6 (the VCD read
    is the one G100 used). PDNSim takes instance power from this same session.
V3. The analysis used the window's activity: the five windows' voltage maps are not all identical. If PDNSim reports
    its total current, current x VDD equals the V2 total within 1%.
V4. Every placed instance with power gets a voltage (the voltage file covers G100's located instances).

## Measured and reported (per window and net)

- Worst static drop (VDD) and rise (VSS), in mV and as a share of VDD; drop + rise as the worst supply squeeze.
- On G100's 32 x 32 tiles: mean and worst squeeze per tile; Spearman correlation of the squeeze map with G100's
  power map.
- The BUMPS bracket's worst squeeze.

## Decision threshold (fixed from power-map materiality)

Dynamic power scales with V squared, so a squeeze of d changes a cell's dynamic power by about 2d/VDD. G96 uses 5%
of dynamic power as the share that matters to a power map (its decision threshold). So IR matters to the maps if,
in any tile holding at least 0.1% of the window's power, 2 x squeeze / VDD >= 5%, that is, squeeze >= 2.5% of VDD
(17.5 mV at 0.7 V), under the primary model. Below that, the nominal-VDD maps stand and the limit is stated with
the measured figure; at or above it, voltage-scaled libraries are needed (open3d-thermal ambition 6).

## Dry run (blind, before the main run)

Default activity only (`VCD=none`, the `def` case) into `gates/g97/runs/dry/`: `help analyze_power_grid` and
`help check_power_grid` from the pinned ORFS image, the grid check, the voltage file's format and one analysis per
net and source type. The dry may only fix tool options and file formats; any such change is a dated amendment
before the main run. k0-k4 stay unseen until then.

## Limits (stated, not tested)

Static only (average power; dynamic IR is commercial-only). PDN resistances at the tech file's temperature, not
the thermal map's. No feedback of the drop into power or timing. One small block (76.7 um square, about 4.5 mW).

## Procedure

`bash gates/g97/run.sh <dry|main>`: ORFS image, one heavy slot (2 GB), then `evaluate.py` writes `result.json`
and a manifest with the sha256 of its inputs; recorded with `scripts/record_gate.py`.

## Amendment 1 (16 Nov 2026, after the blind dry run, before the main run; k0-k4 not yet run)

The dry run (`runs/dry/def`, default activity) settled tool facts only:
- The pinned image takes `-source_type FULL|BUMPS|STRAPS`, `-voltage_file` and `-error_file` as registered.
- BUMPS and FULL wrote byte-identical voltage files for both nets, so on this block the BUMPS bracket carries no
  information. It stays in the run and is reported with that note; nothing is gated on it.
- PDNSim prints its own "Total power"; V3's current check is that figure against the session's `report_power`
  total, within 1%. Both grid checks print "All shapes on net ... are connected"; V1 reads that line for VDD and VSS
  and requires no error file to have been written.
- The voltage file lists every instance terminal on the net (`Instance,Terminal,Layer,X,Y,Voltage`), fillers
  included; an instance's voltage is its lowest VDD terminal and highest VSS terminal. Tiles use G100's instance
  locations, as its power maps do.
Seen in the dry (default activity, not a gated case): worst VDD drop 5.6 mV, VSS rise 6.4 mV at 13.4 mW. The
threshold (17.5 mV) was fixed before this. No bar changed.

## Amendment 2 (16 Nov 2026, AFTER the main run; from /code-review of the evaluator; scoring only, PDNSim not re-run)

- V3 now requires all four (net, source) analyses, each read only up to the next marker (before, a missing block
  passed as empty); a new check requires PDNSim's supply voltage to be 0.7 V on VDD and 0 V on VSS in every block.
- Worst drop and rise are taken over G100's located instances, the same population as the squeeze and the
  decision (before: every terminal in the file, fillers included; the values did not change).
- Spearman is over every tile holding an instance, as registered "of the squeeze map with G100's power map"
  (before: only tiles with >= 0.1% of power, 0.32-0.41; now 0.76-0.84).
- result.json gains each worst figure as a share of VDD; maps.npz holds the per-tile mean and worst squeeze.
- Manifest: the ORFS image digest and the hashes of this file, G100's result, maps and locations. run.sh clears
  each window's folder, caps the container at 2 GB and calls the evaluator. Tile indexing is shared with G100
  (`maps.tile_index`; G100's maps reproduce exactly). Decision unchanged: worst tile squeeze 2.55 mV, 0.36% of VDD.

## Amendment 3 (16 Nov 2026, the TPU part, written before any TPU IR number exists)

As registered ("TPU: only after G99 and G100 close for the TPU, as an amendment naming its windows"). G99 passed for
the TPU at 800 ps and G100 recorded its windows on 16 Nov.
- Layout: G99's ASAP7 TPU at 800 ps (`_build/g99/asap7-tpu-800`, checksums in `gates/g99/record/tpu-800`).
- Activity: G100's TPU windows W1, W2, W3 (`gates/g100/runs/tpu-800/sim/tpu/W*.vcd`, scope `tb/dut`); W3 is the idle
  window. Libraries RVT, LVT and SLVT at TT, as G100 used for the TPU; VDD 0.7 V from Liberty as before.
- Bars V1 to V4, the supply check, the measured quantities, the 0.1%-of-power tile rule and the decision threshold
  (squeeze >= 2.5% of VDD, 17.5 mV) are unchanged; V2 compares with G100's TPU record, and "the windows' voltage
  maps are not all identical" applies to the three TPU windows.
- Run: `bash gates/g97/run.sh tpu` into `runs/tpu`, scored by `evaluate.py runs/tpu tpu`. The runner and evaluator
  gained this design as a parameter only; re-scoring the Ibex main run with the changed evaluator reproduces
  `record/result.json` exactly.
