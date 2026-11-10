#!/bin/bash
# G92c: settled leakage library, per-instance leakage and the gate-level loop, for IHP SG13G2, ASAP7 RVT and ASAP7 LVT ibex.
# Usage: gates/g92c/run.sh <run_id> [ihp|asap7|asap7_lvt|all] [image]
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; KITS=${2:-all}; IMG=${3:-opentsense:g75spice}
[ "$KITS" = all ] && KITS="ihp asap7 asap7_lvt"
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); B=$(cd ../../_build && pwd -W 2>/dev/null || pwd)
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
PF=/OpenROAD-flow-scripts/flow/platforms
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$B:/b:ro" -w /work "$@"; }
for KIT in $KITS; do
  R=gates/g92c/runs/$ID/$KIT; mkdir -p "$R/power" "$R/lib/ship"
  PREV=none; BIND=0
  if [ $KIT = ihp ]; then
    SHIP="$PF/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
    RES=/b/g53/ihp-sg13g2-ibex/results/ihp-sg13g2/ibex/base; VCDD=/b/g53/sim; LOC=/b/g53/ihp-sg13g2-ibex/inst_loc.csv
    REF="gates/g75/runs/main/power/ihp_{w}.txt"; STACK=configs/stacks/g92_ihp.yaml; PAR=6; PREV=gates/g92b/runs/main/ihp/lib/leak_states.json
  else
    V=RVT; [ $KIT = asap7_lvt ] && { V=LVT; BIND=1; }
    L=$PF/asap7/lib/NLDM
    SHIP="$L/asap7sc7p5t_AO_${V}_TT_nldm_211120.lib.gz $L/asap7sc7p5t_INVBUF_${V}_TT_nldm_220122.lib.gz $L/asap7sc7p5t_OA_${V}_TT_nldm_211120.lib.gz $L/asap7sc7p5t_SIMPLE_${V}_TT_nldm_211120.lib.gz $L/asap7sc7p5t_SEQ_${V}_TT_nldm_220123.lib"
    RES=/b/asap7/asap7-ibex/results/asap7/ibex/base; VCDD=/b/asap7/sim; LOC=/b/asap7/asap7-ibex/inst_loc.csv
    STACK=configs/stacks/g92b_asap7.yaml; PAR=2          # G34 ran ASAP7 OpenSTA 2 at a time to fit memory
    if [ $V = RVT ]; then REF="/b/asap7/pw_{w}_TT.txt"; PREV=gates/g92b/runs/main/asap7/lib/leak_states.json; else REF=none; fi
  fi
  t0=$(date +%s)
  dk "$ORFS_IMAGE" cp $SHIP /work/$R/lib/ship/
  LOCAL=$(for f in $SHIP; do echo -n "$R/lib/ship/$(basename $f) "; done)
  dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leaklib.py $KIT $R/lib ${JOBS:-12} $LOCAL 2>&1 | tee "$R/leaklib.log"
  [ -f $R/lib/leak_states.json ] || { echo "leaklib did not finish; stopping"; exit 1; }
  LK=asap7; [ $KIT = ihp ] && LK=ihp
  dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leak.py $LK $R/leak_ref.json 2>&1 | tee -a "$R/leaklib.log"
  [ -f $R/leak_ref.json ] || { echo "leak.py did not finish; stopping"; exit 1; }
  t1=$(date +%s)
  # LVT: the RVT-built design binds to the LVT cells by renaming the cell suffix _L -> _R (G92c registration)
  if [ $BIND = 1 ]; then
    mkdir -p $R/lib/bind
    for f in $R/lib/ship/* $R/lib/*_*C.lib; do o=$R/lib/bind/$(basename ${f%.gz}); case $f in *.gz) zcat $f;; *) cat $f;; esac | sed 's/_ASAP7_75t_L\b/_ASAP7_75t_R/g' > $o; done
    LD=$R/lib/bind; SHIPB=$(for f in $SHIP; do s=$(basename $f); echo -n "/work/$LD/${s%.gz} "; done)
  else
    LD=$R/lib; SHIPB="$SHIP"
  fi
  libs_at() { for f in $LOCAL; do s=$(basename $f); s=${s%.gz}; s=${s%.lib}; echo -n "/work/$LD/${s}_$1C.lib "; done; }
  sta() { dk -e RES=$RES -e LIBS="$3" -e VCD="$VCDD/w$1.vcd" -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" $OR -no_init -exit /work/gates/g92c/power.tcl > "$R/power/k$1_$2.txt" 2>&1; echo "$KIT k$1 $2 rc=$?"; }
  for k in 0 1 2 3; do
    n=0
    for T in ship 25 50 75 100 125; do
      if [ $T = ship ]; then LB="$SHIPB"; else LB=$(libs_at $T); fi
      sta $k $T "$LB" & n=$((n+1))
      [ $((n % PAR)) -eq 0 ] && wait
    done
    wait
  done
  t2=$(date +%s)
  dk -e OPENTSENSE_IMAGE="$(docker image inspect "$IMG" --format '{{.Id}}')" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g92c/evaluate.py $KIT "$R" $LOC "$REF" $STACK $PREV 2>&1 | tee "$R/evaluate.log"
  echo "{\"spice_s\": $((t1-t0)), \"sta_s\": $((t2-t1)), \"total_s\": $(( $(date +%s)-t0 ))}" | tee "$R/timing.json"
done
