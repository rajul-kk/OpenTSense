#!/bin/bash
# Run an ORFS design end to end in the pinned ORFS image, then extract instance locations and power.
# Usage: scripts/orfs_flow.sh <platform> <design> <out_dir on host>   e.g. sky130hd gcd gates/g70/runs/a/orfs
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . docker/versions.env; set +a
P=$1; D=$2; OUT=$3; mkdir -p "$OUT"
HOST_OUT=$(cd "$OUT" && pwd -W 2>/dev/null || pwd); HOST_REPO=$(pwd -W 2>/dev/null || pwd)
MSYS_NO_PATHCONV=1 docker run --rm -v "$HOST_OUT:/out" -v "$HOST_REPO:/repo:ro" -e OUT_DIR=/out "$ORFS_IMAGE" bash -c "
  source /OpenROAD-flow-scripts/env.sh >/dev/null 2>&1; cd /OpenROAD-flow-scripts/flow
  make WORK_HOME=/out DESIGN_CONFIG=./designs/$P/$D/config.mk > /out/flow.log 2>&1
  make WORK_HOME=/out DESIGN_CONFIG=./designs/$P/$D/config.mk RUN_SCRIPT=/repo/opentsense/power/extract.tcl run > /out/power.txt 2>&1
  openroad -version > /out/openroad_version.txt 2>&1 || true"
