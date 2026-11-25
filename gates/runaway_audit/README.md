# Runaway audit of G95, G101 and G103 (20 Nov 2026): the recorded margins hold under the confirmed classifier

**Finding, for the owner. No gate is amended.**
- **G95 and G103: the exact recorded endpoints hold.** For G95 (hot) and G103 (SS and FF corners; its TT control
  repeats G95), each recorded upper end s_hi is a certified runaway. At each recorded lower end s_lo, the loop
  certifiably has an operating point at or below 1000 K.
- **G101: a slightly wider bracket holds.** G101's perturbed tile sets recorded only their midpoint s*. The audit
  certifies a bracket about 2e-4 wide, relative, around each s* (see Limits), not G101's own endpoints.
- **Coverage.** 36 windows (3 kits x TT/SS/FF x 4 windows) and 48 G101 set checks (3 kits x 4 windows x 4 sets, each
  probed on both sides: 96 probes): none undecided, none failed (`record/audit.json`, `complete` true; `record/audit.log` ends `rc=0`).

## Why it was needed

The gates bracketed each margin with `runaway.critical_scale` while Newton's runaway exit assumed leakage convex in
T. G92e's tables are not convex (task runaway-audit; `opentsense/thermal/runaway.py:14-27`; C6-3 showed a false
runaway on a non-convex table, `tests/test_runaway.py:132`). The fixed
classifier (task runaway-fix) works as follows:
- **Runaway** is confirmed by fixed-point iteration from ambient passing T_cap = 1000 K.
- **Converged** is certified by an upper solution at or below T_cap.

Both verdicts refer to R with round-off negatives set to 0, and carry the float limit stated in `runaway`'s
docstring.

## What was run

`audit.py` rebuilds each kit and corner's operator and cases with G95's `sweep.load`, unchanged. For TT, it checks
them against G92e's recorded peaks (`sweep.check_against_g92e`, as G95 and G101 did). It then classifies:

| Source | Probes | Expected |
|---|---|---|
| G95 hot sweep (`gates/g95/runs/main/<kit>/sweep_<kit>.json`), = G103 TT control | recorded s_lo, s_hi | converged, runaway |
| G103 SS/FF (`gates/g103/runs/main/<kit>/<corner>/margin.json`) | recorded s_lo, s_hi | converged, runaway |
| G101 sets (`gates/g101/runs/main/<kit>/g101_<kit>.json`), only s* = sqrt(a b) recorded | s* (1 - 1e-4), s* (1 + 1e-4), with 1e-4 = G95's bisection rtol (`gates/g95/sweep.py:36`, `audit.py:129`) | converged, runaway |

The run used image `opentsense:g75spice` (G95's and G101's), with the ID and the code hashes in `record/inputs.txt`
and every unit's input hashes in `record/audit.json`. It took 732 s (`record/audit.log`). The record run started
from an empty folder, so no unit was reused. The resume check (a kept unit must match its hashed inputs) covers
only the listed files: it does not cover the placement file (named, not hashed), the image ID, or package
modules such as `response.py` and `maps.py`. Treat a resumed run as unverified on those.

## Non-monotone corner tables

Three G103 corner units have instances whose leakage falls with T. `classify`'s certificates assume a monotone loop
map, and its fixed-point check refuses such tables (`runaway.lowest_fixed_point`, `runaway.py:92-93`; this stopped
the first attempt), so the audit routes these windows to envelopes up front (`audit.py:106-111`):

| Unit | Instances (of 49,682 placed) | Largest fall between table points, of the instance's largest value |
|---|---|---|
| asap7 SS | 1,666 | 3.1% |
| asap7 FF | 15 | 6.8% |
| asap7_lvt FF | 1,666 | 0.2% |

The counts are `non_monotone_instances` in `record/audit.json`, over the instances that `sweep.load` matches to the
placement (`/b/asap7/asap7-ibex/inst_loc.csv`; two of the 49,684 power rows have no placement). The falls were
measured on 20 Nov from the placed rows of the G103 power tables (`gates/g103/runs/main/<kit>/<corner>/power/`).
They are exploratory and not in the record.

For these units the audit brackets the model with two monotone envelopes, evaluated on a grid that holds the
table temperatures (`audit.envelopes`):
- **Converged:** the upper envelope has an upper solution U at or below T_cap, so the real loop map sends
  [T_amb, U] into itself and an operating point exists (Brouwer). This proves existence only; it does not show
  that the loop settles there from ambient.
- **Runaway:** the lower envelope's iteration from ambient passes T_cap, so no operating point at or below T_cap
  exists.

All 12 windows of these units were decided this way, as expected (`envelope` in each probe).

## Limits

- **G101 sets.** The probes confirm only a bracket of about 2e-4 relative width around each recorded s*. G101's
  set rankings, ties and its sensitivity bar are not re-checked here.
- **Status only.** No amplification 1/(1 - rho) is computed at a fixed-point endpoint (Sol RF-4).
- **Envelope verdicts are existence only.** For the three corner units above, they do not say the loop settles at
  the operating point from ambient.

Review: Sol confirmed the bracket argument (RA-0) and the fixes for RA-1 and RA-3 before the record run. RA-2 was
only partly fixed; the remaining gap is stated under What was run. Two earlier attempts are kept beside the record
run `runs/record_v3`, but they are git-ignored and not in `record/`:
- `runs/main/audit.log`: stopped at asap7 SS on the refusal above, rc=1.
- `runs/main_v2/audit.log`: same verdicts as the record, before RA-1..3, rc=0.
