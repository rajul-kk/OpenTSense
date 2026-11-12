# G84 registration (written 10 Nov 2026, after a dry run, before the gated run; bars fixed now)

### G84: Benchmark scorer: one command scores any estimator (O2) · REGISTERED

- **Why.** "Score any estimator with one command" is a proposal success criterion, and porting G76–G80 without a
  scorer would give each port its own scoring (`goals.md` O5). The metrics and aggregation follow the draft
  `../../../protocol.md` (sections 2–5).
- **What is built.**
  - `opentsense/bench/`: case-set format (`cases.py`), metrics and group bootstrap (`metrics.py`), estimator
    interface and entries (`estimators.py`), and the command `python -m opentsense.bench.score`.
  - Entries: `average` (training mean; the floor), `field_model` (`estimate/field_model.py`, temperature only),
    `bayes_power` (cross-die Bayes as G42/G73, power and temperature), and `inverted`, which is deliberately wrong
    (bayes_power with its update's sign flipped).
  - `make_cases.py`: a small frozen case set. It uses the G71 3D stack's own PACT matrix, with the TPU die on top and
    the CPU die buried. The CPU die runs G81b's 20 programs (20 segments each) and the TPU die runs G72's W1–W3. The
    set has 400 cases split by program into 240 train, 80 cal and 80 test, with 8 sensors per die and σ = 0.1 K. See
    the module docstring for every assumption.
- **Validity (v): plumbing.** G71's seed-0 power solved with the factorised G71 matrix equals G71's stored PACT
  fields within 0.005 K on both dies. PACT writes temperatures to 0.01 K, so 0.005 K is its rounding. If (v) fails,
  the gate is INCONCLUSIVE.
- **Noise floor (`plan.md` §2.1).** Measured in the dry run: two scorer runs on the same machine give identical
  results (unit test `test_scorer_is_deterministic`; floor 0). Across machines the floor is the floating-point
  difference between LAPACK builds, so bar (b) is an equivalence margin.
- **Pass if all hold:**
  - **(a) One command:** `run.sh` builds the case set and runs the scorer once on the host. It writes `result.json`,
    `per_case.npz` and `manifest.json`, with summaries for at least `average` and `field_model` on both dies.
  - **(b) Same numbers on a second machine:** the case set and the score are rebuilt inside the image
    `opentsense:g93a` (Linux, a different BLAS). Every per-case metric of every estimator agrees with the host run
    within 1e-6 absolute (K, µm or relative), and the two case sets' T arrays agree within 1e-6 K. Equivalence
    margin: max |difference| ≤ 1e-6.
  - **(c) A wrong estimator scores worse:** for both dies, the group-bootstrap 95% interval of `inverted` −
    `average` (mean over groups of the group-median RMSE, 10,000 resamples, seed 0) lies above 0.
- **Disclosed from the dry run (`dry/`, not scored).**
  - Feeding another case's readings was tried first as the wrong estimator. On a synthetic set it was not reliably
    worse than `average`, because a donor case can sit closer to the truth than the training mean. So the wrong
    entry is the inverted update.
  - Peak error is not monotone in field error: on the synthetic set, `inverted` beat `average` on peak error while
    losing on RMSE. Bar (c) is therefore stated on RMSE.
  - Dry-run numbers on this case set (test split, mean group-median peak error, top / buried die):
    - `average`: 6.28 / 5.15 K;
    - `field_model`: 0.25 / 0.10 K;
    - `bayes_power`: 2.29 / 0.45 K;
    - `inverted`: 16.1 / 12.0 K.
    These are disclosed because the bars were written after seeing them. Only (c) depends on such numbers.
- **Reported, not gated:** every estimator's summaries per die and per test tag, power errors, comparisons against
  `average`, and fit and predict times.
- **A fail means:**
  - (a) fails: the command or format is broken; fix it and re-register.
  - (b) fails: results depend on the machine beyond rounding; find the source before any estimator is ported.
  - (c) fails: the metric or aggregation cannot tell a wrong estimator from the floor; rethink the protocol metrics.
- **Not claimed:**
  - This case set is not the frozen benchmark of 15 Jan. It is one stack, steady state only, one sensor layout, and
    a CPU power from toggle shares rather than OpenSTA per window.
  - The `bayes_power` result reflects its bin-uniform power model on a concentrated TPU block. It does not rank the
    methods for the dissertation.
- **Code and output:** `make_cases.py` and `run.sh` here; scorer in `opentsense/bench/`; output in `runs/main/{host,image}/`.
