#!/bin/bash
# G97 (registration.md). Usage (host, holding a heavy slot of 2 GB): bash gates/g97/run.sh <dry|main|tpu>
#   dry: default activity, with the tool's help, into gates/g97/runs/dry; main: Ibex windows k0-k4 into
#   gates/g97/runs/main; tpu: the TPU's windows W1-W3 into gates/g97/runs/tpu (Amendment 3)
set -euo pipefail
cd "$(dirname "$0")/../.."
MODE=${1:-}
set -a; . docker/versions.env; set +a
D=ibex; TAG=ibex-1400; VTS=RVT
case $MODE in
  dry) O=gates/g97/runs/dry; WINS="def"; HELP=1 ;;
  main) O=gates/g97/runs/main; WINS="k0 k1 k2 k3 k4"; HELP=0 ;;
  tpu) O=gates/g97/runs/tpu; WINS="W1 W2 W3"; HELP=0; D=tpu; TAG=tpu-800; VTS="RVT LVT SLVT" ;;
  *) echo "mode: dry, main or tpu"; exit 2 ;;
esac
L=../../_build/g99/asap7-$TAG; [ -f "$L/results/asap7/$D/base/6_final.odb" ] || { echo "no layout $L"; exit 2; }
REPO=$(pwd -W 2>/dev/null || pwd); LH=$(cd "$L" && pwd -W 2>/dev/null || pwd)
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
for w in $WINS; do                                   # every input first: nothing is deleted for a run that cannot run
  [ "$w" = def ] || [ -f "gates/g100/runs/$TAG/sim/$D/$w.vcd" ] || { echo "no VCD for $w"; exit 2; }
done
t0=$(date +%s)
for w in $WINS; do
  rm -rf "$O/$w"; mkdir -p "$O/$w"
  if [ "$w" = def ]; then V=none; else V=/work/gates/g100/runs/$TAG/sim/$D/$w.vcd; fi
  MSYS_NO_PATHCONV=1 docker run --rm --memory 2g --memory-swap 2g -v "$REPO:/work" -v "$LH:/build:ro" -w /work \
    -e RES=/build/results/asap7/$D/base -e CORNER=TT -e VTS="$VTS" -e VCD=$V -e VCD_SCOPE=tb/dut \
    -e OUT=/work/$O/$w -e SOURCES="FULL BUMPS" -e HELP=$HELP \
    "$ORFS_IMAGE" $OR -no_init -exit /work/gates/g97/ir.tcl > "$O/$w/ir.log" 2>&1 || { echo "$w failed, see $O/$w/ir.log"; exit 1; }
  echo "$w done $(( $(date +%s)-t0 )) s"
done
if [ "$MODE" != dry ]; then python gates/g97/evaluate.py "$O" "$D"; fi
