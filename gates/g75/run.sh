#!/bin/bash
# G75: re-measured shortcut errors. Usage: gates/g75/run.sh <run_id> [image]
# IHP first, then the PACT stack loop, then cva6 alone in a memory-capped container (host memory).
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; IMG=${2:-opentsense:g75spice}
R=gates/g75/runs/$ID; mkdir -p "$R/power"
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); E=$(cd ../../experiments && pwd -W 2>/dev/null || pwd); B=$(cd ../../_build && pwd -W 2>/dev/null || pwd)
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$B:/b:ro" -v "$E:/exp:ro" -w /work "$@"; }
t0=$(date +%s)
ihp() { dk -e RES=/b/g53/ihp-sg13g2-ibex/results/ihp-sg13g2/ibex/base -e VCD="$2" -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" $OR -no_init -exit /work/gates/g75/ihp_power.tcl > "$R/power/ihp_$1.txt" 2>&1; echo "ihp $1 rc=$?"; }
ihp def none
for k in 0 1 2 3 4; do ihp "k$k" "/b/g53/sim/w$k.vcd"; done
t1=$(date +%s)
dk -e OPENTSENSE_IMAGE="$IMG_ID" "$IMG" python gates/g75/stack.py gates/g74/out/inputs.npz "$R" 2>&1 | tee "$R/stack.log"
t2=$(date +%s)
cva() { dk --memory=10g --memory-swap=10g -e RES=/b/g52/asap7-cva6/results/asap7/cva6/base -e VCD="$2" -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" $OR -no_init -exit -threads 4 /work/gates/g75/cva6_power.tcl > "$R/power/cva6_$1.txt" 2>&1; rc=$?; echo "cva6 $1 rc=$? ($rc)"; [ $rc -eq 0 ] || mv "$R/power/cva6_$1.txt" "$R/power/failed_cva6_$1.txt"; }
cva def none
for k in 0 1 2 3 4; do cva "k$k" "/b/g52/sim/vcd_ic/w$k.vcd"; done
t3=$(date +%s)
LIBF=$R/sg13g2_stdcell_typ_1p20V_25C.lib
dk "$ORFS_IMAGE" cp /OpenROAD-flow-scripts/flow/platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib "/work/$LIBF"
dk -e OPENTSENSE_IMAGE="$IMG_ID" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g75/evaluate.py "$R" /b/g52 /b/g53 gates/g72/runs/main /exp/code/sens/g53/g53_leak.json "$LIBF" 2>&1 | tee "$R/evaluate.log"
rm -f "$LIBF"
echo "{\"ihp_s\": $((t1-t0)), \"stack_s\": $((t2-t1)), \"cva6_s\": $((t3-t2)), \"total_s\": $(( $(date +%s)-t0 ))}" | tee "$R/timing.json"
