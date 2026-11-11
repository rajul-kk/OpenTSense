#!/bin/bash
# G92e dry run 4: dfrbp_1 reference to 1 ms (not scored)
cd "$(dirname "$0")/../../.."
O=gates/g92e/dry/ref_probe_1ms.log; : > $O
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work -e J=4 opentsense:g75spice python gates/g92e/dry/ref_probe_1ms.py >> $O 2>&1
echo "EXIT=$?" >> $O
