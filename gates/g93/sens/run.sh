#!/bin/bash
# Goal 11: beol_board.py on S1, S2, S4 at 500 um cells in opentsense:g94b (3D-ICE, about 0.8 GB per solve at
# 97k nodes, gates/g93/dry/size_probe_lid.jsonl). S3 (334k nodes) needs its own larger container, not run here.
# Usage (host, repo root, holding a light slot of 2 GB): bash gates/g93/sens/run.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
MSYS_NO_PATHCONV=1 docker run --rm --name g93-beol-board --memory 2g --memory-swap 2g -v "$(pwd -W):/work" -w /work \
  -e PYTHONPATH=/work -e OTS_IMAGE=opentsense:g94b opentsense:g94b \
  python gates/g93/sens/beol_board.py gates/g93/sens/runs 500 s1,s2,s4
