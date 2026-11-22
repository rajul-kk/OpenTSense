#!/bin/bash
# Goal 15: leak.py on S1, S2, S4 at 500 um cells in opentsense:g94b (3D-ICE, under 1 GB per solve; S1 about 26 s per
# solve, gates/g93/sens/cooler_runs), then cooler.py again into cooler_runs_v2 after its move to common.py (A15: the
# refactor must reproduce cooler_runs/).
# Usage (host, repo root, holding a light slot of 2 GB): bash gates/g93/sens/leak.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
run() { MSYS_NO_PATHCONV=1 docker run --rm --name g93-leak --memory 2g --memory-swap 2g -v "$(pwd -W):/work" -w /work \
  -e PYTHONPATH=/work -e OTS_IMAGE=opentsense:g94b opentsense:g94b python "$@"; }
run gates/g93/sens/leak.py gates/g93/sens/leak_runs 500 s1,s2,s4
run gates/g93/sens/cooler.py gates/g93/sens/cooler_runs_v2 500 s1,s2,s4
