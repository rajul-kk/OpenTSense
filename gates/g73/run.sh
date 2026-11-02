#!/bin/bash
# G73: identifiability per die against measured power error. Usage: gates/g73/run.sh <run_id> [--plumbing] [image]
set -euo pipefail
cd "$(dirname "$0")/../.."
ID=$1; FLAG=${2:-}; IMG=${3:-opentsense:g71dev}
R=gates/g73/runs/$ID; mkdir -p "$R"
REPO=$(pwd -W 2>/dev/null || pwd); E=$(cd ../../experiments && pwd -W 2>/dev/null || pwd); A7=$(cd ../../_build/asap7 && pwd -W 2>/dev/null || pwd)
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
t0=$(date +%s)
MSYS_NO_PATHCONV=1 docker run --rm -e OPENTSENSE_IMAGE="$IMG_ID" -v "$REPO:/work" -v "$E:/exp:ro" -v "$A7:/a7:ro" -w /work "$IMG" \
  python gates/g73/run.py /exp/scratch_archive_2026-10-29/sens /a7 /exp/code "$R" $FLAG 2>&1 | tee "$R/run.log"
echo "{\"total_s\": $(( $(date +%s)-t0 ))}" > "$R/timing.json"
