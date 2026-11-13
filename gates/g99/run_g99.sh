#!/bin/bash
# G99: ORFS with CORNER=TC (the ASAP7 platform's name for its TT libraries) and a set clock.
# Inside openroad/orfs (id 55266bc72fd6), started by launch.sh; /work = _build/g99, holding this script and
# opentsense/power/extract.tcl as launch.sh copied them. Every exit writes one row to /work/summary.txt.
# usage: run_g99.sh <ibex|tpu> <clk_period_ps (integer)>
D=${1:-}; P=${2:-}; start=$(date +%s); rc=-1; rc2=-1; mid=$start
row() { echo "$D $P flow_rc=$rc extract_rc=$rc2 flow_s=$((mid-start)) total_s=$(( $(date +%s)-start )) $1" >> /work/summary.txt; }
case $D in ibex|tpu) ;; *) row "bad-design"; exit 2 ;; esac
[[ $P =~ ^[1-9][0-9]*$ ]] || { row "bad-period"; exit 2; }
W=/work/asap7-$D-$P; mkdir -p $W
source /OpenROAD-flow-scripts/env.sh >/dev/null 2>&1; cd /OpenROAD-flow-scripts/flow
# written only when it differs, so a resumed run keeps its timestamp and make does not redo synthesis
sed "s/^set clk_period .*/set clk_period $P/" designs/asap7/$D/constraint.sdc > /tmp/g99.sdc
grep -q "^set clk_period $P\$" /tmp/g99.sdc || { row "clock-not-set"; exit 2; }
cmp -s /tmp/g99.sdc $W/constraint.sdc || cp /tmp/g99.sdc $W/constraint.sdc
ARGS="WORK_HOME=$W DESIGN_CONFIG=./designs/asap7/$D/config.mk CORNER=TC SDC_FILE=$W/constraint.sdc"
timeout 14400 make $ARGS >> $W/flow.log 2>&1; rc=$?; mid=$(date +%s)
if [ $rc -eq 0 ]; then OUT_DIR=$W make $ARGS RUN_SCRIPT=/work/extract.tcl run > $W/extract.log 2>&1; rc2=$?; fi
row ""
