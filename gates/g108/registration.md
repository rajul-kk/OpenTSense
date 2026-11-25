# G108 · Buried-die sensor budget with an active-block keep-out

Decision 16 in [goals.md](../../../goals.md) fixes the contrast, bars and held-out chips.

**Question.** With the top die's sensors fixed, do two outside-uniform buried-die sites increase
whole-die field-model temperature RMSE by at most 0.25 K relative to eight outside-uniform sites?
Ask separately for each sensor offset model.

## Cases and comparisons

- Use [G84's existing case set](../g84/dry/cases.npz) and its original program-group train/cal/test splits.
  Its `CaseSet.sha256()` is `f5941ad74a0d62f256c052607607be24985eaaa3c43fffe3fa10514a677f6e7c`.
  Keep G84's eight top-die sites in every arm. The buried die is the CPU.
- The eight arms cross two and eight buried sites with unrestricted uniform, outside-uniform,
  unrestricted A-optimal greedy and outside A-optimal greedy. Eligibility follows [G104's mask](../g104/dry/sites.py),
  based on the rectangle enclosing the active CPU map and expanded by two cells. Both greedy placements
  use the same G107 train-only placement noise and start from the fixed top sites.
- Reproduce the placement, ordered union and placement noise in the [frozen dry record](dry/keepout.json),
  whose file SHA-256 is `33e9c84efa9ecea22697afc81ce3841ba4bf4236120620c0bc1911cf098d02b5`.
  For each held-out chip and offset model, draw `ring_osc` readings once on the union with salt **107**.
  Each arm selects its own columns. Use independent offsets and correlated offsets with shared fraction 0.8
  and length 3 mm, as in [G107](../g107/registration.md). Score **chip seeds 31–40**. G108 dry seeds 1–5
  and G107's 21–30 are disjoint from this set.
- Fit the field model once on train temperature fields. Use `bench.score` on the test split and average
  the per-program median RMSE for each die. Subtract the eight-site RMSE from the two-site RMSE within each
  chip, then average the ten differences separately for each offset model.

## Bars and validity

| Bar | Buried-die paired mean RMSE difference | Pass |
|---|---|---|
| (a) Independent offsets | Two outside-uniform sites minus eight outside-uniform sites | ≤ +0.25 K |
| (b) Correlated offsets (0.8, 3 mm) | Two outside-uniform sites minus eight outside-uniform sites | ≤ +0.25 K |

Both bars must pass. Report each sample standard error across the paired chip differences.

**INCONCLUSIVE** if the case fingerprint or split/grid metadata changes, the dry placement, ordered union
or placement noise differs, or a site falls outside the grid. Each arm must keep the fixed eight top sites
and its named number of distinct buried sites. The evaluator checks outside-arm eligibility against the
original active-block map. Require exactly the registered chips, offsets, salt, profile and arm set, with finite
metrics on both dies and complete bootstrap comparisons. Require current input hashes equal to the run's
record, the dry record's Python/NumPy/SciPy versions and `OPENBLAS_NUM_THREADS`, the matching manifest, `complete` and
`inputs_unchanged`, and a successful launcher log ending with an `rc=0` line and the hash of the score file
immediately above it. The evaluator derives both bars from individual unit scores. A complete valid record with either bar exceeded is **FAIL**.

## Reported with the verdict

- Report the by-chip deltas, means and standard errors on both dies for all eight named contrasts.
  These include the outside-minus-unrestricted uniform and greedy contrasts at matched budgets, the other
  two-vs-eight contrasts, and the bridge from two outside-uniform sites to eight unrestricted uniform sites.
  Also report per-arm RMSE and peak error for both estimators, group-bootstrap comparisons against the average,
  and site layouts and keep-out overlap.
- The dry buried-die primary deltas were +0.042 ± 0.054 K for independent offsets and −0.027 ± 0.126 K for
  correlated offsets (mean ± SE). The largest individual dry deltas were +0.225 K and +0.242 K, respectively.
  The two uniform two-site layouts coincide. The keep-out changes the eight-site reference, so the primary
  test compares feasible budgets. The same-budget contrasts measure the keep-out effect.
  See `summary.*.bot.paired_rmse_K.outside_uniform_2_vs_8` and `placement.sites` in the [dry record](dry/keepout.json).
- A failed bar means the two-site outside-uniform layout exceeds the budget under that offset model on these
  cases. The scope is one stack, steady state, one sensor profile and whole-die RMSE. The active-block keep-out
  is a map-derived proxy for the routing constraint.

## Execution

From the repository root after registration, use the [Windows launcher](dry/launch.ps1). After the successful
launch, use the [evaluator](evaluate.py) on that run directory.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File gates/g108/dry/launch.ps1 -Scope gated -RunId main -RamGiB 2.4 -Minutes 10
python -B gates/g108/evaluate.py gates/g108/runs/main
```

The launcher holds a medium slot and starts [run.py](run.py) with the named output directory. It saves a
unique `launch.*.log` per attempt. The runner verifies the already-built G84 case set and pins the dry input
files used for scoring, with the scorer pinned at the version the A15 rerun used (`keepout.py` sha256
`f7bbe5ed...`, [dry/a15/keepout.json](dry/a15/keepout.json)). The runner refuses to start unless Python, NumPy,
SciPy and `OPENBLAS_NUM_THREADS` equal the dry record's; the evaluator requires the same, recomputes both bars
from the per-unit scores, and writes its own sha256 into every `result.json`. The runner writes `manifest.json`
and atomically checkpoints `scores.json` after each offset/chip unit. `manifest.json` and `result.json` are the
two files consumed by [record_gate.py](../../scripts/record_gate.py).

Resume an incomplete run with the same ID and inputs. If an interrupted attempt left a `scores.lock` directory,
confirm its process has exited before removing the stale lock. A complete score file is sealed against reuse by
another launch. If the final launcher check fails after the score file completes, keep that record and use a new ID.

The original ten-unit dry used 48.2 s and its process peak working set was 2.06 GiB
([dry resource record](dry/README.md), `wall_s` and `peak_working_set_bytes` in [keepout.json](dry/keepout.json)).
The gated run scores twenty units serially and uses the same-size fit once. The slot limits in the command are
resource reservations.

## Lints checked

| Lint | Application |
|---|---|
| A1, A2, A4, A5, L29, L75 | Check explicit arm, die, offset and chip coverage. Carry ordered site identities through a single per-unit reading draw and paired differences. |
| A3, A22, A23 | Reuse the fingerprinted G84 grid, split and units. Independently check site bounds and G104 mask eligibility. |
| A6, A7, A8, A9, A24 | Reuse one scorer, one layout builder and the existing G104/G107 helpers. Imports do not launch a run. The existing cross-gate helpers remain explicit input dependencies. |
| A10, A11, L11, L41, L79 | Budget from the full dry measurements. Use a hidden launcher with a watchdog, a checked medium slot and the Windows launcher PID. Record process working set. |
| A14, A16, A17, L67, L77 | Fail closed on missing evidence. Use separate dry and gated records, a per-run lock, hash-bound checkpoint resume, a positive end marker, and a launcher receipt bound to `scores.json`. Supply the recorder's result and manifest. Input checks occur at checkpoint boundaries. |
| A15 | A five-chip rerun with the updated scorer ([dry/a15](dry/a15/keepout.json), [log](dry/a15/keepout.log)) reproduced the frozen placement, every unit score and the summary of [keepout.json](dry/keepout.json); a test checks the pin against it. |
| A25, L76 | Cite the dry record for measured numbers. Exercise both bars at the evaluator with a passing case and one-chip changes that drive each mean above its threshold. |
