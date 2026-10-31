# G70: the pinned environment rebuilds from scratch

Registration and pass criteria: `../../../todo-gates.md` (G70, with amendment 1).

## How to run
```
scripts/build_image.sh opentsense:g70a --no-cache     # clean build 1
gates/g70/run.sh a opentsense:g70a                     # smoke run 1
                                                       # --no-cache rebuilds every layer from the pinned inputs
scripts/build_image.sh opentsense:g70b --no-cache     # clean build 2
gates/g70/run.sh b opentsense:g70b                     # smoke run 2
python gates/g70/compare.py gates/g70/runs/a gates/g70/runs/b    # criterion (d)
```
Criteria: (a) the builds need no manual steps; (b) `runs/*/timing.json` total ≤ 3600 s; (c) `runs/*/manifest.json` lists every tool version, the repo commit and the image ID; (d) `compare.py` reports `d_pass: true`.

## Pre-run checks (31 Oct, not part of the verdict)
- The converters were tested against the exploratory WSL builds (3D-ICE 4953952, patched PACT from G47), with the lockfile's Python packages:
  - uniform 1 W on a 3 × 3 mm die: 3D-ICE 3.098 K, PACT 3.100 K, 1-D hand calculation 3.097 K. Units and layer order are right.
  - 0.5 W single-cell hotspot plus 1 W uniform: both peaks are in the same cell (orientation right), but they differ by 2.98 K (10.3%; RMS 4.2% of the mean rise). This is lateral spreading with one node per layer; G71 must resolve it (finer vertical layering) before its 1 K bar can pass.
- `spreader` is a 3D-ICE keyword, so the converter prefixes stack element names with `S_`.
