# GNN registration (written DD Mon YYYY, before the gated run)

### GNN: one-line title · REGISTERED

- **Why.** What question this answers and which earlier gate it builds on.
- **Set-up.** Inputs, tools, image, workloads, seeds. Everything a rerun needs.
- **Noise floor (required for numeric bars; `plan.md` §2.1).** For each gated metric: how the repeat-run spread was
  measured (what was varied, how many repeats), and its value. Put the measurement script in `dry/`.
- **Pass if all hold:**
  - **(a)** ... Each numeric bar is either at least 3× the floor above, or an equivalence margin with its test named
    (for example: paired TOST at α = 0.05, or the 95% bootstrap interval of the difference lies inside ±margin).
- **Validity.** Conditions under which the result is INCONCLUSIVE rather than FAIL.
- **Reported, not gated.** Numbers that are recorded but do not decide the verdict.
- **A fail means.** What a fail would tell us, and what follows.
- **Not claimed.** Limits of the result.
- **Code and output.** Scripts here; output in `runs/main/`; after the run, `python scripts/record_gate.py GNN`.

Amendments go below, dated, each with the reason. Never re-run until it passes.
