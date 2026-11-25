# G94: Do the three solvers agree in time, not only at steady state? (O1, RQ2/RQ3) · PASS (run 19-20 Nov 2026)

Registration: `registration.md` (19 Nov, before the gated run; Amendment 1 of 20 Nov, before any unit was scored).
Run: HotSpot units in two Kaggle sessions (`kaggle_gate_hs.py`, sessions `step` and `rest`), 3D-ICE and PACT units
locally (`bash gates/g94/run_local.sh 4g`, image `opentsense:g94b`), all into `runs/main/` (git-ignored); scored by
`python gates/g94/evaluate.py gates/g94/runs/main`. Record: `record/` (`result.json`, `manifest.json`, the two Kaggle
manifests and parity files).

## Verdict: PASS

Validity held (`result.json`: `valid` true): all 8 units of each solver present, 24 in all (`3d`, `25d_regions`,
`3d_bottom` x step and pulse, plus programs on `3d` and `3d_bottom`), every manifest with `settings.json` and seed 0, every unit
at level 5 with every die of its stack, the registered row counts at levels 5 and 6, and finite values (Amendment 1).
Both Kaggle sessions passed parity with this machine's outputs before their units ran (`record/parity_kaggle_*.json`).

| Bar | Needed | Result (`record/result.json`) |
|---|---|---|
| (a) last step row equals the solver's own steady solve, every stack | within 0.01 K | 9 of 9; largest 0.0062 K (`3d_bottom`, PACT) |
| (b) time to 63% of the final peak rise, every pair, per die | within max(3 x floor, 5% of the pair's mean) | 15 of 15; closest to its bar at 0.75 of it (`3d` step, top die, PACT-HotSpot: 0.149 ms apart, bar 0.1975 ms) |
| (c) peak rise for t > 5 ms, every pair, per die and case | within max(3 x floor, 0.5 K) | 42 of 42; closest to its bar 0.344 K against 0.5 K (`3d` programs, top die, 3D-ICE-PACT) |

Every pair also meets the bars' fixed parts alone: the largest (c) difference anywhere is 0.376 K (under 0.5 K), and
the largest (b) difference is 0.75 of 5% of the pair's mean. The floor term widened 15 of the 42 (c) bars (up to
2.25 K, from PACT's 0.75 K level 5-to-6 change on `3d_bottom` pulse, top die); none of them needed it.

## Reported, not gated (`record/result.json`)

| Pair | (c) largest after 5 ms | RMS after 5 ms, largest | first 5 ms, largest | (b) worst, fraction of bar |
|---|---|---|---|---|
| 3D-ICE - HotSpot | 0.009 K | 0.008 K | 0.001 K | 0.03 |
| 3D-ICE - PACT | 0.376 K | 0.251 K | 0.398 K | 0.73 |
| PACT - HotSpot | 0.376 K | 0.245 K | 0.398 K | 0.75 |

3D-ICE and HotSpot agree to 0.01 K: they share a discretisation here (G93a), so this checks the converters and
boundaries more than the physics (registration, *Not claimed*). The largest peak gap after 5 ms involving PACT is
0.376 K, about 41 times 3D-ICE-HotSpot's 0.009 K; in the first 5 ms PACT's gap reaches 0.398 K. This record does not
show the sign or cause of PACT's gaps (the 1-D dry check, `dry/one_d.txt`, compares source-layer means on another
stack). Level-5 solve times (`level_solve_s`: the transient at the unit's level and its reduction, plus for PACT the
steady run that captures its matrix; Amendment 1): 36,843 s over all 24 units, longest 5,879 s (`25d_regions` step,
HotSpot).

## What this means

At level 5 (5 ms slots split into 32 rows), the three solvers agree within the registered tolerances on what the bars
measure (the step's end, the 63% rise time, and each die's peak rise after 5 ms) for these cases on G93a's stacks.
The observed differences between PACT and the other two (up to 0.40 K peak, 0.25 K RMS after 5 ms) are what a later
time-domain result using PACT should report beside its own numbers; this gate does not establish that the solvers
are interchangeable for other observables (e.g. G79's sensor readings) or bound a model error.

Not claimed: stock HotSpot (fitting factor kept) or PACT's Xyce netlist path; other stacks, power maps or levels;
agreement with a measured chip.

## Limits of the record

- The manifests record no image digest. The local units ran in `opentsense:g94b`; `docker image inspect` after the
  run (20 Nov) gives ID `sha256:bc6e5483861a03dca64c1d1d85888e91faa30f1d04acb9906a87be772a8642c8`, created
  2026-11-16T22:13:49Z. The image holds the tools, not the gate's code.
- The source that ran is not pinned. Every manifest records a dirty checkout (`repo.dirty` true; local base commit
  `ce3765b`, the Kaggle sessions none). The local units ran the bind-mounted working tree (`run_local.sh`), and the
  Kaggle units a copy of the `opentsense-src` dataset (`kaggle_kernel.py`) whose version is not in the record. The
  Kaggle parity checks show their solvers matched this machine's outputs, not that the source bytes matched.
- The local units were relaunched at a 4 GB cap after 3d_bottom step PACT thrashed for 16 h at the 3 GB default
  (Amendment 1); `run_local.sh` now defaults to 4g.
