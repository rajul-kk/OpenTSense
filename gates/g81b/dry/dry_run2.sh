#!/bin/bash
# G81b dry run, part 1 again after the harness plusarg fix: rebuild, then every program at LSF=1 / NPASS=1, no windows.
cd /d/Work/FYP-search/fyp/opentsense || exit 1
REPO=$(pwd -W); D=gates/g81b/dry; S=/work/$D/sim/obj/simv
{
s=$(date +%s); MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work opentsense:g93a bash gates/g81b/build_sim.sh $D/sim; echo "build_s $(( $(date +%s)-s ))"
ls $D/sw1/*.hex | xargs -n1 basename | sed 's/\.hex$//' | xargs -P 2 -I{} bash -c \
  "s=\$(date +%s); MSYS_NO_PATHCONV=1 docker run --rm -v '$REPO:/work' -w /work/$D/runs1 opentsense:g93a bash -c 'mkdir -p {} && cd {} && $S +hex=/work/$D/sw1/{}.hex +max=6000000 > run.log 2>&1'; echo \"{} wall_s=\$(( \$(date +%s)-s )) \$(grep RESULT $D/runs1/{}/run.log) \$(grep -c . $D/runs1/{}/timeline.csv) rows\""
echo EXIT=0
} > $D/dry_run2.log 2>&1
