# G95: The runaway boundary near rho = 1 (RQ1) · PASS (run 13 Nov 2026)

Registration: `registration.md` (queued for commit as #51 before the run). Draft and pilot: `draft.md`,
`dry/pilot300/`. Run: `run_sweep.sh gates/g95/runs/main hot`, then `evaluate.py gates/g95/runs/main hot`. Output:
`runs/main/` (git-ignored); record: `record/{result,manifest}.json`.

Cases (held out): G92e's three ibex designs (IHP SG13G2, ASAP7 RVT, ASAP7 LVT), four windows each, at G92e's hot
ambient, 358.15 K, leakage scaled by f = s / s* on 0.5, 0.8, 0.9, 0.95, 0.99, 0.999, 1.001, 1.01, 1.1, 1.5.
Validity held: every window's real-leakage fixed point reproduced G92e's recorded hot peak within 1e-6 K.

## Verdict

| Bar | Result | Pass? |
|---|---|---|
| (a) f <= 0.999 converges, f >= 1.001 runs away; Picard (10^5 iterations) agrees within 1e-6 K | all 12 windows; Picard within 2.2e-9 K on every converged point | yes |
| (b) rho at the last converged bisection point >= 0.97 | 0.9885 to 0.9969 | yes |
| (c) \|A - 1/(1 - rho_hot)\| / A <= 0.25 for converged f <= 0.8 | worst 6.0% (IHP), 15.5% (RVT), 15.2% (LVT) | yes |

**PASS.** On real leakage tables at a hot ambient, the spectral test along Newton separates converging from running
away to within 0.1% of the leakage, the bisected boundary sits where rho reaches 1, and 1/(1 - rho) at the operating
point predicts the leakage amplification within 16% while the leakage is at most 80% of the runaway leakage.

## Leakage margin: how far each design is from runaway (1/f at the real leakage)

| Kit | 300 K (pilot) | 358.15 K (this gate) |
|---|---|---|
| IHP SG13G2 | 33,000 to 33,200 | 4,580 to 4,620 |
| ASAP7 RVT | 176 to 197 | 22.8 to 25.2 |
| ASAP7 LVT | 23 to 26 | **4.1 to 4.5** |

At an 85 C ambient, the LVT ibex runs away if its leakage is about four times the library's typical value; RVT at
about 24 times. The margin shrinks about 7x between 300 K and 358 K on every kit.

## Reported

- **Near the boundary rho is not a distance.** 1 - rho ~ c sqrt(1 - f) with c = 1.35 to 1.37 at f = 0.99 and 1.37 to
  1.42 at f = 0.999 (sqrt 2 = 1.414 for one temperature exponent): at f = 0.999, rho_hot is about 0.955, yet the
  design is 0.1% of leakage from runaway. Quote the leakage margin f, not rho.
- **Prediction fails near the boundary**, as in the pilot: at f = 0.999 A = 2.8 to 3.5 against 1/(1 - rho_hot) of
  about 22; 1/(1 - rho_cold) under-predicts (1.1 to 1.5). G74's A (baseline at 25 C) reads 2.6 to 2.7 there.
- Newton needed at most 10 iterations; every step was monotone on ASAP7, not on IHP (not gated, as in the pilot).
- Peak temperature at f = 0.999: IHP 388 K, RVT 419 to 423 K, LVT 426 to 430 K.

## What this means

RQ1: the electrothermal loop's runaway test is reliable on the real temperature-aware libraries, and the useful
number for a design is its leakage margin. At a hot ambient the LVT ibex has a margin of about 4x, which process
variation (fast corners leak several times typical) could use up; this motivates corners in later work.

## Not claimed

As registered: transient runaway (G94); temperature-dependent conductivity; process corners other than typical; one
stack per kit; G74's 20 cases are not re-classified here.
