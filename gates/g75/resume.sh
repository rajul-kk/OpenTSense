#!/bin/bash
# G75 Amendment 2: formal shortcut (2), then cva6 one window at a time under a host-memory watchdog, then scoring.
# Usage: gates/g75/resume.sh <run_id> [spice|cva6|score]...   The IHP and stack parts of the run stand.
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; shift; R=gates/g75/runs/$ID; IMG=opentsense:g75spice; MIN_KB=${MIN_KB:-420000}
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); E=$(cd ../../experiments && pwd -W 2>/dev/null || pwd); B=$(cd ../../_build && pwd -W 2>/dev/null || pwd)
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$B:/b:ro" -v "$E:/exp:ro" -w /work "$@"; }
free_kb() { powershell -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory" | tr -d '\r'; }
cva() {   # one window; returns 0 on success
  local n=g75cva_$1 out=$R/power/cva6_$1.txt peak=99999999
  dk --name "$n" --memory=10g --memory-swap=10g -e RES=/b/g52/asap7-cva6/results/asap7/cva6/base -e VCD="$2" -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" $OR -no_init -exit -threads 4 /work/gates/g75/cva6_power.tcl > "$out" 2>&1 &
  local pid=$! stopped=0
  while kill -0 $pid 2>/dev/null; do
    f=$(free_kb); [ "${f:-0}" -lt "$peak" ] && peak=$f
    if [ "${f:-0}" -lt "$MIN_KB" ]; then echo "watchdog: $1 stopped, free ${f} kB"; docker stop -t 2 "$n" >/dev/null 2>&1; stopped=1; break; fi
    sleep 15
  done
  wait $pid; rc=$?
  echo "cva6 $1 rc=$rc stopped=$stopped lowest_free_kB=$peak"
  if [ $rc -ne 0 ] || [ $stopped -eq 1 ]; then mv "$out" "$R/power/failed_cva6_$1.txt"; return 1; fi
  rm -f "$R/power/failed_cva6_$1.txt"
}
for step in "$@"; do case $step in
  spice) dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leak.py ihp "/work/$R/spice_ihp.json" ;;
  cva6) [ -f "$R/power/cva6_def.txt" ] || cva def none || exit 3
        for k in 0 1 2 3 4; do [ -f "$R/power/cva6_k$k.txt" ] || cva "k$k" "/b/g52/sim/vcd_ic/w$k.vcd" || exit 3; done ;;
  score) LIBF=$R/sg13g2_stdcell_typ_1p20V_25C.lib
        dk "$ORFS_IMAGE" cp /OpenROAD-flow-scripts/flow/platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib "/work/$LIBF"
        dk -e OPENTSENSE_IMAGE="$IMG_ID" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g75/evaluate.py "$R" /b/g52 /b/g53 gates/g72/runs/main /exp/code/sens/g53/g53_leak.json "$LIBF" 2>&1 | tee "$R/evaluate.log"
        rm -f "$LIBF" ;;
esac; done
