# G94 registration (written 19 Nov 2026, after the dry runs, before the gated run)

The history is in `draft.md`: the transient paths (16 Nov), the student's choices (A "three discretisations", bars
pairwise throughout, bar (c) after the first 5 ms with floor rule 0.2 K and level 5), the time-step correction and the
dry runs. Terms the student left open were delegated on 18 Nov ("no questions just do what youd recommend as id pick
that option either way") and are marked *(delegated)*.

### G94: Do the three solvers agree in time, not only at steady state? (O1, RQ2/RQ3) · REGISTERED

- **Why.** Steady fields agree within 0.41 K across the three solvers (G93a). G79 (Kalman with an identified plant),
  recovery in time, the transient leakage loop and any governor study rest on transient truth.
- **What is compared.** Three discretisations (student, 16 Nov): 3D-ICE 4.0 as shipped; HotSpot 7 with its
  capacitance fitting factor undone (`to_hotspot`); PACT's conductance network integrated by our backward Euler
  (`run.pact_transient`). Every solver gets the same rows (`solve.py`): each 5 ms slot split into 2^L rows, one step
  per row.
- **Cases** (`cases.py`, **seed 0**; every dry run used seed 1): G93a's stacks `3d`, `25d_regions`, `3d_bottom`, G71's
  maps of the seed:
  1. step: on at t = 0, held 156 slots (0.78 s, 10 slowest time constants: 3d_bottom's 78 ms,
     `dry/time_constants.json`);
  2. pulse: on for 2 slots (10 ms), then off, 40 slots;
  3. programs (stacks with a CPU die, `3d` and `3d_bottom`): the 19 G81b programs in a seeded order, 4 slots each,
     at G84's power construction; the TPU die holds its map.
- **Level and floor.** Level 5 for every solver (`settings.json`): the change of the peak rise from level 4 to 5 after
  5 ms is at most 0.186 K on every die and stack (`dry/floor_after/floor.jsonl`; rule: at most 0.2 K). In the gated
  run each unit is also solved at level 6; a solver's floor on a quantity is its change from level 5 to 6 over the
  same times, and a pair's floor is the larger of its two.
- **Pass if all hold:**
  - **(a) Steady end:** every solver's last step row equals its own steady solve within 0.01 K, every stack.
  - **(b) Time constants:** per die, the time to 63% of the step's final peak rise agrees between every solver pair
    within max(3 x floor, 5% of the pair's mean) *(5%: delegated, the draft's proposal)*.
  - **(c) Trajectories:** per die and case, the largest difference of the peak rise between every solver pair over
    t > 5 ms is within max(3 x floor, 0.5 K) (student, 17 Nov). The first 5 ms are reported, not gated.
- **Validity (INCONCLUSIVE otherwise).** Every unit of every solver is present; every manifest in the run directory
  (one per machine: this one and each Kaggle session) holds `settings.json` and seed 0; every unit ran at its
  solver's level and holds only finite values.
  Kaggle units run only after parity with this machine's opentsense:g94b outputs (`kaggle_gate_hs.py`: HotSpot
  transient at levels 0, 2 and 5 and 3D-ICE at level 4: temperatures within 0.01 K, t63 within 1e-3 relative).
- **Reported, not gated** (`result.json`). The first 5 ms difference per pair; RMS difference over t > 5 ms; wall
  time per unit; each solver's floor per die and case.
- **A fail means.** Transient truth depends on the solver at this resolution: G79 and any time-domain result names
  its solver and carries the measured disagreement as a model error (G87).
- **Not claimed.** Stock HotSpot (fitting factor kept) and PACT's Xyce netlist path are not run; HotSpot and 3D-ICE
  share a discretisation here (G93a), so their agreement checks converters and boundaries more than physics.

### Known before registration

- HotSpot's transient dump is streamed through stdout since 19 Nov (it holds every layer at every row, tens of GB
  at level 6), checked equal to the file path's saved outputs (`dry/stream_check/`).
- Small plumbing stack, same rows for all (`draft.md`): HotSpot's row-end peaks equal 3D-ICE's to 1e-4 K.
- 1-D check (`dry/one_d.txt`): PACT reads 15% low at 1 ms and 5% low at 12 ms against a fine reference; 3D-ICE within
  2%. PACT ends 0.18 K below the others at steady on the small stack; G93a's steady spread is up to 0.41 K, so bar (c)'s
  0.5 K leaves PACT little room.
- Floors, seed 1, step case (`dry/floor_after/floor.jsonl`): level 4 to 5 after 5 ms, 3D-ICE / PACT / HotSpot,
  0.185 / 0.186 / 0.185 K (3d stack, bot die) and at most 0.106 K elsewhere; t63 change up to 4.6% (25d_regions).

### Code and output

`cases.py`, `solve.py`, `run.py` (one unit per stack, case and solver), `evaluate.py` (bars, validity,
`<run dir>/result.json`), `settings.json`. HotSpot units: `kaggle_gate_hs.py` in two Kaggle sessions (`step`, `rest`;
kernel file `kaggle_kernel.py`), copied into `runs/main/` with their manifests renamed `manifest_kaggle_<session>.json`.
3D-ICE and PACT units: `bash gates/g94/run_local.sh` (opentsense:g94b) into `runs/main/`. Then
`python gates/g94/evaluate.py gates/g94/runs/main` and `python scripts/record_gate.py g94`.

Lints checked: A4 (one population: G93a's stacks, G71's seed-0 maps), A9 (settings in one file, read by the runner
and the evaluator through the manifest), A16/A17 (one unit per file, written whole; reruns skip finished units), A18
(Kaggle parity first), A25 (every number above cites its file).

Amendments go below, dated, each with the reason. Never re-run until it passes.


### Amendment 1 (20 Nov 2026, before any unit was scored; 19 of 24 units in, none read by the scorer)

Reason: a second, independent review found that `evaluate.py` took each case's dies from the first solver's unit
and never checked row counts or `wall_s`; with one die removed from all three units of a case it still returned
PASS on fewer comparisons. The registered validity rule already requires every unit present and finite; this makes
the scorer check it in full. No bar, tolerance, case or level changes.
- Validity also requires: every unit holds every die of its stack (`cases.STACKS`), n_slots x 2^level rows at its
  level and twice that one level finer, for both peak and mean, and a finite `wall_s` (plus `steady_end_diff_K` for
  step units), as numbers. Otherwise INCONCLUSIVE with the reason (`evaluate.problem`,
  `tests/test_g94_evaluate.py`). Row counts come from `settings.json` and G81b's tracked record (`cases.n_slots`),
  so a complete unit set can be scored without G81b's timelines.
- "Wall time per unit" under *Reported* is the transient at the unit's level and its reduction to peak and mean
  series (for PACT this includes the steady run that captures its matrix); `run.py` reads the clock before the
  level + 1 solve, the steady solve and the writes. `result.json` names it `level_solve_s`.
- The record also keeps `manifest_kaggle_step.json`, `manifest_kaggle_rest.json` and the two Kaggle parity files
  (`parity_kaggle_step.json`, `parity_kaggle_rest.json`) (`scripts/record_gate.py`).
- The local units were relaunched with a 4 GB cap (`bash gates/g94/run_local.sh 4g`): 3d_bottom step PACT thrashed
  for 16 h at the 3 GB default (peak 3.17 GB). The manifests record no image digest and the local checkout was
  dirty; the README states the image (`opentsense:g94b`) digest read after the run and this limit.
