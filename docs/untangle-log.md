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
