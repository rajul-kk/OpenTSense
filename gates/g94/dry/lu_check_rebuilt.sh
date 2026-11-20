#!/bin/bash
# G94 dry: the rebuilt opentsense:g94b (LF patch, leak fixes, release before the steady solve) against the old
# image's output in lu_check_v1/g94a.npz (same cases: small stack, 3d seed 1, 4 slots, level 0).
# Same container limits as lu_check_v1: --memory 2900m with Docker's default swap (with --memory-swap 2900m HotSpot is
# killed on the 3d case without output: lu_check_noswap_oom/, 17 Nov 2026).
# Usage (host, repo root, holding a heavy slot of 2.9 GB): bash gates/g94/dry/lu_check_rebuilt.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
D=gates/g94/dry/lu_check
mkdir -p "$D"
rm -f "$D/g94b.npz" "$D/compare.txt"
MSYS_NO_PATHCONV=1 docker run --rm --memory 2900m -v "$(pwd -W):/work" -w /work \
  -e PYTHONPATH=/work opentsense:g94b python gates/g94/dry/lu_reuse_check.py run "$D/g94b.npz" 4 > "$D/g94b.log" 2>&1
rc=$?
echo "run rc=$rc" >> "$D/g94b.log"
[ $rc -eq 0 ] || { echo "run failed (rc=$rc), not compared" > "$D/compare.txt"; exit 1; }
python gates/g94/dry/lu_reuse_check.py compare gates/g94/dry/lu_check_v1/g94a.npz "$D/g94b.npz" > "$D/compare.txt" 2>&1
echo "compare rc=$?" >> "$D/compare.txt"
