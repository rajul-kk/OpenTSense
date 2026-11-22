#!/bin/bash
# Goal 19: coldplate.py on S1, S2, S4 at 500 um cells in opentsense:g94b (3D-ICE with its 2RM channel model).
# Usage (host, repo root, holding a light slot of 2 GB): bash gates/g93/sens/coldplate.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
MSYS_NO_PATHCONV=1 docker run --rm --name g93-coldplate --memory 2g --memory-swap 2g -v "$(pwd -W):/work" -w /work \
  -e PYTHONPATH=/work -e OTS_IMAGE=opentsense:g94b opentsense:g94b \
  python gates/g93/sens/coldplate.py gates/g93/sens/coldplate_runs 500 s1,s2,s4
