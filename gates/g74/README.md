# G74: leakage runaway margin ρ(R·D)

**Verdict: PASS (2 Nov 2026).** Registration and Amendment 1: `registration.md`. Result: `runs/main/result.json` (not in git); summary below.

Run: `gates/g74/run.sh main`. Post-hoc (not gated, written after the verdict): `gates/g74/posthoc.py`.

| Group | Cases | ρ at the uncoupled point | Amplification predicted / measured |
|---|---|---|---|
| G31, runaway | 4 | 8.32 to 8.34 | n/a |
| G31b, runaway | 4 | 6.27 to 6.28 | n/a |
| G37, converged | 8 | 3e-8 to 1e-5 | 1.00001 / 1.00001 |
| G41, converged | 4 | 0.037 to 0.042 | 1.039 to 1.046 / 1.041 to 1.047 |

**Limits.**
- Bar (b) was weak as registered: measured amplification never exceeded 1.05, so even "no amplification" would have passed. The post-hoc test on the converged G31b runs is the stronger evidence: 16 runs at 1.2× or more (up to 1.71×), all within 25%, worst 21%.
- All 96 G31b map runs are classified correctly, but the closest cases are ρ = 0.38 and ρ = 3.9. The exact boundary at ρ = 1 is not tested.
- G31 is included because the registration names it, but its exponential leakage model was withdrawn by G35b.
