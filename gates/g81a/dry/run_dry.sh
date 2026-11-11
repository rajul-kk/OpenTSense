#!/bin/bash
# G81a dry run (not scored): for each Verilator flag variant, build + window k0, then OpenSTA annotation and power on it.
cd "$(dirname "$0")/../../.."
set -a; . docker/versions.env; set +a
REPO=$(pwd -W); B=$(cd ../../_build/asap7 && pwd -W); O=gates/g81a/dry/dry.log; [ -n "${APPEND:-}" ] || : > $O
for V in ${VARIANTS:-plain public}; do
  MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work opentsense:g93a bash gates/g81a/dry/build.sh $V >> $O 2>&1
  D=gates/g81a/dry/$V
  [ -f $D/k0.vcd ] || { echo "variant $V: no VCD" >> $O; continue; }
  MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -v "$B:/build:ro" -w /work -e RES=/build/asap7-ibex/results/asap7/ibex/base -e CORNER=TT -e VTS=RVT \
    -e VCD=/work/$D/k0.vcd -e VCD_SCOPE=${SCOPE:-tb/dut} "$ORFS_IMAGE" /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad -no_init -exit \
    /work/opentsense/power/vcd_power.tcl > $D/pw_k0.txt 2>&1
  echo "variant $V: $(grep -m1 'Annotated' $D/pw_k0.txt) $(grep -m1 'unannotated' $D/pw_k0.txt) | $(grep -m1 '^Total' $D/pw_k0.txt)" >> $O
done
echo "G72 Icarus k0: $(grep -m1 '^Total' gates/g72/runs/main/power/ibex_k0.txt)" >> $O
echo "EXIT=$?" >> $O
