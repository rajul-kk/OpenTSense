#!/bin/bash
# G74: rebuild inputs from the exploratory archive, then run the margin. Usage: gates/g74/run.sh <run_id> [--plumbing] [image]
set -euo pipefail
cd "$(dirname "$0")/../.."
ID=$1; FLAG=${2:-}; IMG=${3:-opentsense:g71dev}
R=gates/g74/runs/$ID; mkdir -p "$R"
REPO=$(pwd -W 2>/dev/null || pwd); E=$(cd ../../experiments && pwd -W 2>/dev/null || pwd); A7=$(cd ../../_build/asap7 && pwd -W 2>/dev/null || pwd)
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
dk() { MSYS_NO_PATHCONV=1 docker run --rm -e OPENTSENSE_IMAGE="$IMG_ID" -v "$REPO:/work" -v "$E:/exp:ro" -v "$A7:/a7:ro" -w /work "$IMG" "$@"; }
if [ ! -f gates/g74/out/inputs.npz ]; then
  mkdir -p gates/g74/out; dk python gates/g74/prep.py /exp/scratch_archive_2026-10-29 /a7 /exp/code gates/g74/out/inputs.npz 2>&1 | tee gates/g74/out/prep.log
fi
t0=$(date +%s)
dk python gates/g74/run.py gates/g74/out/inputs.npz /exp/code "$R" $FLAG 2>&1 | tee "$R/run.log"
echo "{\"total_s\": $(( $(date +%s)-t0 ))}" > "$R/timing.json"
