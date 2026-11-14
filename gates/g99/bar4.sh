#!/bin/bash
# G99 bar 4: G72's gate-level simulation (gates/g72/sim.py) on one G99 netlist, at its own SDC clock; checksums only.
# Usage (host): bash gates/g99/bar4.sh <ibex|tpu> <ps>   -> gates/g99/record/<design>-<ps>/sim.json
# VCDs and models stay in _build/g99/bar4-<design>-<ps>; the layout is mounted where sim.py expects asap7-<design>.
set -euo pipefail
cd "$(dirname "$0")/../.."
D=$1; P=$2
case $D in ibex) IW=0,1,2,3; TW="" ;; tpu) IW=""; TW=W1,W2,W3 ;; *) echo "design: ibex or tpu"; exit 2 ;; esac
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd)
L=../../_build/g99/asap7-$D-$P; [ -f "$L/results/asap7/$D/base/6_final.v" ] || { echo "no layout $L"; exit 2; }
R=../../_build/g99/bar4-$D-$P; mkdir -p "$R"
LH=$(cd "$L" && pwd -W 2>/dev/null || pwd); RH=$(cd "$R" && pwd -W 2>/dev/null || pwd)
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$RH:/run" -v "$LH:/build/asap7-$D:ro" -w /work "$@"; }
dk "$ORFS_IMAGE" bash -c "mkdir -p /run/stdcell && cp /OpenROAD-flow-scripts/flow/platforms/asap7/verilog/stdcell/*.v /run/stdcell/"
dk opentsense:g71dev python gates/g72/sim.py /run /build "$IW" "$TW" 2>&1 | tee "$R/sim.log"
mkdir -p gates/g99/record/$D-$P && cp "$R/sim.json" gates/g99/record/$D-$P/sim.json
