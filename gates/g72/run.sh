#!/bin/bash
# G72: routed ASAP7 ibex and TPU -> Icarus gate-level VCD windows -> OpenSTA per-instance power -> 32x32 tile maps.
# Usage: gates/g72/run.sh <run_id> [image] [build dir] [ibex windows] [tpu windows]
#   build dir: the exploratory ORFS results (default ../../_build/asap7); rerouting is not part of the gate.
#   windows default to all (ibex 0,1,2,3,4; tpu W1,W2,W3); a shorter list is for plumbing checks only.
set -euo pipefail
cd "$(dirname "$0")/../.."
ID=$1; IMG=${2:-opentsense:g71dev}; B=${3:-../../_build/asap7}; IW=${4:-0,1,2,3,4}; TW=${5:-W1,W2,W3}
R=gates/g72/runs/$ID; mkdir -p "$R/power"
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); BH=$(cd "$B" && pwd -W 2>/dev/null || pwd)
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$BH:/build:ro" -w /work "$@"; }
t0=$(date +%s)
# 1. pristine ASAP7 cell models, from the pinned ORFS image
dk "$ORFS_IMAGE" bash -c "mkdir -p $R/stdcell && cp /OpenROAD-flow-scripts/flow/platforms/asap7/verilog/stdcell/*.v $R/stdcell/"
# 2. gate-level simulation, all windows in parallel (light on memory)
dk "$IMG" python gates/g72/sim.py "$R" /build "$IW" "$TW" 2>&1 | tee "$R/sim.log"
t1=$(date +%s)
# 3. OpenSTA power at TT, one job at a time (host memory); default activity first, which also writes the locations
pw() {  # design window vcd vts
  local res=/build/asap7-$1/results/asap7/$1/base
  dk -e RES=$res -e CORNER=TT -e VTS="$4" -e VCD="$3" -e VCD_SCOPE=tb/dut ${5:+-e LOC=$5} "$ORFS_IMAGE" \
    /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit /work/opentsense/power/vcd_power.tcl \
    > "$R/power/$1_$2.txt" 2>&1
}
pw ibex def none RVT "/work/$R/power/ibex_loc.csv"
for k in ${IW//,/ }; do pw ibex "k$k" "/work/$R/sim/ibex/k$k.vcd" RVT; done
pw tpu def none "RVT LVT SLVT" "/work/$R/power/tpu_loc.csv"
for k in ${TW//,/ }; do pw tpu "$k" "/work/$R/sim/tpu/$k.vcd" "RVT LVT SLVT"; done
t2=$(date +%s)
# 4. evaluation and manifest
dk -e OPENTSENSE_IMAGE="$IMG_ID" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g72/evaluate.py "$R" /build 2>&1 | tee "$R/evaluate.log"
t3=$(date +%s)
echo "{\"sim_s\": $((t1-t0)), \"power_s\": $((t2-t1)), \"eval_s\": $((t3-t2)), \"total_s\": $((t3-t0))}" > "$R/timing.json"
cat "$R/timing.json"
