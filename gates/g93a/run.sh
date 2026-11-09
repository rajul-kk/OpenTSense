#!/bin/bash
# G93a: three thermal solvers on G71's stacks plus two new configs. Usage: gates/g93a/run.sh <run_id> [image]
cd "$(dirname "$0")/../.."
ID=${1:-main}; IMG=${2:-opentsense:g93a}
mkdir -p gates/g93a/runs/$ID
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W 2>/dev/null || pwd):/work" -w /work -e PYTHONPATH=/work \
  -e OPENTSENSE_IMAGE="$(docker image inspect "$IMG" --format '{{.Id}}')" "$IMG" \
  python gates/g93a/run.py gates/g93a/runs/$ID 2>&1 | tee gates/g93a/runs/$ID/run.log
echo "EXIT=${PIPESTATUS[0]}" >> gates/g93a/runs/$ID/run.log
