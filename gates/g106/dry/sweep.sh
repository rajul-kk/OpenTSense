#!/bin/bash
# G106 dry sweep in opentsense:g103 (ngspice, ASAP7 and IHP models, three corners); 16 s per deck on average (18 Nov).
# Usage (host, repo root, holding a light slot of 1 GB): bash gates/g106/dry/sweep.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
MSYS_NO_PATHCONV=1 docker run --rm --name g106-sweep --memory 1g -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work \
  -e OTS_IMAGE=opentsense:g103 opentsense:g103 python gates/g106/dry/sweep.py gates/g106/dry/sweep.json
