#!/bin/bash
# Goal 14 (stretch, ungated): STA and PDNSim on G99's ASAP7 Ibex (1,400 ps, TT, RVT) at each case of cases.py, G100's
# window k3 (G97's worst VDD drop). Usage (host, repo root, holding a light slot of 2 GB): bash gates/stretch_tir/run.sh
# Needs gates/stretch_tir/runs/derate.json (derate_probe.py). Output: gates/stretch_tir/runs/<case>/ (sta_ir.log, v_*.csv)
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; . docker/versions.env; set +a
O=gates/stretch_tir/runs; W=k3
L=../../_build/g99/asap7-ibex-1400; [ -f "$L/results/asap7/ibex/base/6_final.odb" ] || { echo "no layout $L"; exit 2; }
[ -f "gates/g100/runs/ibex-1400/sim/ibex/$W.vcd" ] || { echo "no VCD $W"; exit 2; }
REPO=$(pwd -W 2>/dev/null || pwd); LH=$(cd "$L" && pwd -W 2>/dev/null || pwd)
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
python gates/stretch_tir/cases.py "$O/derate.json" > "$O/cases.txt"
while read -r name T cf wf; do
  rm -rf "${O:?}/$name"; mkdir -p "$O/$name"
  MSYS_NO_PATHCONV=1 docker run --rm --memory 2g --memory-swap 2g -v "$REPO:/work" -v "$LH:/build:ro" -w /work \
    -e RES=/build/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT -e CELL_F="$cf" -e WIRE_F="$wf" \
    -e VCD=/work/gates/g100/runs/ibex-1400/sim/ibex/$W.vcd -e VCD_SCOPE=tb/dut -e OUT=/work/$O/$name \
    "$ORFS_IMAGE" $OR -no_init -exit /work/gates/stretch_tir/sta_ir.tcl > "$O/$name/sta_ir.log" 2>&1 \
    || { echo "$name failed, see $O/$name/sta_ir.log"; exit 1; }
  echo "$name T=$T cell=$cf wire=$wf done"
done < "$O/cases.txt"
python gates/stretch_tir/evaluate.py "$O"
