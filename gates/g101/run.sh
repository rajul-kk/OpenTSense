#!/bin/bash
# G101 on G95's three kits at the hot ambient. Usage: gates/g101/run.sh <out dir> [image]
set -uo pipefail
cd "$(dirname "$0")/../.."
O=$1; IMG=${2:-opentsense:g75spice}
B=$(cd ../../_build 2>/dev/null && (pwd -W 2>/dev/null || pwd)) || { echo "no _build folder at ../../_build" >&2; exit 2; }
REPO=$(pwd -W 2>/dev/null || pwd)
mkdir -p "$O"
MSYS_NO_PATHCONV=1 docker run --rm --memory=2g --memory-swap=2g -v "$REPO:/work" -v "$B:/b:ro" -w /work -e PYTHONPATH=/work "$IMG" bash -c "
python gates/g101/run.py ihp gates/g92e/runs/main/ihp /b/g53/ihp-sg13g2-ibex/inst_loc.csv configs/stacks/g92_ihp.yaml $O/ihp &&
python gates/g101/run.py asap7 gates/g92e/runs/main/asap7 /b/asap7/asap7-ibex/inst_loc.csv configs/stacks/g92b_asap7.yaml $O/asap7 &&
python gates/g101/run.py asap7_lvt gates/g92e/runs/main/asap7_lvt /b/asap7/asap7-ibex/inst_loc.csv configs/stacks/g92b_asap7.yaml $O/asap7_lvt &&
python gates/g101/evaluate.py $O" 2>&1 | tee "$O/run.log"
exit "${PIPESTATUS[0]}"
