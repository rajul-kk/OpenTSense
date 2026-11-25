# Untangle log

Decisions from the untangle step (run in every review-and-commit loop), kept so they survive between sessions.

## Standing answers

| Question | Answer | Date |
|---|---|---|
| Extra passes beyond the core untangle (Comments, Tests, both, neither) | **Both**: comments are brought in line with the code (each says why, none restates what), and tests are checked for coverage of each module's contract, adding missing ones | 2026-11-12 |

## Goal 0, phase A (12 Nov 2026)

Scope: everything outside G92e's import closure. G92e's container mounts this repo and its resume imports
`stack/*`, `thermal/{run,response,electrothermal}`, `power/{leak,leaklib,maps}` and `manifest` live, so those wait
for phase B (`untangle-g92e` in tasks.json). Registered gate folders are frozen evidence: copies inside them never
change, so they are not hidden links. Live (unregistered) gates are in scope: g81e, g95.

Behaviour: after both rounds, 55 of 66 snapshot outputs are identical and 11 (interface energy per window) differ by
at most 1.3e-16 relative (summation order); the snapshot is of 66 outputs (DRAM traces and checks, energy windows, features and totals, every
benchmark estimator's scores, every placement method) taken before any change and compared after.

### Fixes, each above the problems it solves

- **One table of DRAM timing gaps** (`dramctl.gaps(spec)`, each gap named and derived once from the memspec, with
  its JEDEC/DRAMSys source), read by both the scheduler and the checker. The checker stays independent where it
  should be (its own state machine over the trace); the formulas exist once and are tested against DRAMSys
  CheckerLPDDR4's.
  - `power/dramctl.py:101,138,140` (scheduler) and `:201,204,213-215` (checker) each write every timing formula;
    the missing JEDEC clock on write recovery was in both, so the "independent" check could not catch it.
- **A trace carries the memspec it was scheduled with** (`Trace.spec`), so bank count and tRFCab come with it.
  - `power/dramenergy.py:94-95` imports LPDDR4-3200 for a default tRFCab: a trace scheduled with another spec gets
    the wrong refresh time silently.
  - `features`, `fit`, `windows`, `predict_totals` all take `nb` beside the trace; `tests/test_dramenergy.py:8`
    hard-codes 8 and `gates/g81e/dry/fit_energy.py:19` re-reads it from the spec.
  - `Trace.csv(spec)` takes the spec again.
- **One table of energy terms** (core terms per bank, interface terms per window), used by `fit`, `windows` and
  `predict_totals`.
  - `power/dramenergy.py:160-161` and `:176-177` write the core energy sum twice; `:167` and `:179` the interface
    sum twice; `:139` builds fit's interface columns in an order that must match `Model`'s fields by position.
- **The case set owns sensor indexing** (`CaseSet.flat_sensors`, also on `Public`; `has_R`).
  - `bench/cases.py:110`, `bench/estimators.py:167` and `:187` turn (die, row, col) into an index three ways.
  - `bench/estimators.py:180` reads `cs.a` (the case set's internals) to see whether R is present.
- **`regularise` says which rules need sigma; the registry is keyed by each entry's own name.**
  - `bench/estimators.py:266-268` lists the sigma rules by hand; `estimate/regularise.py:92` has its own list.
  - `estimators.py:236` (Tikhonov's name) and `:267` (its registry key) build the same string separately.
- **One placement entry point for every method, baselines included** (`placement.place`).
  - `estimate/ood_check.py:42-47` and `:90` dispatch methods with special cases for `uniform` and `random`, twice.
  - `ood_check.py:48-50` and `:91` build noisy readings and the posterior twice.
- **G95 checks its copy of G92e's case construction against G92e's record** (each window's nominal peak must
  match G92e's `peak_K`), so the copy cannot drift unnoticed. G92e's script runs at import, so it cannot be imported.
  - `gates/g95/sweep.py:34-55` copies G92e's case construction with nothing tying the two.
  - `sweep.py:63` (rtol 1e-4) and `:82` (2e-4 = 2 x rtol) hold one value twice.
- Special case kept as needed: `bench/estimators.py` `Inverted` exists for G84's bar (b) by design.
- Small: `gates/g81e/dry/fit_energy.py:41` checks trace legality with `assert` (skipped under `python -O`).

### Round 2 (search subagent, 15 findings)

Fixed:
- **The memspec copy is checked against the file DRAMPower reads** (`dramctl.memspec_mismatches`, called by
  G81e's dry script before fitting; today: no mismatch).
  - `power/dramctl.py:26-30` copies DRAMSys's JSON by hand; nothing compared the two.
- `estimate/ood_check.py`: `--loco` ignored `--methods`; the default method lists were written twice. Now one
  constant per mode, and `--keep-duplicates` with `--loco` is refused (leave-one-out always drops seen fields).
- `scripts/record_gate.py --parts`: a part folder without result.json was skipped silently; now reported missing.
- Unused, removed: `CaseSet.sensor_values`, `Stats.miss_rate`, `Level.part`, `Calibrator.n_cal`,
  `regularise.choose(tau)`, `regularise.oracle(weight)`.

Kept, with the reason:
| Finding | Why it stays |
|---|---|
| `tests/test_dramenergy.py` fit test builds DRAMPower-like outputs from `features` | a known-answer test of `fit`; `features` has its own hand-checked tests |
| 273.15 in `runaway.critical_scale_1tile` and `electrothermal` | the leakage tables' Celsius convention; `electrothermal` is in G92e's closure (phase B) |
| `power/workloads.py` literals (lanes, shifts, drain length, kernel 3 checksum) | fixed by the TPU and Ibex testbench RTL outside this repo |
| `power/dram.py:29-30` puts periphery on the top and right die edges only | G93a's registered result depends on this layout; noted as a limitation, not changed |
| `regularise` discrepancy falls back to the smallest lambda | G77 already reports how often a rule picks a grid end |
| `score.py` compares peak and RMSE only | protocol choice (protocol.md section 5) |
| traffic generator in two tests and the G81e dry script | test inputs, each tuned to its check; not product code |
| IC-ThermBench README case layout | a stated, labelled assumption ("unconfirmed") |

### Tests (done last)

- `tests/test_bench.py:91` re-derives BayesPower's formula line by line: it checks the code against a copy of
  itself. Remove; the scorer-ordering tests check its behaviour.

### Phase B, waiting for G92e (planned 12 Nov from a read of the files; nothing changed yet)

Fixes, each above the problems it solves:

- **The stack expands itself into solver sublayers** (`Stack.sublayers(from_sink_far_side)`, yielding layer,
  kind (bulk, source, plain) and thickness in solver order), and every converter iterates that.
  - `stack/to_pact.py:95-104` and `stack/to_hotspot.py:50-58` each write the sink-relative order and the die's
    source/bulk split; `stack/to_3dice.py:214-222` writes its own top-first variant. This is the hidden link
    codegraph found: `model.py`, `to_3dice.py`, `to_pact.py` and `thermal/run.py` changed together in 3 of 3 commits
    (n_sub, source_side and regions each had to be added to every converter).
- **`to_pact` owns PACT's grid layout** (one pair: our (die, row, col) <-> PACT's flat index), used by the reader,
  the right-hand side and the response operator.
  - PACT's row flip is written in `thermal/run.py:129` (`read_pact`), `thermal/response.py:193` (`rhs`), `:224`
    (`build`), `:244` (`_build_observed`, as `ny - 1 - i`), and in `gates/g84/make_cases.py` and
    `gates/g77/make_cases.py` (`[:, ::-1]`).
- **One factorisation** (`response.factor(A)`, PACT's SuperLU options in one place) and one batched solve, used by
  `build`, `_build_observed` and the case builders.
  - `thermal/response.py:205-213` repeats `_factor` (`:228-237`) inside `build`; G84's and G77's builders repeat the
    options; `:216-225` and `:246-250` repeat the batching loop.
- `stack/model.py` checks with `assert` (`validate`, `place`): skipped under `python -O`. Make them ValueError, as
  the case sets were on 11 Nov (goals.md).

Behaviour check for phase B: G71's stored 3D-ICE and PACT fields and G93a's three-solver fields must be
reproduced exactly from the same inputs (they are in runs/), plus the stack tests.

**Done 13 Nov, after G92e.**
- `Stack.sublayers()` (from the side away from the sink) drives `to_pact` and `to_hotspot`. `to_3dice` keeps its own
  form: 3D-ICE takes named die blocks top-first and states the sink side itself, so it has no flat sublayer list to share.
- `to_pact.rows` / `to_pact.cell` hold PACT's row order; `read_pact`, `response.rhs` and both operator modes use them.
- `response.SUPERLU`, one `_factor` and one batched `_solves` serve both operator modes. The full mode now also honours
  `dtype` (default float64, as before). The layout check raises RuntimeError instead of asserting.
- `stack/model.py` checks raise ValueError (`_need`).
- Not changed: G77's and G84's case builders keep their copies of the flip and the SuperLU options (frozen gate code).
- Check: every solver input G93a wrote (5 stacks x 4 seeds x 3 solvers, 1,368 files) regenerated byte for byte; the
  single-die stack re-solved in the image with all three solvers, difference 0; new against old `response.build` on
  G71's 3d stack, 70 patterns, full and observed: difference 0; all tests, including the 22 in-image solver tests, pass.
  (A full re-solve of the larger stacks was stopped: HotSpot needs more than the 2 GB the free RAM allowed.)

## 15 Nov: queued commits #63-67 (sdc.py, G96, G100, ood_check, G101), run late, before they landed

Fixed:
- `power/sdc.py`: a missing clause raised a bare AttributeError; an SDC with two port clocks was read as its first.
  One `_values` helper names the file and the clause; `half_ps` counts only clocks on a port (ORFS adds a virtual
  `vclk_*` of the same period) and refuses more than one. Same values on all 5 built layouts (450, 100, 455, 4, 700 ps).
- `estimate/ood_check.run_loco`: the fit hash set was built twice; built once.

Kept, with reasons:
- `ann[0] / (ann[0] + ann[1])` is copied in 7 gate evaluators (G72, G75, G81a/b/x, G96, G100): recorded gate code, so
  frozen; a `maps` helper only when a new gate needs it.
- G96/G100 `run.sh` share docker/OpenSTA helpers: recorded gate scripts, frozen. G96 `sim.py` builds the SDC path twice:
  same reason.
- `g101/run.py` swaps `runaway._rho`: it measures the unchanged `classify`; a parameter for one caller would couple
  worse. Goes if `electrothermal.rho` moves to power iteration (student's call).
- `g101` imports `g95/sweep`: G95 is recorded and frozen, so the dependency points at the more stable side.
- `ood_check.run_loco` filters the ID set's hashes against fit only, not calibration (the held-out set is filtered
  against both). Index-disjoint from calibration as the docstring says; a duplicate field shared by calibration and
  the ID set is a scientific choice, not a structural one, so not changed here.
- Note: #63 edited `gates/g72/sim.py` (recorded G72) to call `sdc.half_ps`; its values are unchanged (450 / 100 ps).

codegraph before and after: cycles 0, needless 0; the 8 hidden pairs are the stack model and its converters (phase B).

## #72 sdc.input_ps, decision 10 (16 Nov)
- One module reads the SDC once (`_read`) and parses each command strictly (`_commands`); half_ps and input_ps share it.
- Kept: `gates/g96/sim.py` calls half_ps and input_ps separately on the same path (frozen G96 file).
- Nothing else to untangle: two callers (g72/sim.py, g96/sim.py), no hidden links.

## rho on overflow (c6 v2 classify fix, 20 Nov)
- The overflow guard lives in `electrothermal.rho` only (inf where the difference stencil overflows, ValueError on
  non-finite T or R); `runaway.classify` needs no branch of its own, since `rho >= 1` already means runaway, and it
  does no extra leakage evaluation.
- Kept: `gates/g101/run.py`'s `Recorder` copies rho's body without the guard; it is a recorded gate's timing harness
  (eigvals against the Perron bracket), so it is left as recorded. A rerun of G101 would need it to call `et.rho`.
- A duplicate test name in `tests/test_runaway.py` hid one test; renamed, so that test runs again.

## G94 (20 Nov 2026): one pass for the gate, after its run (PASS) and before its commits

Scope: `gates/g94/{cases,solve,run,evaluate,kaggle_gate_hs,kaggle_kernel}.py`, `run_local.sh`,
`tests/test_g94_evaluate.py`, `scripts/record_gate.py`. Nothing outside `gates/g94` imports its modules (grep).
Rule for this pass (A14): the files that produced the recorded units (`cases.py`, `solve.py`, `run.py`,
`kaggle_gate_hs.py`, `kaggle_kernel.py`, `dry/*`) stay as they ran; their problems are logged for whoever reuses
them. The scorer is re-run, and must give a byte-identical `result.json`.

- Split `evaluate.main`'s single loop (bars b and c, floors, first 5 ms, RMS, all inline) into `trajectories` (bar c
  for one pair on one die) and `time_constants` (bar b), each taking (level, series, finer series) per solver, so a
  bar's rule changes in one function. Done; `result.json` sha256 c69fd72c... before and after; behaviour tests
  added after Sol's last review (G94-LR-4): a 0.6 K gap in the first 5 ms passes c and shows in first_5ms, the
  same gap later fails; the floor widens c's bar; t63 2% apart passes b and 40% fails; string or nested series are
  refused (`problem` now checks 1-D numeric rows, LR-5; result.json still c69fd72c...).
  - `evaluate.py:main` computed the floor, the late-time mask, bar c and bar b for each pair in one 30-line loop body.
  - No test exercised a bar: `tests/test_g94_evaluate.py` covered validity (`problem`) only.
- Frozen as run, for a successor that reuses this code (G79 will name a solver from G94):
  - `cases.py`: G71's `maps.npz` path is built in both `maps()` and `programs()`; `programs()` defaults
    `stack_name="3d"` though every caller passes it; `CPU_BLOCK_W` and the 0.4 W dark power are copies of G84's
    values (G84 frozen, so a copy, commented, rather than a cross-gate import).
  - `run.py` / `evaluate.py`: the unit schema (`series`, `series_finer`, `wall_s`, `steady_end_diff_K`) is written in
    `run.unit` and checked in `evaluate.problem`; both sit in this folder, so the link is local but unnamed.
  - `run.py`, `evaluate.py`: importing them edits `sys.path` and needs the repo root as cwd (the test fixture
    `chdir`s); `settings()` reads relative paths.
  - `kaggle_gate_hs.py`: correct only if `run` is imported before `kaggle_floor_hs` (which puts `gates/g93`, with its
    own `run.py`, first on the path) - an import order callers must know.
  - `solve.py` belongs in the package (A6) if G79 or a later gate runs these transients: move it then, with A24.
  - Old ruff findings in these files (unused `noqa`, import order, open() without a context manager): left as run.
- `scripts/record_gate.py`, `run_local.sh`: nothing to change (the 4g default is Amendment 1's).
- Comments/Tests passes: the comments in `evaluate.py` state outside facts (Amendment 1, run.py's clock); none
  removed. Tests: all 9 check behaviour a regression would break; none removed.

## runaway-fix (20 Nov 2026): certified verdicts (C6-3, RF-1..6)

- Every verdict now comes with what proves it: "converged" needs an upper solution at or below T_cap
  (`upper_solution`), "runaway" a monotone lower iterate past T_cap (`lowest_fixed_point`); anything else is
  not_converged. One operator rule (`operator`: round-off negatives projected once) is used by both solves, so the
  Newton and fixed-point paths can no longer disagree about which R they classify.
  - Newton's runaway exits assumed leakage convex in T (false for Liberty tables): C6-3.
  - A small Picard step was taken as existence (also happens just past the fold): RF-1.
  - The post-Picard central-difference rho decided stability (misreads a point just below the fold): RF-1 round 1.
  - Signed R broke the lower-iterate proof: RF-3.
  - The Newton converged exit accepted points above T_cap while Picard counted them runaway: review finding 2.
- `classify`'s inner helper renamed `runaway` -> `by_fixed_point` (it decides by fixed-point iteration; the old name
  shadowed the module's own name for readers).
- Left, logged: `lowest_fixed_point` repeats `electrothermal.solve`'s loop. `solve`'s divergence rule (step > 1e4 K)
  and tol produced recorded results (G74, G95 sweep's picard_diff_K), so they stay apart; merge only with an
  equivalence check on those records (A15).
- Declined with a stated limit (docstring): RF-5/RF-6, rounding of H beyond the matrix product (~1e-13 relative on
  constructed inputs; rtol is 1e-4).
- Before/after on real data: the synthetic 1,024-tile SVT case gives the same bracket [482.251, 482.277] with and
  without the change; the recorded gates' cases are the runaway-audit task.

## Runaway audit (20 Nov 2026): gates/runaway_audit/{audit.py,run.sh}

**Kept: G95's case construction is loaded from `gates/g95/sweep.py` (by file, as G103's margin.py does)**, not
copied, so the audit's R and cases are the gates' own; TT units are checked against G92e's recorded peaks.
**Kept: the kit table (placement, stack) repeats `gates/g95/run_sweep.sh`**: G95 is recorded and frozen, and the
audit hashes the stack file per unit, so a drift shows as an input mismatch.
**Kept in the audit, not moved to `runaway`: the monotone envelopes for non-monotone tables.** One consumer; the
package's classifier keeps refusing such tables. Move it into `runaway` (with the Brouwer/induction argument and a
test) the first time a gate needs a verdict on a non-monotone model.
**Changed before the record run (Sol RA-1..3):** a failed re-bracket is recorded instead of raised; a kept unit is
reused only if its hashed inputs match; "complete" needs all nine units.
**Tests:** `tests/test_runaway_audit.py` checks the envelopes off-grid on random non-monotone tables; the audit is the
check of the recorded gates.
