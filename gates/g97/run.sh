#!/bin/bash
# G97 (registration.md). Usage (host, holding a heavy slot of 2 GB): bash gates/g97/run.sh <dry|main>
#   dry: default activity, with the tool's help, into gates/g97/runs/dry; main: windows k0-k4 into gates/g97/runs/main
set -euo pipefail
cd "$(dirname "$0")/../.."
MODE=$1
set -a; . docker/versions.env; set +a
L=../../_build/g99/asap7-ibex-1400; [ -f "$L/results/asap7/ibex/base/6_final.odb" ] || { echo "no layout $L"; exit 2; }
case $MODE in
  dry) O=gates/g97/runs/dry; WINS="def"; HELP=1 ;;
  main) O=gates/g97/runs/main; WINS="k0 k1 k2 k3 k4"; HELP=0 ;;
  *) echo "mode: dry or main"; exit 2 ;;
esac
REPO=$(pwd -W 2>/dev/null || pwd); LH=$(cd "$L" && pwd -W 2>/dev/null || pwd)
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
t0=$(date +%s)
for w in $WINS; do
  rm -rf "$O/$w"; mkdir -p "$O/$w"
  if [ "$w" = def ]; then V=none; else V=/work/gates/g100/runs/ibex-1400/sim/ibex/$w.vcd; fi
  MSYS_NO_PATHCONV=1 docker run --rm --memory 2g --memory-swap 2g -v "$REPO:/work" -v "$LH:/build:ro" -w /work \
    -e RES=/build/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT -e VCD=$V -e VCD_SCOPE=tb/dut \
    -e OUT=/work/$O/$w -e SOURCES="FULL BUMPS" -e HELP=$HELP \
    "$ORFS_IMAGE" $OR -no_init -exit /work/gates/g97/ir.tcl > "$O/$w/ir.log" 2>&1 || { echo "$w failed, see $O/$w/ir.log"; exit 1; }
  echo "$w done $(( $(date +%s)-t0 )) s"
done
[ "$MODE" = main ] && ORFS_IMAGE="$ORFS_IMAGE" python gates/g97/evaluate.py "$O"
