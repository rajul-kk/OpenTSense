#!/bin/bash
# G93 noise floor: the parity units in the image (A18), S2 at 500 um in each solver, against which the Kaggle build's
# same units are compared (floor_summary.py). Output floor_image/ (one JSON per unit, resumes per unit).
# Usage (host, repo root, holding a light slot of 2 GB; S2 at 500 um peaked at 0.91 GB in HotSpot): bash gates/g93/dry/floor_image.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
for sv in ice hs pact; do
  MSYS_NO_PATHCONV=1 docker run --rm --name "g93-floor-$sv" --memory 2g --memory-swap 2g -v "$(pwd -W):/work" -w /work \
    -e PYTHONPATH=/work -e OTS_IMAGE=opentsense:g94b opentsense:g94b \
    python gates/g93/dry/floor.py gates/g93/dry/floor_image 1 s2 "$sv" || echo "unit s2 500 $sv failed"
done
