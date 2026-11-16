#!/bin/bash
# G96: zero-delay against delay-aware activity on one G99 layout (registration.md).
# Usage (host): bash gates/g96/run.sh <ibex|tpu> <ps>
#   work (SDF, delay netlist, VCDs) in _build/g96/<design>-<ps>; reports and result in gates/g96/runs/<design>-<ps>
set -euo pipefail
cd "$(dirname "$0")/../.."
D=$1; P=$2; IMG=opentsense:g71dev
case $D in ibex) VTS=RVT ;; tpu) VTS="RVT LVT SLVT" ;; *) echo "design: ibex or tpu"; exit 2 ;; esac
set -a; . docker/versions.env; set +a
L=../../_build/g99/asap7-$D-$P; [ -f "$L/results/asap7/$D/base/6_final.odb" ] || { echo "no layout $L"; exit 2; }
W=../../_build/g96/$D-$P; R=gates/g96/runs/$D-$P; mkdir -p "$W" "$R/power"
REPO=$(pwd -W 2>/dev/null || pwd); LH=$(cd "$L" && pwd -W 2>/dev/null || pwd); WH=$(cd "$W" && pwd -W 2>/dev/null || pwd)
B=/build/asap7-$D/results/asap7/$D/base
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$WH:/w" -v "$LH:/build/asap7-$D:ro" -w /work "$@"; }
sta() { dk -e RES=$B -e CORNER=TT -e VTS="$VTS" "$@"; }
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
t0=$(date +%s)
sta -e OUT=/w/design.sdf "$ORFS_IMAGE" $OR -no_init -exit /work/gates/g96/dry/write_sdf.tcl > "$R/sdf.log" 2>&1
dk "$ORFS_IMAGE" bash -c "mkdir -p /w/stdcell && cp /OpenROAD-flow-scripts/flow/platforms/asap7/verilog/stdcell/*.v /w/stdcell/"
dk "$IMG" python gates/g96/delay_netlist.py $B/6_final.v /w/design.sdf /w/delay.v 2>&1 | tee "$R/convert.log"
dk "$IMG" python gates/g96/sim.py /w $B "$D" /w/delay.v 2>&1 | tee "$R/sim.log"
cp "$W/sim.json" "$R/sim.json"
# OpenSTA reads pin activity from the cell scopes: point outputs at their delayed nets, merge multi-output copies
dk "$IMG" python gates/g96/delay_netlist.py view /w/delay.v /w/delay.vcd /w/delay_sta.vcd 2>&1 | tee "$R/view.log"
t1=$(date +%s)
pw() {  # name vcd [loc]
  sta -e VCD="$2" -e VCD_SCOPE=tb/dut ${3:+-e LOC=$3} "$ORFS_IMAGE" $OR -no_init -exit /work/opentsense/power/vcd_power.tcl \
    > "$R/power/$1.txt" 2>&1
}
pw zero /w/zero.vcd "/work/$R/power/loc.csv"
pw delay /w/delay_sta.vcd
pw delay_raw /w/delay.vcd       # the simulator's own VCD, reported only (Amendment 1)
t2=$(date +%s)
dk -e OPENTSENSE_IMAGE="$IMG_ID" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g96/evaluate.py "$R" /w "$D" 2>&1 | tee "$R/evaluate.log"
echo "{\"sim_s\": $((t1-t0)), \"power_s\": $((t2-t1)), \"total_s\": $(( $(date +%s)-t0 ))}" > "$R/timing.json"
