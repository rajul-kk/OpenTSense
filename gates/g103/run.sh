#!/bin/bash
# G103: leakage libraries, OpenSTA power and the leakage margin at the SS and FF corners (registration.md).
# Usage (host, holding a heavy slot): gates/g103/run.sh <run_id> "<kit@corner ...>"   e.g. "asap7@ss asap7@ff"
# Per kit@corner, as G92e's run.sh (kit table copied from it; G92e's scripts are frozen): leaklib (opentsense:g103),
# leak.py at the corner, OpenSTA per window and library temperature (no shipped-library pass), then margin.py.
# A step is kept on rerun only if its output is newer than the step before it, so a rebuilt library redoes the rest.
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; KITS=$2; IMG=opentsense:g103
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); B=$(cd ../../_build && pwd -W 2>/dev/null || pwd)
OR=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad
PF=/OpenROAD-flow-scripts/flow/platforms
dk() { MSYS_NO_PATHCONV=1 docker run --rm --memory 3g -v "$REPO:/work" -v "$B:/b:ro" -w /work "$@"; }
for KC in $KITS; do
  case $KC in ihp@ss|ihp@ff|asap7@ss|asap7@ff|asap7_lvt@ss|asap7_lvt@ff) ;; *) echo "not a kit@corner: $KC"; exit 2;; esac
  KIT=${KC%@*}; C=${KC#*@}; R=gates/g103/runs/$ID/$KIT/$C; mkdir -p "$R/power" "$R/lib/ship"
  BIND=0
  if [ $KIT = ihp ]; then
    SHIP="$PF/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
    RES=/b/g53/ihp-sg13g2-ibex/results/ihp-sg13g2/ibex/base; VCDD=/b/g53/sim; LOC=/b/g53/ihp-sg13g2-ibex/inst_loc.csv
    STACK=configs/stacks/g92_ihp.yaml; PAR=2; LK=ihp
  else
    V=RVT; [ $KIT = asap7_lvt ] && { V=LVT; BIND=1; }
    L=$PF/asap7/lib/NLDM
    SHIP="$L/asap7sc7p5t_AO_${V}_TT_nldm_211120.lib.gz $L/asap7sc7p5t_INVBUF_${V}_TT_nldm_220122.lib.gz $L/asap7sc7p5t_OA_${V}_TT_nldm_211120.lib.gz $L/asap7sc7p5t_SIMPLE_${V}_TT_nldm_211120.lib.gz $L/asap7sc7p5t_SEQ_${V}_TT_nldm_220123.lib"
    RES=/b/asap7/asap7-ibex/results/asap7/ibex/base; VCDD=/b/asap7/sim; LOC=/b/asap7/asap7-ibex/inst_loc.csv
    STACK=configs/stacks/g92b_asap7.yaml; PAR=1; LK=asap7
  fi
  # The image and the corner model files this kit loads, hashed. Every kept output below hangs off this manifest, so
  # outputs from another image stop the run instead of being kept.
  if [ $KIT = ihp ]; then MF="/opt/spice/ihp/models/cornerMOSlv.lib /opt/spice/ihp/models/cornerDIO.lib"
  else MF=/opt/spice/asap7/asap7_${C}_osdi.lib; fi
  IMGID=$(docker image inspect $IMG --format '{{.Id}}')
  if [ -f $R/manifest.json ]; then
    grep -q "$IMGID" $R/manifest.json || { echo "$R was made with another image; use a new run id"; exit 1; }
  else
    dk -e PYTHONPATH=/work -e OPENTSENSE_IMAGE="$IMGID" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python -c \
      "import sys; from opentsense import manifest; manifest.write(sys.argv[1], {'gate': 'G103', 'kit': sys.argv[2], 'image': sys.argv[3], 'corner_models': {f: manifest.file_sha256(f) for f in sys.argv[4:]}})" \
      $R/manifest.json $KC "$IMGID" $MF || exit 1
  fi
  TC=gates/g103/runs/$ID/$KIT/tt_control          # control: margin.py on G92e's own TT run must give G95's margins;
  mkdir -p $TC                                     # redone every run (minutes), so it checks the code the corners use
  dk -e PYTHONPATH=/work "$IMG" python gates/g103/margin.py gates/g92e/runs/main/$KIT $LOC $STACK $TC/margin.json \
    2>&1 | tee "$TC/margin.log"
  t0=$(date +%s)
  LOCAL=$(for f in $SHIP; do echo -n "$R/lib/ship/$(basename $f) "; done)
  LS=$R/lib/leak_states.json
  if [ ! -f $LS ]; then
    dk "$ORFS_IMAGE" cp $SHIP /work/$R/lib/ship/
    dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leaklib.py $KC $R/lib ${JOBS:-4} $LOCAL 2>&1 | tee -a "$R/leaklib.log"
    [ -f $LS ] || { echo "leaklib did not finish; stopping"; exit 1; }
  fi
  if [ ! -f $R/leak_ref.json ]; then
    dk -e PYTHONPATH=/work "$IMG" python opentsense/power/leak.py $LK $R/leak_ref.json $C 2>&1 | tee -a "$R/leaklib.log"
    [ -f $R/leak_ref.json ] || { echo "leak.py did not finish; stopping"; exit 1; }
  fi
  t1=$(date +%s)
  if [ $BIND = 1 ]; then          # G92c: the RVT-built design binds to the LVT cells by renaming the suffix
    mkdir -p $R/lib/bind
    for f in $R/lib/*_*C.lib; do sed 's/_ASAP7_75t_L\b/_ASAP7_75t_R/g' $f > $R/lib/bind/$(basename $f); done
    LD=$R/lib/bind
  else
    LD=$R/lib
  fi
  libs_at() { for f in $LOCAL; do s=$(basename $f); s=${s%.gz}; s=${s%.lib}; echo -n "/work/$LD/${s}_$1C.lib "; done; }
  for k in 0 1 2 3; do
    n=0
    for T in 25 50 75 100 125; do
      o="$R/power/k${k}_$T.txt"
      if [ ! "$o" -nt $LS ]; then
        { dk -e RES=$RES -e LIBS="$(libs_at $T)" -e VCD="$VCDD/w$k.vcd" -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" $OR -no_init -exit \
            /work/gates/g92e/power.tcl > "$o.tmp" 2>&1 && grep -q "^Total" "$o.tmp" && mv "$o.tmp" "$o"; } &
        n=$((n+1)); [ $((n % PAR)) -eq 0 ] && wait
      fi
    done
    wait
  done
  t2=$(date +%s)
  NEWEST=$(ls -t $R/power/k*_*.txt $LS 2>/dev/null | head -1)
  if [ ! $R/margin.json -nt "$NEWEST" ]; then
    dk -e PYTHONPATH=/work "$IMG" python gates/g103/margin.py $R $LOC $STACK $R/margin.json 2>&1 | tee -a "$R/margin.log"
  fi
  echo "{\"spice_s\": $((t1-t0)), \"sta_s\": $((t2-t1)), \"total_s\": $(( $(date +%s)-t0 ))}" > "$R/timing_$(date +%s).json"
done
