#!/bin/bash
# G81b dry run (fixes scale factors and NPASS; checks the harness). Not scored.
#  1. every program at LSF=1 / NPASS=1, no windows: start/stop/done cycles and the verify result;
#  2. harness check: G72's k0 program, one window at 1500 for 1000 cycles, against G81x's Verilator hold k0 window.
cd /d/Work/FYP-search/fyp/opentsense || exit 1
set -a; . docker/versions.env; set +a
REPO=$(pwd -W); B=$(cd ../../_build/asap7 && pwd -W)
D=gates/g81b/dry; S=/work/$D/sim/obj/simv
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work "$@"; }
{
mkdir -p $D/runs1
# 2. harness check first (short)
dk -w /work/$D/runs1 opentsense:g93a bash -c "echo 1500 > k0win.txt && $S +hex=/work/gates/g72/inputs/ibex_hex/k0.hex +max=2510 +windows=k0win.txt +win_len=1000 +vcd_prefix=k0w > k0w.log 2>&1; \
  python /work/gates/g81a/vcd_names.py /work/$D/sim/netlist.v k0w000.vcd k0w.vcd && rm k0w000.vcd"
dk -v "$B:/build:ro" -e RES=/build/asap7-ibex/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT -e VCD=/work/$D/runs1/k0w.vcd -e VCD_SCOPE=tb/dut \
  "$ORFS_IMAGE" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit /work/opentsense/power/vcd_power.tcl > $D/runs1/k0w_power.txt 2>&1
echo "harness k0: $(grep -m1 Annotated $D/runs1/k0w_power.txt) $(grep -m1 '^Total' $D/runs1/k0w_power.txt)"
echo "G81x vl k0: $(grep -m1 '^Total' gates/g81x/runs/main/power/vl_k0.txt)"
# 1. all programs, 2 at a time (host memory)
ls $D/sw1/*.hex | xargs -n1 basename | sed 's/\.hex$//' | xargs -P 2 -I{} bash -c \
  "s=\$(date +%s); MSYS_NO_PATHCONV=1 docker run --rm -v '$REPO:/work' -w /work/$D/runs1 opentsense:g93a bash -c 'mkdir -p {} && cd {} && $S +hex=/work/$D/sw1/{}.hex +max=6000000 > run.log 2>&1'; echo \"{} wall_s=\$(( \$(date +%s)-s )) \$(grep RESULT $D/runs1/{}/run.log)\""
echo EXIT=0
} > $D/dry_run.log 2>&1
