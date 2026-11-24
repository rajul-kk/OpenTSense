#!/bin/bash
# G94 gated run, the 3D-ICE and PACT units on this machine (HotSpot's on Kaggle, kaggle_gate_hs.py), in
# opentsense:g94b. Resumes per unit. Hold a slot of the cap's size.
# Usage (host, repo root): bash gates/g94/run_local.sh [memory, default 3g]
set -uo pipefail
cd "$(dirname "$0")/../.."
MSYS_NO_PATHCONV=1 docker run --rm --name g94-gate-icepact --memory "${1:-3g}" -v "$(pwd -W):/work" -w /work \
  -e PYTHONPATH=/work opentsense:g94b python gates/g94/run.py gates/g94/runs/main ice,pact
