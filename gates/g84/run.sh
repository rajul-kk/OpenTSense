#!/bin/bash
# G84: build the case set and score it on the host and inside the image, then evaluate bars (v), (a), (b), (c).
# Usage: gates/g84/run.sh <run_id> [image]
set -euo pipefail
cd "$(dirname "$0")/../.."
ID=$1; IMG=${2:-opentsense:g93a}; R=gates/g84/runs/$ID; mkdir -p $R/host $R/image
EST=average,field_model,bayes_power,inverted
python gates/g84/make_cases.py $R/host/cases.npz 2>&1 | tee $R/host/make_cases.log
python -m opentsense.bench.score $R/host/cases.npz --estimators $EST --out $R/host 2>&1 | tee $R/host/score.log
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W 2>/dev/null || pwd):/work" -w /work -e PYTHONPATH=/work \
  -e OPENTSENSE_IMAGE="$(docker image inspect "$IMG" --format '{{.Id}}')" "$IMG" bash -c \
  "python gates/g84/make_cases.py $R/image/cases.npz > $R/image/make_cases.log 2>&1 && python -m opentsense.bench.score $R/image/cases.npz --estimators $EST --out $R/image > $R/image/score.log 2>&1"
python gates/g84/evaluate.py $R 2>&1 | tee $R/evaluate.log
