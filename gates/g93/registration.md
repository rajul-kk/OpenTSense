# G93 registration (written 18 Nov 2026, before the gated run)

The history before this is in `draft.md`. The student delegated the choices left open there (18 Nov: "no questions
just do what youd recommend as id pick that option either way"); each one taken under that delegation is marked
*(delegated)*.

### G93: Do the three solvers still agree on stacks at consumer area and power? (O1/RQ1) · REGISTERED

- **Why.** G93a showed 3D-ICE, HotSpot and PACT agree on 3 x 3 mm dies at 6 to 8 W. Lateral spreading changes with
  die size, and a buried die under a large hot die is the case the testbed is for, so the agreement has to be shown
  again at consumer area and power before the benchmark uses these stacks.
- **Stacks.** S1 cache-on-logic, S2 HBM-style (base plus 8 DRAM dies), S3 2.5D accelerator (logic beside four S2
  stacks on an interposer), S4 3-tier buried die, as built by `stacks.build(name, 500)` (`stacks.py`; figures and
  sources in `draft.md`): BEOL on every die's source face, lid and cooler (`stacks.PACKAGE`), interface layers
  (`stacks.INTERFACES`), k(T) of silicon with exponent 1.3.
- **Cell.** 500 um *(delegated)*: the largest tried size that ran S1, S2 and S4 on this machine under a 3 GB cap
  (lidded stacks before BEOL was added, `dry/size_probe_lid.jsonl`); S3 is 391,406 nodes.
- **Leakage** *(delegated, draft "Leakage in the gated stacks")*. Each cell's nominal power is its power at 85 C, of
  which 10% is leakage on our ASAP7 LVT curve (`stacks.LEAK_CURVE`); k(T) and leakage settle together in
  `thermal.run.solve_kT` (tolerance 0.01 K, at most 40 solves), the same loop for all three solvers. One k per layer:
  in S3 the `hbase` layer holds the logic die and the four HBM base dies, and its silicon k is taken at the mean
  temperature over all five.
- **Solvers and where it runs.** All three solvers built on Kaggle CPU sessions as `opentsense:g94b` has them
  (`kaggle_build.py`: HotSpot f18831e with the dump and lu-reuse patches, 3D-ICE and PACT with their patches;
  versions from `docker/versions.env`). HotSpot needs 25.55 GB on S3; on S1 and S4 it peaked at 2.52 and 2.72 GB
  before BEOL (`dry/size_probe_lid.jsonl`; not measured with BEOL here), which needs this machine's 4 GB heavy slot,
  and the machine sat at about 4.3 to 5 GB free on 18 Nov with G94's HotSpot pass waiting for that slot. So every
  stack runs on Kaggle. Session A: S2, S4, S1 (each solver), then S3 3D-ICE and PACT.
  Session B: S3 HotSpot alone (4,483 s a solve, `dry/size_probe_kaggle_beol.jsonl`).
- **Parity first (A18).** Each session first runs `dry/floor.py` on S2 at 500 um in every solver and compares with
  this machine's image units (`dry/floor_image/`) by `dry/floor_summary.py`'s rule: all three present, the same
  `inputs` hash, each die's peak and spread within 0.1%. A miss stops that session before any gated unit. The floor
  session passed this check with differences of 0.0 (`dry/floor_kaggle/parity.json`). Both sessions' units carry
  `image` "kaggle-build"; S3's HotSpot pairs join a unit of each session, and what ties the two builds is that each
  passed parity against the same image units.
- **Noise floor (plan.md 2.1).** The solvers are deterministic: a repeat run gives the same answer (G93a part (a) to
  1e-9 K; the Kaggle build matched the image to 0.0 above), so the repeat spread is zero. The floor that limits a
  comparison is each solver's mesh error at 500 um, measured as f = the change of its peak rise (and spread) when
  every cell is split in four, relative to the 500 um value, per stack, die and solver (`dry/floor.py`,
  `dry/floor_kaggle/floor_summary.json`, Kaggle session of 18 Nov, all 18 units, one linear solve at 85 C k and
  nominal power). Largest f per stack:

| Stack | f, peak rise | f, spread |
|---|---|---|
| S1 | 0.18% | 0.11% |
| S2 | 0.23% | 0.32% |
| S4 | 0.28% | 0.40% |
| S3 (not measured: 1.5 M nodes refined) | per solver, the largest over S1, S2, S4: 0.26 / 0.28 / 0.26% (3D-ICE / HotSpot / PACT) | 0.40 / 0.40 / 0.38% |

- **Pass if all hold, for every stack, die (S3: each powered region, 37 of them) and solver pair:**
  - **(a) Peak.** |peak_a - peak_b| <= max(2 (f_a + f_b), 1%) x the pair's mean peak rise.
  - **(b) Spread.** The same rule for the spread (peak minus coolest cell of the die's powered silicon).
  - **(c) RMS.** The RMS of the difference of the two rise maps over the die's powered silicon <= 2% of the pair's
    mean rise there (G93a's RMS bar).
  - The bars of (a) and (b) are in `dry/bars.json` (`dry/bars.py`): 1.00% except these (ice-hs / ice-pact / hs-pact,
    1.00% where not named): S2 d0 spread 1.26 / 1.04 / 1.03%; S2 d2 spread ice-pact 1.07%, hs-pact 1.06%; S4 top
    peak 1.07 / 1.04 / 1.08%; S4 top spread 1.59 / 1.57 / 1.56%; S4 mid peak ice-pact 1.02%; S4 bot spread ice-hs
    1.05%, hs-pact 1.08%; S3 (every region) peak 1.07 / 1.04 / 1.08% and spread 1.59 / 1.57 / 1.56%.
  - **How they meet plan.md 2.1.** They are equivalence margins of route (ii); the test is the direct comparison, as
    both answers are deterministic. Why 2 (f_a + f_b) *(delegated, fixed in `draft.md` before any solver was
    compared)*: a halving moves an error that goes as h^2 by 0.75 of it and one that goes as h by 0.5, so a solver's
    500 um error is at most about 2 f, and two solvers erring in opposite directions differ by at most 2 (f_a + f_b).
    1% keeps a solver whose answer does not move from setting a zero bar. No bar is tighter than the floor of the
    difference (f_a + f_b, at most 0.80%).
  - Buried dies (S1 ccd, S2 base, S4 mid) are gated by the same rule and reported separately.
- **Validity.** A pair is INCONCLUSIVE, not FAIL, when a unit is missing (a session ran out of time or memory, a
  tool failed, the unit reached its time budget, its `inputs` differ from the evaluating code, its regions differ
  from the evaluating code's, or its maps are unreadable), when its two units carry different `image`, or when
  neither loop settled. Each unit's budget in `kaggle_run.py` is 1.5 x 40 of its measured solve times, or the
  session's time left if less, so a loop still moving after 40 solves is reached on S1, S2 and S4; on S3 the session
  limit comes first. One solver settling and the other not (ran away, or still moving after 40 solves) is a FAIL of
  that pair. S3 HotSpot: the build, solver tests and parity took about 4 min on the floor session, leaving about
  41,000 s, so up to 9 solves (40,347 s) fit with about 11 min spare; the solves S3 needs are not measured (S2 and
  S4 took 4, S1 9). If it does not finish, S3's two HotSpot pairs are INCONCLUSIVE, so the gate can at best be
  INCONCLUSIVE; any FAIL elsewhere still decides. Verdict: FAIL if any pair fails, else INCONCLUSIVE if any is, else
  PASS.
- **Reported, not gated.** Solves to settle, total power over nominal, the largest cell-to-cell gradient, wall time
  per unit; each pair's three ratios against their bars.
- **A fail means.** The solvers' agreement at 3 x 3 mm does not carry to that stack at consumer size; the report
  names the pair, stack and die, and the benchmark keeps to the stacks that passed (as the draft says).
- **Not claimed.** Accuracy against a measured or finite-element reference; the through-thickness mesh (the floor
  splits cells sideways only and keeps G93a's sublayers); transient behaviour (G94); a per-cell k (one k per layer);
  the leakage share itself (ASSUMED, swept in `sens/leak_runs/`).
- **Code and output.** `run.py` (one unit), `evaluate.py` (verdict, the reported fields and the buried dies apart,
  `manifest.json`), `kaggle_kernel.py` (the kernel file; its `UNITS` set per session), `kaggle_run.py` and
  `kaggle_build.py` (the sessions); outputs of both sessions copied to `runs/main/`, then
  `python gates/g93/evaluate.py gates/g93/runs/main gates/g93/runs/main/result.json` and
  `python scripts/record_gate.py g93`.

### Seen before registration (declared)

- 16 Nov, S1 at 500 um, uniform-in-block power, no leakage, in all three solvers: peaks 59.22 / 58.86 / 59.04 K (CCD)
  and 55.34 / 54.98 / 55.18 K (L3D), 3D-ICE / HotSpot / PACT (draft, "Interface resistances").
- 18 Nov, the design review of the floor opened S2's base die on the gated mesh (one linear solve at 85 C k, nominal
  power): 40.701 / 40.700 / 40.680 K (`dry/floor_image_v0/`).
- 18 Nov, while checking the format of the Kaggle floor units, S1's L3D on the gated mesh (same linear solve):
  62.34 / 62.57 / 62.27 K (HotSpot / 3D-ICE / PACT; `dry/floor_kaggle/floor/s1_x1_*.json`). The bar was fixed by
  the rule in `draft.md` before this, and the numbers in `dry/bars.json` follow from the floor only.
- The floor units on disk (`dry/floor_kaggle/floor/`, `dry/floor_image/`) hold every solver's absolute linear-solve
  peaks on S1, S2 and S4; they are not the gated (loop-settled) numbers and are committed after this registration
  (`dry/floor_image*/` is no longer ignored, as the parity reference has to be in the repo).
- 18 Nov, a smoke run of `run.py` on S2 in 3D-ICE only (`runs/smoke/`, ignored), to check the unit against
  `sens/leak_runs/s2_500um_leak0.1.json`; no second solver.
- Earlier 3D-ICE-only sensitivities on these stacks (`sens/`) are listed in `draft.md`.

Lints checked: A4 (one population: every pair on the same stack build, cell and power), A9 (bars from one file,
`dry/bars.json`; cell from `floor.CELL_UM`), A10 (cost from measured solve times and loop counts), A11 (Kaggle sessions
detached, own time limits), A14 (outputs append-only, floor units kept as run), A16 (one unit per file, a failed unit
does not stop the rest), A17 (units skip on equal inputs and image), A18 (parity first in each session), A25 (every
number cites its file).

Amendments go below, dated, each with the reason. Never re-run until it passes.

## Amendment 1 (18 Nov 2026, the student's decision; before any gated output was read)

- **Change.** S3 is compared in 3D-ICE and PACT only; its HotSpot unit is dropped (the student: "forget S3
  hotspot"). Session B (`opentsense-g93-run-b`, S3 HotSpot alone) was stopped by deleting the kernel about
  40 min after it started. It had written its parity units (S2, `dry/floor.py`) but no gated unit, and nothing from it was read. `evaluate.py` forms S3's pairs from
  `GATED["s3"] = ("ice", "pact")`.
- **Why.** One HotSpot solve on S3 takes 4,483 s and 25.55 GB, and 9 solves would only just fit in a session, so S3's
  HotSpot pairs risked leaving the whole gate INCONCLUSIVE. HotSpot is still compared on S1, S2 and S4.
- **What it changes.** S3 has one pair, 3D-ICE against PACT, gated by its bar in `dry/bars.json` (unchanged: peak
  1.04%, spread 1.57%); S3's ice-hs and hs-pact bars are no longer used. No longer apply: the question's "three
  solvers" for S3, session B in "Solvers and where it runs", the sentence on S3's HotSpot pairs joining both
  sessions' builds (under "Parity first"), and the S3 HotSpot budget under "Validity". No other bar, stack or
  pair changes, and the verdict rule is unchanged.
- **Known risk, not changed.** Session A was already running when this was decided: S3 3D-ICE runs before S3 PACT
  and may take most of the session's time left. If S3 PACT is then missing or out of time, only that unit is run
  in a new session (completing a missing unit, not a re-run of a finished one) and recorded as Amendment 2.
