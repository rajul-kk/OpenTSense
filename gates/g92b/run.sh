#!/bin/bash
# G92b: leakage library, per-instance leakage and the gate-level loop, for IHP SG13G2 and ASAP7 ibex.
# Usage: gates/g92b/run.sh <run_id> [ihp|asap7|both] [image]
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; KITS=${2:-both}; IMG=${3:-opentsense:g75spice}
[ "$KITS" = both ] && KITS="ihp asap7"
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); B=$(cd ../../_build && pwd -W 2>/dev/null || pwd)
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
PF=/OpenROAD-flow-scripts/flow/platforms
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$B:/b:ro" -w /work "$@"; }
for KIT in $KITS; do
  R=gates/g92b/runs/$ID/$KIT; mkdir -p "$R/power" "$R/lib/ship"
  if [ $KIT = ihp ]; then
    SHIP="$PF/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
    RES=/b/g53/ihp-sg13g2-ibex/results/ihp-sg13g2/ibex/base; VCDD=/b/g53/sim; LOC=/b/g53/ihp-sg13g2-ibex/inst_loc.csv
    REF="gates/g75/runs/main/power/ihp_{w}.txt"; STACK=configs/stacks/g92_ihp.yaml; PAR=6
  else
    L=$PF/asap7/lib/NLDM
    SHIP="$L/asap7sc7p5t_AO_RVT_TT_nldm_211120.lib.gz $L/asap7sc7p5t_INVBUF_RVT_TT_nldm_220122.lib.gz $L/asap7sc7p5t_OA_RVT_TT_nldm_211120.lib.gz $L/asap7sc7p5t_SIMPLE_RVT_TT_nldm_211120.lib.gz $L/asap7sc7p5t_SEQ_RVT_TT_nldm_220123.lib"
    RES=/b/asap7/asap7-ibex/results/asap7/ibex/base; VCDD=/b/asap7/sim; LOC=/b/asap7/asap7-ibex/inst_loc.csv
    REF="/b/asap7/pw_{w}_TT.txt"; STACK=configs/stacks/g92b_asap7.yaml; PAR=2          # G34 ran ASAP7 OpenSTA 2 at a time to fit memory
  fi
  t0=$(date +%s)
  dk "$ORFS_IMAGE" cp $SHIP /work/$R/lib/ship/
  LOCAL=$(for f in $SHIP; do echo -n "$R/lib/ship/$(basename $f) "; done)
  dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leaklib.py $KIT $R/lib ${JOBS:-12} $LOCAL 2>&1 | tee "$R/leaklib.log"
  [ -f $R/lib/leak_states.json ] || { echo "leaklib did not finish; stopping"; exit 1; }
  dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leak.py $KIT $R/leak_ref.json 2>&1 | tee -a "$R/leaklib.log"
  [ -f $R/leak_ref.json ] || { echo "leak.py did not finish; stopping"; exit 1; }
  t1=$(date +%s)
  libs_at() { for f in $LOCAL; do s=$(basename $f); s=${s%.gz}; s=${s%.lib}; echo -n "/work/$R/lib/${s}_$1C.lib "; done; }
  sta() { dk -e RES=$RES -e LIBS="$3" -e VCD="$VCDD/w$1.vcd" -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" $OR -no_init -exit /work/gates/g92b/power.tcl > "$R/power/k$1_$2.txt" 2>&1; echo "$KIT k$1 $2 rc=$?"; }
  for k in 0 1 2 3; do
    n=0
    for T in ship 25 50 75 100 125; do
      if [ $T = ship ]; then LB="$SHIP"; else LB=$(libs_at $T); fi
      sta $k $T "$LB" & n=$((n+1))
      [ $((n % PAR)) -eq 0 ] && wait
    done
    wait
  done
  t2=$(date +%s)
  dk -e OPENTSENSE_IMAGE="$(docker image inspect "$IMG" --format '{{.Id}}')" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g92b/evaluate.py $KIT "$R" $LOC "$REF" $STACK 2>&1 | tee "$R/evaluate.log"
  echo "{\"spice_s\": $((t1-t0)), \"sta_s\": $((t2-t1)), \"total_s\": $(( $(date +%s)-t0 ))}" | tee "$R/timing.json"
done
