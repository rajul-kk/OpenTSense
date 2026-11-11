#!/bin/bash
# G92e dry run 2: full 25 C traces to 1 s (FLAT=0, FLOOR_A=0: no early stop) for the two G92d SDFHx3 failures, four variants
cd "$(dirname "$0")/../../.."
W="(CLK * D * SE * SI * QN);(CLK * !D * SE * !SI * QN)"
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work -e TEMPS=25 -e J=2 -e FLAT=0 -e FLOOR_A=0 "$@"; }
O=gates/g92e/dry/probe2.log; : > $O
for v in "" "-e TAIL=0.1" "-e CONT_OPTS=reltol=1e-6" "-e CONT_OPTS=reltol=1e-6 -e TAIL=0.1"; do
  dk $v opentsense:g75spice python gates/g92e/dry/probe.py asap7 SDFHx3_ASAP7_75t_R "$W" >> $O 2>&1
done
echo "EXIT=$?" >> $O
