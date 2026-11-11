#!/bin/bash
# G81b: Verilator build of the routed ASAP7 ibex with the G81b testbench and harness (G81a flags), in opentsense:g93a.
# Usage (in the container, from the repo root): gates/g81b/build_sim.sh <out dir>
set -euo pipefail
O=$1; G72=gates/g72/runs/main; mkdir -p $O
sed 's/\r$//' $G72/sim/ibex/netlist.v > $O/netlist.v
python gates/g81a/vl_models.py $G72/sim/models_ibex $O/netlist.v $O/models.v
python gates/g81b/regions.py $O/netlist.v $G72/sim/models_ibex $G72/power/ibex_loc.csv $O/regions.vh | tee $O/regions.log
verilator --cc --exe --build --timing --trace --trace-underscore -j 1 --output-split 2000 --output-split-cfuncs 2000 \
  -MAKEFLAGS "OPT_FAST=-O1 -j 1" -Wno-fatal -Wno-lint -Wno-style --top-module tb -I$O -Mdir $O/obj -o simv \
  $O/models.v $O/netlist.v gates/g81b/tb/ibex_tb_g81b.v gates/g81b/tb/main.cpp > $O/build.log 2>&1
ls -la $O/obj/simv
