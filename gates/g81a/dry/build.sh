#!/bin/bash
# G81a dry run (not scored): Verilator build of the routed ASAP7 ibex + G72 testbench, flag variant $1, then window k0 only.
# Usage (inside opentsense:g93a, from the repo root): gates/g81a/dry/build.sh <variant> ; variants: plain | public | noinline
set -euo pipefail
V=$1; D=gates/g81a/dry/$V; mkdir -p $D; G72=gates/g72/runs/main
sed 's/\r$//' $G72/sim/ibex/netlist.v > $D/netlist.v
python gates/g81a/vl_models.py $G72/sim/models_ibex $D/netlist.v $D/models.v
case $V in plain) X="";; public) X="--public-flat-rw";; noinline) X="-fno-inline --public-flat-rw";; underscore) X="--trace-underscore";; esac
t0=$(date +%s)
verilator --binary --timing --trace -j 4 --output-split 2000 --output-split-cfuncs 2000 -MAKEFLAGS OPT_FAST=-O1 -Wno-fatal -Wno-lint -Wno-style \
  $X --top-module tb -Mdir $D/obj -o simv $D/models.v $D/netlist.v opentsense/power/tb/ibex_tb.v > $D/build.log 2>&1 || { grep -m20 "%Error" $D/build.log; exit 1; }
t1=$(date +%s)
( cd $D && ./obj/simv +hex=/work/gates/g72/inputs/ibex_hex/k0.hex +win_start=1500 +win_len=1000 +vcd=k0.vcd +max=30000 > k0.log 2>&1 )
t2=$(date +%s)
echo "variant $V build_s $((t1-t0)) sim_s $((t2-t1))"; tail -2 $D/k0.log; ls -la $D/k0.vcd
