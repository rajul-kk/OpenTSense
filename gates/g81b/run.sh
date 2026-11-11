#!/bin/bash
# G81b scored run (registration.md, Amendment 1).
#  1. software with the fixed scale factors (scale.txt) and idle NPASS=2; 2. Verilator build (tb, harness, region counters);
#  3. idle first pass without windows (phase markers); 4. window files; 5. every program with its windows, 2 at a time;
#  6. OpenSTA power per window, one at a time; 7. evaluate.
# Usage: gates/g81b/run.sh <run_id>
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; R=gates/g81b/runs/$ID; mkdir -p $R
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); B=$(cd ../../_build/asap7 && pwd -W 2>/dev/null || pwd)
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work "$@"; }
S=/work/$R/sim/obj/simv; MAX=6000000
t0=$(date +%s)
dk opentsense:g81b-cc bash gates/g81b/build_sw.sh $R/sw gates/g81b/scale.txt 2 > $R/sw_build.log 2>&1 || { echo "software build failed"; tail $R/sw_build.log; exit 1; }
cp $R/sw_build.log $R/sw/build.log
dk opentsense:g93a bash gates/g81b/build_sim.sh $R/sim > $R/sim_build.log 2>&1 || { echo "sim build failed"; tail $R/sim_build.log; exit 1; }
t1=$(date +%s)
mkdir -p $R/idle_pass1
dk -w /work/$R/idle_pass1 opentsense:g93a bash -c "$S +hex=/work/$R/sw/idle.hex +max=$MAX > run.log 2>&1" || { echo "idle pass 1 failed"; exit 1; }
dk opentsense:g93a python gates/g81b/windows.py gates/g81b/dry/dry_run2.log gates/g81b/scale.txt $R/idle_pass1/run.log $R/windows \
  > $R/windows.log 2>&1 || { echo "windows failed"; cat $R/windows.log; exit 1; }
t2=$(date +%s)
ls $R/windows/*.txt | xargs -n1 basename | sed 's/\.txt$//' | xargs -P 2 -I{} bash -c \
  "s=\$(date +%s); MSYS_NO_PATHCONV=1 docker run --rm -v '$REPO:/work' -w /work/$R opentsense:g93a bash -c 'mkdir -p {} && cd {} && \
   $S +hex=/work/$R/sw/{}.hex +max=$MAX +windows=/work/$R/windows/{}.txt +win_len=1000 +vcd_prefix=raw_ > run.log 2>&1; rc=\$?; \
   for f in raw_*.vcd; do [ -e \"\$f\" ] && python /work/gates/g81a/vcd_names.py ../sim/netlist.v \$f w\${f#raw_} > /dev/null && rm \$f; done; exit \$rc'; \
   echo \"{} exit=\$? wall_s=\$(( \$(date +%s)-s )) \$(grep -h RESULT $R/{}/run.log) \$(grep -h WINDOWS $R/{}/run.log)\"" | tee $R/sims.log
t3=$(date +%s)
for d in $(ls $R/windows/*.txt | xargs -n1 basename | sed 's/\.txt$//'); do
  mkdir -p $R/$d/power
  for v in $R/$d/w*.vcd; do
    [ -e "$v" ] || continue
    n=$(basename $v .vcd)
    dk -v "$B:/build:ro" -e RES=/build/asap7-ibex/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT -e VCD=/work/$v -e VCD_SCOPE=tb/dut \
      "$ORFS_IMAGE" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit /work/opentsense/power/vcd_power.tcl > $R/$d/power/$n.txt 2>&1
  done
  echo "$d power: $(ls $R/$d/power | wc -l) windows; $(grep -h -m1 Annotated $R/$d/power/*.txt | sort | uniq -c | tr '\n' ' ')"
done | tee $R/power.log
t4=$(date +%s)
dk -e OPENTSENSE_IMAGE="$(docker image inspect opentsense:g93a --format '{{.Id}}')" -e CC_IMAGE="$(docker image inspect opentsense:g81b-cc --format '{{.Id}}')" \
  -e ORFS_IMAGE="$ORFS_IMAGE" opentsense:g93a python gates/g81b/evaluate.py $R 2>&1 | tee $R/evaluate.log
RC=${PIPESTATUS[0]}
echo "{\"build_s\": $((t1-t0)), \"idle_pass1_s\": $((t2-t1)), \"sims_s\": $((t3-t2)), \"power_s\": $((t4-t3)), \"total_s\": $(( $(date +%s)-t0 ))}" | tee $R/timing.json
echo "EXIT=$RC"
