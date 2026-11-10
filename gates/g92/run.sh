#!/bin/bash
# G92: leakage library, per-instance leakage and the gate-level loop. Usage: gates/g92/run.sh <run_id> [image]
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; IMG=${2:-opentsense:g75spice}
R=gates/g92/runs/$ID; mkdir -p "$R/power" "$R/lib"
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); B=$(cd ../../_build && pwd -W 2>/dev/null || pwd)
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
LIBP=/OpenROAD-flow-scripts/flow/platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$B:/b:ro" -w /work "$@"; }
t0=$(date +%s)
dk "$ORFS_IMAGE" cp $LIBP /work/$R/lib/sg13g2_stdcell_typ_1p20V_25C.lib
dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leaklib.py $R/lib/sg13g2_stdcell_typ_1p20V_25C.lib $R/lib ${JOBS:-12} 2>&1 | tee "$R/leaklib.log"
[ -f $R/lib/leak_states.json ] || { echo "leaklib did not finish; stopping"; exit 1; }
dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leak.py ihp $R/leak_g53.json 2>&1 | tee -a "$R/leaklib.log"
[ -f $R/leak_g53.json ] || { echo "leak.py did not finish; stopping"; exit 1; }
t1=$(date +%s)
sta() { dk -e RES=/b/g53/ihp-sg13g2-ibex/results/ihp-sg13g2/ibex/base -e LIB="$3" -e VCD="/b/g53/sim/w$1.vcd" -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" $OR -no_init -exit /work/gates/g92/power.tcl > "$R/power/k$1_$2.txt" 2>&1; echo "k$1 $2 rc=$?"; }
for k in 0 1 2 3; do
  sta $k ship $LIBP &
  for T in 25 50 75 100 125; do sta $k $T /work/$R/lib/sg13g2_stdcell_typ_1p20V_25C_${T}C.lib & done
  wait
done
t2=$(date +%s)
dk -e OPENTSENSE_IMAGE="$(docker image inspect "$IMG" --format '{{.Id}}')" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g92/evaluate.py "$R" /b/g53/ihp-sg13g2-ibex/inst_loc.csv gates/g75/runs/main/power 2>&1 | tee "$R/evaluate.log"
echo "{\"spice_s\": $((t1-t0)), \"sta_s\": $((t2-t1)), \"total_s\": $(( $(date +%s)-t0 ))}" | tee "$R/timing.json"
