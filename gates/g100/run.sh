#!/bin/bash
# G100: G72's pipeline (Icarus windows -> OpenSTA power at TT -> 32x32 tiles) on one G99 layout, at its own clock.
# Usage (host, from anywhere): bash gates/g100/run.sh <ibex|tpu> <ps>   -> gates/g100/runs/<design>-<ps>/
set -euo pipefail
cd "$(dirname "$0")/../.."
D=$1; P=$2; IMG=opentsense:g71dev
case $D in
  ibex) IW=0,1,2,3,4; TW=""; VTS=RVT; WINS="k0 k1 k2 k3 k4" ;;
  tpu) IW=""; TW=W1,W2,W3; VTS="RVT LVT SLVT"; WINS="W1 W2 W3" ;;
  *) echo "design: ibex or tpu"; exit 2 ;;
esac
set -a; . docker/versions.env; set +a
L=../../_build/g99/asap7-$D-$P; [ -f "$L/results/asap7/$D/base/6_final.odb" ] || { echo "no layout $L"; exit 2; }
R=gates/g100/runs/$D-$P; mkdir -p "$R/power"
REPO=$(pwd -W 2>/dev/null || pwd); LH=$(cd "$L" && pwd -W 2>/dev/null || pwd)
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
# the layout is mounted where G72's scripts expect asap7-<design>
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$LH:/build/asap7-$D:ro" -w /work "$@"; }
t0=$(date +%s)
dk "$ORFS_IMAGE" bash -c "mkdir -p $R/stdcell && cp /OpenROAD-flow-scripts/flow/platforms/asap7/verilog/stdcell/*.v $R/stdcell/"
dk "$IMG" python gates/g72/sim.py "$R" /build "$IW" "$TW" 2>&1 | tee "$R/sim.log"
t1=$(date +%s)
pw() {  # window vcd [loc]
  dk -e RES=/build/asap7-$D/results/asap7/$D/base -e CORNER=TT -e VTS="$VTS" -e VCD="$2" -e VCD_SCOPE=tb/dut ${3:+-e LOC=$3} \
    "$ORFS_IMAGE" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit /work/opentsense/power/vcd_power.tcl \
    > "$R/power/${D}_$1.txt" 2>&1
}
pw def none "/work/$R/power/${D}_loc.csv"
for w in $WINS; do pw "$w" "/work/$R/sim/$D/$w.vcd"; done
t2=$(date +%s)
dk -e OPENTSENSE_IMAGE="$IMG_ID" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g100/evaluate.py "$R" "$D" /build/asap7-$D 2>&1 | tee "$R/evaluate.log"
echo "{\"sim_s\": $((t1-t0)), \"power_s\": $((t2-t1)), \"total_s\": $(( $(date +%s)-t0 ))}" > "$R/timing.json"
