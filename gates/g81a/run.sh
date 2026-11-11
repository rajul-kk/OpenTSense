#!/bin/bash
# G81a: Verilator gate-level windows of the routed ASAP7 ibex (G72's netlist, models and windows) -> OpenSTA power,
# scored against G72's Icarus results. Usage: gates/g81a/run.sh <run_id>
set -uo pipefail
cd "$(dirname "$0")/../.."
ID=$1; IMG=opentsense:g93a; R=gates/g81a/runs/$ID; G72=gates/g72/runs/main; mkdir -p $R/power $R/sim
set -a; . docker/versions.env; set +a
REPO=$(pwd -W 2>/dev/null || pwd); B=$(cd ../../_build/asap7 && pwd -W 2>/dev/null || pwd)
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work "$@"; }
t0=$(date +%s)
# 1. models and Verilator build (Amendment 1 flags)
dk "$IMG" bash -c "sed 's/\r$//' $G72/sim/ibex/netlist.v > $R/sim/netlist.v && python gates/g81a/vl_models.py $G72/sim/models_ibex $R/sim/netlist.v $R/sim/models.v && \
  verilator --binary --timing --trace --trace-underscore -j 4 --output-split 2000 --output-split-cfuncs 2000 -MAKEFLAGS OPT_FAST=-O1 -Wno-fatal -Wno-lint -Wno-style \
  --top-module tb -Mdir $R/sim/obj -o simv $R/sim/models.v $R/sim/netlist.v opentsense/power/tb/ibex_tb.v > $R/sim/build.log 2>&1" || { echo "build failed"; exit 1; }
t1=$(date +%s)
declare -A MAX=([0]=30000 [1]=30000 [2]=30000 [3]=30000 [4]=2600)        # G72's IBEX_MAX
for k in 0 1 2 3 4; do
  H=/work/gates/g72/inputs/ibex_hex/k$k.hex
  # window run: ends at the window end (Verilator ignores \$dumpoff), then the name map
  s=$(date +%s)
  dk -w /work/$R/sim "$IMG" bash -c "./obj/simv +hex=$H +win_start=1500 +win_len=1000 +vcd=k${k}_raw.vcd +max=2500 > k${k}_win.log 2>&1 && \
    python /work/gates/g81a/vcd_names.py netlist.v k${k}_raw.vcd k$k.vcd && rm k${k}_raw.vcd"
  e=$(date +%s)
  # function run: to G72's cycle limit, VCD discarded
  dk -w /work/$R/sim "$IMG" bash -c "./obj/simv +hex=$H +win_start=1500 +win_len=1000 +vcd=/dev/null +max=${MAX[$k]} > k${k}_fun.log 2>&1"
  f=$(date +%s)
  echo "{\"window_s\": $((e-s)), \"function_s\": $((f-e)), \"function_cycles\": ${MAX[$k]}}" > $R/sim/k${k}_timing.json
  dk -v "$B:/build:ro" -e RES=/build/asap7-ibex/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT -e VCD=/work/$R/sim/k$k.vcd -e VCD_SCOPE=tb/dut \
    "$ORFS_IMAGE" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit /work/opentsense/power/vcd_power.tcl > $R/power/ibex_k$k.txt 2>&1
  echo "k$k done: $(grep -m1 Annotated $R/power/ibex_k$k.txt) $(grep -m1 '^Total' $R/power/ibex_k$k.txt)"
done
t2=$(date +%s)
dk -e OPENTSENSE_IMAGE="$(docker image inspect "$IMG" --format '{{.Id}}')" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g81a/evaluate.py $R $G72 2>&1 | tee $R/evaluate.log
RC=${PIPESTATUS[0]}   # evaluate.py status (fixed 8 Nov, after scoring: EXIT used to print the timing echo's status)
echo "{\"build_s\": $((t1-t0)), \"sim_power_s\": $((t2-t1)), \"total_s\": $(( $(date +%s)-t0 ))}" | tee $R/timing.json
echo "EXIT=$RC"
