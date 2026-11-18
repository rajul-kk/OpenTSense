#!/bin/bash
# G81e step 1: request traces of every G81b program (G81b's hex files), two at a time; traces gzipped.
# Usage (host, under the heavy slot): bash gates/g81e/step1/run.sh <run_id>
# Resumable: the build is reused if simv exists, and a program is skipped only when it has an `ok` marker, written
# after simv exits 0 and its trace is gzipped. A RESULT line and a gzipped trace are not enough: an interrupted first
# launch left two of them with traces missing their start (run 1, 16 Nov), so every other state reruns from scratch.
set -uo pipefail
cd "$(dirname "$0")/../../.."
ID=$1; R=gates/g81e/runs/step1-$ID; SW=gates/g81b/runs/main/sw; mkdir -p $R
REPO=$(pwd -W 2>/dev/null || pwd); S=/work/$R/sim/obj/simv; MAX=6000000
dk() { MSYS_NO_PATHCONV=1 docker run --rm -v "$REPO:/work" -w /work "$@"; }
t0=$(date +%s)
[ -s $R/sim/obj/simv ] || dk opentsense:g93a bash gates/g81e/step1/build_sim.sh $R/sim > $R/sim_build.log 2>&1 || { echo "sim build failed"; tail $R/sim_build.log; exit 1; }
t1=$(date +%s)
ls $SW/*.hex | xargs -n1 basename | sed 's/\.hex$//' | xargs -P 2 -I{} bash -c \
  "[ -f $R/{}/ok ] && exit 0; rm -rf $R/{}; \
   s=\$(date +%s); MSYS_NO_PATHCONV=1 docker run --rm -v '$REPO:/work' -w /work/$R opentsense:g93a bash -c 'mkdir -p {} && cd {} && \
   $S +hex=/work/$SW/{}.hex +max=$MAX +reqlog=req.txt > run.log 2>&1 && gzip -f req.txt && touch ok'; \
   echo \"{} exit=\$? wall_s=\$(( \$(date +%s)-s )) \$(grep -h RESULT $R/{}/run.log)\"" | tee -a $R/sims.log
echo "{\"build_s\": $((t1-t0)), \"sims_s\": $(( $(date +%s)-t1 ))}" > $R/timing.json
