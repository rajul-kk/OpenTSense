#!/bin/bash
# G81e step 1: G81b's gate-level ibex simulation with a request log. The testbench is G81b's (gates/g81b/tb), with one
# block inserted before its region counters, so the core, program, memory and timing are G81b's. Built as G81b's.
# Usage (in opentsense:g93a, repo root): bash gates/g81e/step1/build_sim.sh <out dir>
set -euo pipefail
O=$1; G72=gates/g72/runs/main; mkdir -p $O
sed 's/\r$//' $G72/sim/ibex/netlist.v > $O/netlist.v
python gates/g81a/vl_models.py $G72/sim/models_ibex $O/netlist.v $O/models.v
python gates/g81b/regions.py $O/netlist.v $G72/sim/models_ibex $G72/power/ibex_loc.csv $O/regions.vh > $O/regions.log
python - gates/g81b/tb/ibex_tb_g81b.v $O/ibex_tb_g81e.v <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, newline="").read()
log = r'''  // G81e request log: one line per granted request (gnt = req here), memory-mapped testbench registers excluded:
  // "cycle port we addr be", port I or D, addr and be in hex. File from +reqlog=<file>.
  integer reqf = 0; reg [1023:0] reqname;
  initial if ($value$plusargs("reqlog=%s", reqname)) reqf = $fopen(reqname, "w");
  always @(posedge clk) if (reqf != 0 && rst_n) begin
    if (instr_req) $fwrite(reqf, "%0d I 0 %08x f\n", cyc, instr_addr);
    if (data_req && !mmio) $fwrite(reqf, "%0d D %0d %08x %x\n", cyc, data_we, data_addr, data_be);
  end
'''
anchor = '`include "regions.vh"'
assert s.count(anchor) == 1
open(dst, "w", newline="").write(s.replace(anchor, log + anchor))
PY
verilator --cc --exe --build --timing --trace --trace-underscore -j 1 --output-split 2000 --output-split-cfuncs 2000 \
  -MAKEFLAGS "OPT_FAST=-O1 -j 1" -Wno-fatal -Wno-lint -Wno-style --top-module tb -I$O -Mdir $O/obj -o simv \
  $O/models.v $O/netlist.v $O/ibex_tb_g81e.v gates/g81b/tb/main.cpp > $O/build.log 2>&1
ls -la $O/obj/simv
