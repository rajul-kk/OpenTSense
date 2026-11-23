#!/bin/bash
# G94 dry: after-5 ms floors at levels 4 and 5 for every stack and solver (floor_after.py); 3D-ICE and PACT first,
# HotSpot last (the slow one: about 6.5 s a step on the 3d stack, 2,496 steps at level 5). Resumes per unit.
# Usage (host, repo root): bash gates/g94/dry/floor_after.sh [passes] [memory]
#   passes: solver groups run in turn, default "ice,pact hs"; memory: the container's cap, default 4g (HotSpot needed
#   more than 2.9 GB without swap, dry/lu_check_noswap_oom/). Hold a slot of the cap's size.
set -uo pipefail
cd "$(dirname "$0")/../../.."
OUT=gates/g94/dry/floor_after
PASSES=${1:-"ice,pact hs"}; MEM=${2:-4g}
mkdir -p "$OUT"
for sv in $PASSES; do
  MSYS_NO_PATHCONV=1 docker run --rm --name "g94-floor-${sv/,/-}" --memory "$MEM" -v "$(pwd -W):/work" -w /work \
    -e PYTHONPATH=/work opentsense:g94b python gates/g94/dry/floor_after.py "$OUT" 3d,25d_regions,3d_bottom "$sv" 4,5 \
    || exit $?
done
