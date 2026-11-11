#!/bin/bash
cd /d/Work/FYP-search/fyp/opentsense || exit 1
{ s=$(date +%s); MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/work" -w /work opentsense:g93a bash gates/g81b/build_sim.sh gates/g81b/dry/sim; echo "build_s $(( $(date +%s)-s ))"; echo EXIT=$?; } > gates/g81b/dry/build.out 2>&1
