# Rebuilt opentsense:g94b against the original image (17 Nov 2026)

`bash gates/g94/dry/lu_check_rebuilt.sh` (heavy slot, `--memory 2900m` with Docker's default swap, as lu_check_v1):
the rebuilt image (LF patch, both leak fixes, LU released before HotSpot's closing steady solve) against
`lu_check_v1/g94a.npz`, the unpatched image's output. `compare.txt`: every array identical, exit 0; the 3d case
(seed 1, 4 slots, level 0) took 213 s (`g94b.log`), against 533.6 s for the unpatched image and 241.6 s for the
first patched build (lu_check_v1/).

The reference file predates the binary hash (`compare` prints "unrecorded"), so the hash guard does not cover this
pair. Its source is the run command that wrote it (`docker run ... opentsense:g94a ... lu_reuse_check.py run
lu_check/g94a.npz 4`, moved to lu_check_v1/) and its wall time (533.6 s, the unpatched per-step factorisation).

`../lu_check_noswap_oom/`: the first attempt, with `--memory-swap 2900m` (no swap); HotSpot was killed on the 3d case
with no output, so nothing was compared.
