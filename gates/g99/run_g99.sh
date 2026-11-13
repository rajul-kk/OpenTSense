#!/bin/bash
# G99: ORFS with CORNER=TT and a set clock. Inside openroad/orfs (id 55266bc72fd6), /work = _build/g99.
# usage: run_g99.sh <ibex|tpu> <clk_period_ps>
D=$1; P=$2; W=/work/asap7-$D-$P; mkdir -p $W
source /OpenROAD-flow-scripts/env.sh >/dev/null 2>&1; cd /OpenROAD-flow-scripts/flow
sed "s/^set clk_period .*/set clk_period $P/" designs/asap7/$D/constraint.sdc > $W/constraint.sdc
grep -q "^set clk_period $P\$" $W/constraint.sdc || { echo "clock not set"; exit 2; }
start=$(date +%s)
make WORK_HOME=$W DESIGN_CONFIG=./designs/asap7/$D/config.mk CORNER=TT SDC_FILE=$W/constraint.sdc > $W/flow.log 2>&1; rc=$?
if [ $rc -eq 0 ]; then
  sed "s#/work/inst_loc.csv#$W/inst_loc.csv#" /work/extract.tcl > $W/extract.tcl
  make WORK_HOME=$W DESIGN_CONFIG=./designs/asap7/$D/config.mk CORNER=TT SDC_FILE=$W/constraint.sdc RUN_SCRIPT=$W/extract.tcl run > $W/extract.log 2>&1; rc2=$?
else rc2=-1; fi
echo "$D $P flow_rc=$rc extract_rc=$rc2 total_s=$(( $(date +%s)-start ))" >> /work/summary.txt
