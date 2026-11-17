#!/bin/bash
# G93 size probe: every stack x solver, one container each, in order of size; output gates/g93/dry/size_probe.jsonl.
# Usage (host, under the heavy slot): bash gates/g93/dry/size_probe.sh [image]
cd "$(dirname "$0")/../../.."
IMG=${1:-opentsense:g93a}; OUT=gates/g93/dry/size_probe.jsonl; : > $OUT
for sc in "s1 250" "s4 250" "s2 250" "s3 500"; do set -- $sc
  for solver in ice hs pact; do
    MSYS_NO_PATHCONV=1 timeout 3600 docker run --rm -v "$(pwd -W 2>/dev/null || pwd):/w" -w /w -e PYTHONDONTWRITEBYTECODE=1 \
      "$IMG" python gates/g93/dry/size_probe.py $1 $2 $solver /tmp/probe | tail -1 | tee -a $OUT
  done
done
