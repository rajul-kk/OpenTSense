# G95 draft (written 12 Nov 2026; NOT registered): the runaway boundary near ρ = 1 (goals.md U4)

### G95: Does the stability margin separate runaway from convergence at ρ ≈ 1, and what does it predict? (RQ1) · DRAFT

- **Why.** G74 passed, but its nearest cases were ρ = 0.38 and 3.9, so ρ ≈ 1 itself was never tested. Four of its
  eight "runaway" cases were only "no convergence in 40 iterations", and its inner solve flags neither NaN nor the
  cap. Its bar (b) was weak: measured amplification was at most 1.05.
- **Method (code ready, `opentsense/thermal/runaway.py`, 11 unit tests).** Monotone Newton from T_amb on the tile
  operator, F(T) = T − T_amb − R (P_dyn + P_leak(T)), Jacobian J = I − R diag(dP_leak/dT), with ρ = spectral radius of
  R diag(dP_leak/dT) checked at every iterate (the stability test of Thermo report 9.37, which classified 150 of 150
  cases with Newton-PCG on the full field). Three statuses: **converged** (step < tol with ρ < 1), **runaway** (ρ
  reaches 1 first, or a non-finite step), **not converged** (iteration cap). Leakage from G92e's libraries
  (`thermal/electrothermal.LeakModel`), so this waits for G92e.
- **Dry findings (12 Nov, not scored).**
  - One tile, exponential leakage, f = leakage ÷ critical leakage: ρ at the fixed point solves
    **ρ − ln ρ = 1 − ln f** exactly (unit test), so **1 − ρ ≈ √(2 (1 − f))** near the boundary (a saddle-node).
    ρ = 0.86 is 1% of leakage from runaway.
    **Not new:** this is Semenov's thermal-explosion condition (1928; Frank-Kamenetskii for fields) and the generic
    square-root law at a saddle-node; cite them. The contribution is its use as a leakage margin for buried dies.
    **Prior art in chips (search 12 Nov):** Bhat, Gumussoy and Ogras, "Power-Temperature Stability and Safety
    Analysis for Multiprocessor Systems", ACM TECS 16(5s) art. 145, 2017 (CODES+ISSS; arXiv 1806.06180): the same
    fixed-point existence test (runaway iff no fixed point) on a discrete-time linear thermal model with exponential
    leakage, a closed-form existence condition for one hotspot, a multi-hotspot extension, planar SoC (Odroid XU3).
    Also Shim, Lee and Shin, IEEE TCAS-I 2015 (DOI 10.1109/TCSI.2014.2380638): closed-form temperatures with a
    piecewise-quadratic leakage fit, used to prevent runaway. Neither treats stacked dies, a spectral-radius test
    along Newton, or the square-root distance law, as far as the abstracts and Bhat's text up to Thm 4.2 show;
    their full texts must be read before any claim.
  - **Several tiles (12 Nov, `gates/g95/sweep.py` on a synthetic 3-tile, 60-instance case):** the square-root
    scaling holds, but the constant √2 is exact only when every instance has the same temperature exponent.
    (1 − ρ)/√(1 − f) at f = 0.999: 1.431 with one exponent (0.03/K; √2 = 1.414), 1.447 with exponents spread over
    0.01 to 0.06/K, 1.512 over 0.005 to 0.1/K. So "1 − ρ ≈ √(2(1 − f))" is a rule of thumb on real tables, and
    the gate should report the fitted constant per design rather than assume √2. On that case Newton and a
    10⁵-iteration Picard agree to round-off on every converged point, every step was monotone, and ρ at the last
    converged bisection point was 0.990 (bar (b)'s bound 0.98).
  - The sweep's resolution in f is the bisection tolerance: with rtol 1e-4 on s*, points closer than about 1e-4 to
    the boundary are not resolved (f = 0.9999 gave a meaningless ratio).
  - 1/(1 − ρ) at the fixed point is not a predictor of amplification near the boundary: f = 0.99 gives 7.4 against a
    measured 2.5; f = 0.999 gives 22.7 against 2.8. G74's 1/(1 − ρ) agreed only because A ≤ 1.05 there.
  - Newton classifies f = 0.5 to 0.999 in 5 to 10 steps; a 40-iteration Picard (G74's cap) calls f ≥ 0.9
    "not converged".
- **Cases (proposed).** G92e's designs and stacks with the leakage scaled by f on a grid that is dense near 1 (for
  example 0.5, 0.8, 0.9, 0.95, 0.99, 0.999, 1.001, 1.01, 1.1, 1.5), found per case by bisection on f to 1e-4; plus
  G74's 20 cases re-classified for continuity (constant-k operator only; k(T) needs G74's own loop).
- **Bars (proposal; the student fixes them, after the noise-floor rule of `plan.md` §2.1).**
  - **(a) Classification:** every case with f ≤ 1 − δ converges and every case with f ≥ 1 + δ runs away, with δ
    registered (the dry check passes δ = 0.001). Checked against an independent long Picard run (10⁵ iterations) on
    the converged side.
  - **(b) Boundary:** the bisected critical f* agrees with ρ = 1 to within the bisection tolerance, i.e. ρ at the
    last converged f is ≥ 1 − √(2 · 2 · 1e-4) ≈ 0.97 (from the saddle-node law).
  - **(c) Prediction, rewritten:** report A against both 1/(1 − ρ_cold) and 1/(1 − ρ_hot) over f, and gate only the
    region where the registered predictor stays within 25%.
- **A fail means.** (a): the spectral test is not a safe margin on real leakage tables (for example because a table
  is not convex across a knot; `classify` reports whether every Newton step was monotone). (b) or (c): ρ is a
  classifier but not a distance, and the report should quote the leakage margin f instead.
- **Not claimed.** Transient runaway (needs G94); k(T) operators beyond G74's cases; process corners other than G92e's.
- **Code (12 Nov).** `runaway.critical_scale` (bisection in log scale on Newton's status; refuses a bad bracket or
  a not-converged probe; 2 unit tests against the analytic boundary) and `gates/g95/sweep.py` (G92e's case
  construction copied, so G92e's files stay untouched; runs in the image because the operator comes from PACT).
- **Effort.** After G92e: run the sweep per kit (minutes; the operator build dominates), then write the scorer once
  the bars are fixed.

## Student decision (12 Nov 2026)

Bars (a) and (b) accepted as proposed (delta = 0.001; rho at the last converged f >= 0.97). Bar (c) is gated on rho_hot (the Jacobian at the converged temperature), with A against 1/(1 - rho_cold) reported only. Bar numbers still follow the noise-floor rule of `plan.md` 2.1 where it applies.
