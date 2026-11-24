#!/bin/bash
# G94: HotSpot's transient dump streamed through stdout (19 Nov) against the file path's saved outputs, in
# opentsense:g94b: lu_reuse_check cases (lu_check/g94b.npz) and the small stack at level 5
# (kaggle_parity/small_hs_L5.npz), then the solver tests. Hold a slot of 3 GB.
set -uo pipefail
cd "$(dirname "$0")/../../.."
O=gates/g94/dry/stream_check
MSYS_NO_PATHCONV=1 docker run --rm --name g94-stream --memory 2900m -v "$(pwd -W):/work" -w /work -e PYTHONPATH=/work \
  opentsense:g94b bash -c "python gates/g94/dry/lu_reuse_check.py run $O/hs.npz 4 && \
  python gates/g94/dry/kaggle_floor_hs.py ref $O/small_hs_L5.npz && python -m pytest -q tests/test_solvers.py && \
  python -c \"import sys; sys.path.insert(0, 'gates/g94/dry'); from kaggle_floor_hs import agree; \
print(agree('gates/g94/dry/lu_check/g94b.npz', '$O/hs.npz')); \
print(agree('gates/g94/dry/kaggle_parity/small_hs_L5.npz', '$O/small_hs_L5.npz'))\""
echo "rc=$?"
