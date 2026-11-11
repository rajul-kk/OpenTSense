#!/bin/bash
# G81x: Icarus (hold and original testbench) and Verilator (hold testbench) windows of the routed ASAP7 ibex -> OpenSTA.
# Usage: gates/g81x/run.sh <run_id>
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; R=gates/g81x/runs/$ID; G72=gates/g72/runs/main; mkdir -p $R/power $R/sim/ivh $R/sim/ivx $R/sim/vl
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); B=$(cd ../../_build/asap7 && pwd -W 2>/dev/null || pwd)
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work "$@"; }
HEX=/work/gates/g72/inputs/ibex_hex
t0=$(date +%s)
# 1. Icarus: compile both testbenches with G72's models and netlist; window runs end at 2,500 ($dumpoff there anyway)
dk opentsense:g71dev bash -c "set -e; M=\$(ls $G72/sim/models_ibex/*.v); \
  iverilog -g2012 -s tb -o $R/sim/ivh/sim.vvp \$M $G72/sim/ibex/netlist.v gates/g81x/ibex_tb_hold.v; \
  iverilog -g2012 -s tb -o $R/sim/ivx/sim.vvp \$M $G72/sim/ibex/netlist.v opentsense/power/tb/ibex_tb.v; \
  for v in ivh ivx; do for k in 0 1 2 3 4; do echo \$v \$k; done; done | xargs -P 5 -n 2 sh -c \
  'cd $R/sim/\$0 && vvp -n sim.vvp +hex=$HEX/k\$1.hex +win_start=1500 +win_len=1000 +vcd=k\$1.vcd +max=2500 > k\$1.log 2>&1'" \
  > $R/sim/icarus.log 2>&1 || { echo "icarus failed"; cat $R/sim/icarus.log; exit 1; }
t1=$(date +%s)
# 2. Verilator: G81a's build and flags, hold testbench
dk opentsense:g93a bash -c "sed 's/\r$//' $G72/sim/ibex/netlist.v > $R/sim/vl/netlist.v && python gates/g81a/vl_models.py $G72/sim/models_ibex $R/sim/vl/netlist.v $R/sim/vl/models.v && \
  verilator --binary --timing --trace --trace-underscore -j 4 --output-split 2000 --output-split-cfuncs 2000 -MAKEFLAGS OPT_FAST=-O1 -Wno-fatal -Wno-lint -Wno-style \
  --top-module tb -Mdir $R/sim/vl/obj -o simv $R/sim/vl/models.v $R/sim/vl/netlist.v gates/g81x/ibex_tb_hold.v > $R/sim/vl/build.log 2>&1" || { echo "verilator build failed"; exit 1; }
declare -A MAX=([0]=30000 [1]=30000 [2]=30000 [3]=30000 [4]=2600)
for k in 0 1 2 3 4; do
  dk -w /work/$R/sim/vl opentsense:g93a bash -c "./obj/simv +hex=$HEX/k$k.hex +win_start=1500 +win_len=1000 +vcd=k${k}_raw.vcd +max=2500 > k${k}_win.log 2>&1 && \
    python /work/gates/g81a/vcd_names.py netlist.v k${k}_raw.vcd k$k.vcd && rm k${k}_raw.vcd && \
    ./obj/simv +hex=$HEX/k$k.hex +win_start=1500 +win_len=1000 +vcd=/dev/null +max=${MAX[$k]} > k${k}_fun.log 2>&1"
done
t2=$(date +%s)
# 3. OpenSTA power, one job at a time
for v in ivh ivx vl; do for k in 0 1 2 3 4; do
  dk -v "$B:/build:ro" -e RES=/build/asap7-ibex/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT -e VCD=/work/$R/sim/$v/k$k.vcd -e VCD_SCOPE=tb/dut \
    "$ORFS_IMAGE" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit /work/opentsense/power/vcd_power.tcl > $R/power/${v}_k$k.txt 2>&1
  echo "$v k$k: $(grep -m1 Annotated $R/power/${v}_k$k.txt) $(grep -m1 '^Total' $R/power/${v}_k$k.txt)"
done; done
t3=$(date +%s)
dk -e OPENTSENSE_IMAGE="$(docker image inspect opentsense:g93a --format '{{.Id}}')" -e ICARUS_IMAGE="$(docker image inspect opentsense:g71dev --format '{{.Id}}')" \
  -e ORFS_IMAGE="$ORFS_IMAGE" opentsense:g93a python gates/g81x/evaluate.py $R $G72 2>&1 | tee $R/evaluate.log
RC=${PIPESTATUS[0]}   # evaluate.py status (fixed 8 Nov, after scoring: EXIT used to print the timing echo's status)
echo "{\"icarus_s\": $((t1-t0)), \"verilator_s\": $((t2-t1)), \"power_s\": $((t3-t2)), \"total_s\": $(( $(date +%s)-t0 ))}" | tee $R/timing.json
echo "EXIT=$RC"
