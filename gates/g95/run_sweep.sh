#!/bin/bash
# G95 sweep on G92e's three kits. Usage: gates/g95/run_sweep.sh <out dir> <nominal|hot> [image]
# Writes <out dir>/<kit>/sweep_<kit>.json and <out dir>/sweep.log.
set -uo pipefail
cd "$(dirname "$0")/../.."
O=$1; CASE=$2; IMG=${3:-opentsense:g75spice}
B=$(cd ../../_build 2>/dev/null && (pwd -W 2>/dev/null || pwd)) || { echo "no _build folder at ../../_build" >&2; exit 2; }
REPO=$(pwd -W 2>/dev/null || pwd)
mkdir -p "$O"
MSYS_NO_PATHCONV=1 docker run --rm --memory=2g --memory-swap=2g -v "$REPO:/work" -v "$B:/b:ro" -w /work -e PYTHONPATH=/work "$IMG" bash -c "
python gates/g95/sweep.py ihp gates/g92e/runs/main/ihp /b/g53/ihp-sg13g2-ibex/inst_loc.csv configs/stacks/g92_ihp.yaml $O/ihp $CASE &&
python gates/g95/sweep.py asap7 gates/g92e/runs/main/asap7 /b/asap7/asap7-ibex/inst_loc.csv configs/stacks/g92b_asap7.yaml $O/asap7 $CASE &&
python gates/g95/sweep.py asap7_lvt gates/g92e/runs/main/asap7_lvt /b/asap7/asap7-ibex/inst_loc.csv configs/stacks/g92b_asap7.yaml $O/asap7_lvt $CASE" 2>&1 | tee "$O/sweep.log"
exit "${PIPESTATUS[0]}"
