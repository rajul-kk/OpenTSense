#!/bin/bash
# G93 size probe for the lidded stacks (draft, "Package: lid and cooler", 17 Nov 2026), beside size_probe.jsonl:
# S1, S2, S4 at 500 um cells, each solver in its own container (uniform power over the grid, as size_probe.sh: the
# cost depends on the node count, not on where the power is; nodes, RAM, wall time, no temperatures).
# Usage (host, repo root, holding a heavy slot of 3 GB; the old probe peaked at 2.03 GB at 93k nodes (S2, HotSpot)): bash gates/g93/dry/size_probe_lid.sh [image]
set -uo pipefail
cd "$(dirname "$0")/../../.."
IMG=${1:-opentsense:g94b}; OUT=gates/g93/dry/size_probe_lid.jsonl; LOG=gates/g93/dry/size_probe_lid.log
: > "$OUT"; : > "$LOG"
for st in s1 s2 s4; do
  for sv in ice hs pact; do
    # timeout stops only the docker client, so the container is named and killed on timeout (no second 3 GB container)
    name=g93-size-lid-$st-$sv
    line=$(MSYS_NO_PATHCONV=1 timeout 3600 docker run --rm --name "$name" --memory 3g --memory-swap 3g \
      -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work "$IMG" python gates/g93/dry/size_probe.py "$st" 500 "$sv" /tmp/w \
      2>> "$LOG" | tail -1)
    rc=$?
    docker kill "$name" > /dev/null 2>&1
    case "$line" in
      "{"*) echo "$line" >> "$OUT" ;;
      *) echo "{\"stack\": \"$st\", \"cell_um\": 500, \"solver\": \"$sv\", \"ok\": false, \"error\": \"exit $rc, no result line\"}" >> "$OUT" ;;
    esac
    tail -1 "$OUT"
  done
done
