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

## Registration (as fixed before the run)
- **Pass if all hold:**
  - (a) The image builds with no manual steps.
  - (b) The smoke run finishes in ≤ 1 h on the laptop.
  - (c) Each run writes a manifest with every tool version and the repo commit.
  - (d) A second clean rebuild reproduces the power report exactly and the temperatures within 0.01 K.
- **Amendment 1 (31 Oct, before any run):**
  - Two images: ORFS from the official image pinned by digest, and everything else from `docker/Dockerfile`.
  - The OpenVAF/OSDI device models move to G72, after a licence check of their Verilog-A sources.
  - Criterion (c) also records the image IDs.

## Verdict: PASS (1 Nov 2026)
| Criterion | Result |
|---|---|
| (a) no manual steps | Both `--no-cache` builds succeeded: g70a `819a8d5a` (3 min 26 s), g70b `d43915f7` (3 min 13 s) |
| (b) ≤ 1 h | Run A 106 s, run B 144 s |
| (c) manifest | `runs/*/manifest.json`: tool versions, 3D-ICE, SuperLU_MT and PACT commits, repo `4ec7e01`, image ID, ORFS digest |
| (d) reproducible | 822/822 power-report lines identical; max \|ΔT\| = 0.000 K (3D-ICE and PACT) |

Notes:
- Run B's manifest says `dirty: true` only because its own log file (`gates/g70/run_b.log`) was untracked in the repo while it ran. That log has since been moved to `runs/b/run.log`.
- The first attempts at build A and run B were cut off when Windows ran out of memory and killed WSL (see `fyp/failures.md`); they were discarded.
- On the gcd smoke stack, the 3D-ICE and PACT peaks differ by 0.21 K. Agreement between the two tools is tested properly in G71.
