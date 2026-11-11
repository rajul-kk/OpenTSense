# Gates

One folder per gate (G70 onwards). The rules for registering and running a gate are in `../../plan.md` section 2.1.

## What a gate folder holds

| State | Files | Checked by |
|---|---|---|
| Draft | `draft.md` | nothing |
| Registered, not run | `registration.md`, scripts, `run.sh` | nothing |
| Run | the above, plus `README.md` (verdict and notes) and `record/result.json` + `record/manifest.json` | `tests/test_gate_records.py` |

- `runs/` is git-ignored bulk output. After a run, copy the two small verdict files into `record/`:
  `python scripts/record_gate.py gNN` (options: `--run a b` for several runs, `--parts` for one sub-folder per kit).
- A gate with several parts keeps one pair per part, for example `record/asap7/` and `record/ihp/`.
- G70 carries its registration in its README; every later gate has `registration.md`.
- Each runner must write `manifest.json` (`opentsense/manifest.py`). G81c, G81d and G81d2 did not; the gap is listed
  in the test's `KNOWN_GAPS` and must not be extended to new gates.
