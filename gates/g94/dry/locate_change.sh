#!/bin/bash
# G94 dry: locate_change.py on the 3d step case, levels 0-5, in opentsense:g94b.
# Usage (host, repo root, holding a heavy slot of 3 GB): bash gates/g94/dry/locate_change.sh
cd "$(dirname "$0")/../../.."
mkdir -p gates/g94/dry/locate
MSYS_NO_PATHCONV=1 docker run --rm --name g94-locate --memory 3g -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work \
  opentsense:g94b python gates/g94/dry/locate_change.py 78 6 gates/g94/dry/locate/change.json
