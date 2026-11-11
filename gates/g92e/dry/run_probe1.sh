#!/bin/bash
# G92e dry run 1: the two G92d ASAP7 RVT SDFHx3 failures at 25 C, four variants (not scored)
cd "$(dirname "$0")/../../.."
W="(CLK * D * SE * SI * QN);(CLK * !D * SE * !SI * QN)"
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work -e TEMPS=25 -e J=2 "$@"; }
O=gates/g92e/dry/probe1.log; : > $O
dk opentsense:g75spice python gates/g92e/dry/probe.py asap7 SDFHx3_ASAP7_75t_R "$W" >> $O 2>&1
dk -e TAIL=0.1 opentsense:g75spice python gates/g92e/dry/probe.py asap7 SDFHx3_ASAP7_75t_R "$W" >> $O 2>&1
dk -e CONT_OPTS="reltol=1e-6" opentsense:g75spice python gates/g92e/dry/probe.py asap7 SDFHx3_ASAP7_75t_R "$W" >> $O 2>&1
dk -e CONT_OPTS="reltol=1e-6" -e TAIL=0.1 opentsense:g75spice python gates/g92e/dry/probe.py asap7 SDFHx3_ASAP7_75t_R "$W" >> $O 2>&1
echo "EXIT=$?" >> $O
