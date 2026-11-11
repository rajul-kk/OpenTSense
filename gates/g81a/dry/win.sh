#!/bin/bash
# G81a dry run (not scored): window k0 ending the simulation at the window end (Verilator ignores $dumpoff), then OpenSTA.
cd "$(dirname "$0")/../../.."
set -a; . docker/versions.env; set +a
REPO=$(pwd -W); B=$(cd ../../_build/asap7 && pwd -W); D=gates/g81a/dry/underscore; O=gates/g81a/dry/dry.log
MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work/$D opentsense:g93a ./obj/simv +hex=/work/gates/g72/inputs/ibex_hex/k0.hex +win_start=1500 +win_len=1000 +vcd=k0w.vcd +max=2500 > $D/k0w.log 2>&1
MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$B:/build:ro" -w /work -e RES=/build/asap7-ibex/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT \
  -e VCD=/work/$D/k0w.vcd -e VCD_SCOPE=tb/dut "$ORFS_IMAGE" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit \
  /work/opentsense/power/vcd_power.tcl > $D/pw_k0w.txt 2>&1
echo "underscore, sim ends at window end: $(grep -m1 'Annotated' $D/pw_k0w.txt) $(grep -m1 'unannotated' $D/pw_k0w.txt) | $(grep -m1 '^Total' $D/pw_k0w.txt)" >> $O
echo "EXIT=$?" >> $O
