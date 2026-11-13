# Untangle log

Decisions from the untangle step (run in every review-and-commit loop), kept so they survive between sessions.

## Standing answers

| Question | Answer | Date |
|---|---|---|
| Extra passes beyond the core untangle (Comments, Tests, both, neither) | **Both**: comments are brought in line with the code (each says why, none restates what), and tests are checked for coverage of each module's contract, adding missing ones | 2026-11-12 |

## Open evidence for goal 0 (from `codegraph.py`, 2026-11-12)

| Finding | Files | Note |
|---|---|---|
| Hidden link | `stack/model.py` with `to_3dice.py`, `to_pact.py`, `thermal/run.py` | changed together in 3 of 3 commits, no import between them: each converter re-reads the stack format itself |
| Hidden link | `to_3dice.py` with `to_pact.py` | same cause |
| Hidden link | `thermal/run.py` with `tests/test_stack.py` | |
| Copied code | `gates/g92*/evaluate.py` (5 versions) and `gates/g95/sweep.py` | case construction copied; G92e's own copy is left alone until its run ends |
| Shared formulas | `power/dramctl.py` scheduler and checker | both derive timing from the same reading; one cited timing table should feed both |
