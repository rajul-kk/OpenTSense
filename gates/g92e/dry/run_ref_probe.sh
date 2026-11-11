#!/bin/bash
# G92e dry run 3: the IHP dfrbp_1 reference under three solver variants (not scored)
cd "$(dirname "$0")/../../.."
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work -e J=3 "$@"; }
O=gates/g92e/dry/ref_probe.log; : > $O
dk opentsense:g75spice python gates/g92e/dry/ref_probe.py >> $O 2>&1
dk -e OPTS=reltol=1e-5 opentsense:g75spice python gates/g92e/dry/ref_probe.py >> $O 2>&1
dk -e TMAX=0.1n opentsense:g75spice python gates/g92e/dry/ref_probe.py >> $O 2>&1
echo "EXIT=$?" >> $O
