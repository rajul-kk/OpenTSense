#!/bin/bash
# G70 smoke run: ORFS gcd (sky130hd, default activity) -> OpenSTA power -> single-die stack -> 3D-ICE and PACT.
# Usage: gates/g70/run.sh <run_id> [image]     outputs go to gates/g70/runs/<run_id>/
set -euo pipefail
cd "$(dirname "$0")/../.."
ID=$1; IMG=${2:-opentsense:dev}; R=gates/g70/runs/$ID; mkdir -p "$R"
t0=$(date +%s)
scripts/orfs_flow.sh sky130hd gcd "$R/orfs"
t1=$(date +%s)
set -a; . docker/versions.env; set +a
IMG_ID=$(docker image inspect "$IMG" --format '{{.Id}}')
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W 2>/dev/null || pwd):/work" -e OPENTSENSE_IMAGE="$IMG_ID" -e ORFS_IMAGE="$ORFS_IMAGE" "$IMG" python gates/g70/thermal.py "$R"
t2=$(date +%s)
echo "{\"orfs_s\": $((t1-t0)), \"thermal_s\": $((t2-t1)), \"total_s\": $((t2-t0))}" > "$R/timing.json"
cat "$R/timing.json"
