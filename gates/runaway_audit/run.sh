#!/bin/bash
# Runaway audit (audit.py). Usage (host, repo root's gates/runaway_audit, under a medium 2 GB slot):
#   bash gates/runaway_audit/run.sh <out dir> [unit ...]      e.g. runs/measure asap7:tt
# The image is G95's and G101's (opentsense:g75spice), launched by the ID recorded in <out dir>/image.txt.
set -euo pipefail
cd "$(dirname "$0")/../.."
O=gates/runaway_audit/$1; shift
IMG=opentsense:g75spice
B=$(cd ../../_build && (pwd -W 2>/dev/null || pwd))
REPO=$(pwd -W 2>/dev/null || pwd)
mkdir -p "$O"
IMGID=$(docker image inspect "$IMG" --format '{{.Id}}')
{ echo "image $IMG $IMGID"; echo "repo $(git rev-parse HEAD) dirty=$(git status --porcelain | wc -l)"
  sha256sum gates/runaway_audit/audit.py gates/g95/sweep.py opentsense/thermal/runaway.py opentsense/thermal/electrothermal.py
} > "$O/inputs.txt"
s=$(date +%s)
MSYS_NO_PATHCONV=1 docker run --rm --memory=2g --memory-swap=2g -e PYTHONDONTWRITEBYTECODE=1 -v "$REPO:/work" \
  -v "$B:/b:ro" -w /work -e PYTHONPATH=/work "$IMGID" python gates/runaway_audit/audit.py "$O/audit.json" "$@" \
  >> "$O/audit.log" 2>&1 && rc=0 || rc=$?
echo "rc=$rc after $(( $(date +%s) - s )) s" >> "$O/audit.log"
exit $rc
