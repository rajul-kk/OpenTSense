# G101 registration (written 15 Nov 2026, before any run; bars fixed now)

### G101: Is the spectral radius certified by power iteration, and does the left Perron vector pick the tiles that set the runaway margin? (RQ1)  · REGISTERED

- **Why.** G95 classified runaway with rho = spectral radius of M = R diag(D), D = dP_leak/dT, from a full `eigvals`
  (O(n^3), 0.6 s at n = 1,024). Two consequences of M >= 0 have not been tested on real cases:
  1. **Certificate.** For M >= 0, rho is its Perron root, and for any x > 0 the Collatz–Wielandt bounds
     min_i (Mx)_i / x_i <= rho <= max_i (Mx)_i / x_i hold. Power iteration narrows the bracket in O(it n^2). Runaway
     can then be certified (lower bound >= 1) or excluded (upper bound < 1) without a full eigendecomposition.
  2. **Driving tiles.** At the runaway boundary (saddle node), the Jacobian J = I - M is singular. For a leakage
     perturbation p, implicit differentiation gives ds*/dp = -(y^T dF/dp) / (y^T dF/ds), with y the left null vector
     of J, which is the left Perron vector of M. Scaling tile j's leakage by (1 + e) gives, to first order,
     ds*/s* = -e sum_{j in S} w_j / sum_j w_j, with w_j = (R^T y)_j P_leak,j(T*). The tiles that set the margin are
     therefore ranked by w, not by temperature or leakage alone.
- **Novelty (searched 15 Nov 2026).** The scalar criterion R dP/dT < 1 is known (detectors, per-block chips). The
  multi-core power-temperature fixed-point analysis (Bhat, Gumussoy, Ogras 2018) works per hotspot with Newton and
  gives no spectral or eigenvector form. A battery FE paper uses an eigenvalue sign; multi-finger HBT work uses
  thermal-resistance matrices and collapse patterns. No source was found for a Collatz–Wielandt certificate or a
  left-Perron ranking of runaway-driving tiles on a chip's tile grid. Claimed only as "not found in these searches".
- **Cases.** G95's 12 windows (IHP SG13G2, ASAP7 RVT, ASAP7 LVT ibex; k0–k3) at G95's hot ambient, 358.15 K, on
  G95's case construction (`gates/g95/sweep.py` `load`, imported unchanged, with its G92e reproduction check). These
  cases are **not held out**: G95 ran them. The quantities gated here were never computed on them.
- **Pilot (disclosed).** Power iteration against `eigvals` was tried only on random non-negative matrices (n 1,024 and
  2,048: same value to 1e-15, 2–15 ms against 0.6–5 s). The bars below come from the theory, not from that pilot.
- **Method.** `run.py` per kit, in `opentsense:g75spice` capped at 2 GB, output `gates/g101/runs/main/` (git-ignored).
  - Part (a): `runaway.classify` runs unchanged with `eigvals`. A recorder wrapped around its `_rho` also runs
    power iteration on every M it sees (start x = 1; stop when (hi - lo) / hi <= 1e-12, or after 10,000 iterations)
    and records eigvals rho, the bracket [lo, hi], iterations and both times. It covers every Newton iterate of every
    bisection probe of `runaway.critical_scale` (G95's settings: lo 1e-2, hi 1e6, rtol 1e-4, max_it 400).
  - Part (b): at the last converged bisection scale s_lo, Newton's fixed point T* gives w_j = (R^T y)_j P_leak,j(T*).
    z = R^T y is computed directly as the right Perron vector of R^T diag(D), because M^T has zero rows on tiles
    without leakage. Four tile sets of size k = 51 (5% of 1,024):
    - **Perron:** top w;
    - **hot:** top T*;
    - **leak:** top P_leak(T*);
    - **slope:** top D(T*).
    For each set, every instance in those tiles has its leakage times 1.1. s* is found again by the same bisection
    (bracket 0.5 s* to 1.5 s*). The reported drop is drop = 1 - s*_new / s*.
- **Validity (INCONCLUSIVE, not FAIL).**
  - G95's reproduction check passes.
  - R.min() >= 0 for each kit, and D.min() >= 0 at every recorded call, since the Perron argument needs M >= 0.
  - The recorder sees more than 0 calls.
  - Every bisection brackets (lo converged, hi runaway).
- **Pass if all hold, on every kit and window:**
  - **(a) Certificate.** At every recorded call:
    - the bracket closes to 1e-12 within 10,000 iterations;
    - eigvals rho lies in [lo (1 - 1e-10), hi (1 + 1e-10)];
    - the decision is identical, i.e. (hi >= 1) == (eigvals rho >= 1).
  - **(b) Ranking.** drop(Perron) >= drop(set) - 2e-4 for each baseline set (hot, leak, slope). 2e-4 is twice the
    bisection's relative tolerance, so a difference below it is a tie.
  - **(c) First-order prediction.** |drop - pred| / drop <= 0.25 for the Perron set, where
    pred = 1 - 1 / (1 + 0.1 sum_S w / sum w), the first-order law solved for a finite scaling.
- **Reported, not gated.**
  - Mean time per call (eigvals against power iteration), and power-iteration iterations.
  - drop for every set, and pred for every set.
  - How many windows have Perron strictly best by more than 2e-4. If none, the ranking is "no better than the simple
    baselines" and is reported as such.
  - Overlap of the Perron set with each baseline set.
  - The right Perron vector's peak tile against T*'s peak.
- **A fail means.**
  - (a): power iteration is not a safe replacement for eigvals on these matrices, and `electrothermal.rho` keeps
    `eigvals`.
  - (b): the left-Perron ranking does not find the margin-setting tiles better than temperature or leakage alone.
  - (c): the first-order law does not size the effect at a 10% change.
- **Not claimed.**
  - Switching `electrothermal.rho` to power iteration. That is a separate change, and it needs the student's
    go-ahead even if (a) passes.
  - Transient runaway.
  - Corners other than G92e's.
  - Sensor placement from the right vector, which is reported only.
- **Code and output.** `run.py`, `evaluate.py`, `run.sh` here; output `runs/main/`.

Amendments go below, dated, each with the reason. Never re-run until it passes.

**Amendment 1 (15 Nov 2026, during the run, before any result was seen; no bar changed): prior art.** A wider search
found the method behind part (b) in power systems. The sensitivity of the loading margin at a saddle-node bifurcation,
taken from the Jacobian's zero left eigenvector, is Greene, Dobson and Alvarado (IEEE Trans. Power Systems 12(1),
1997). The same work ranks contingencies by it. Collatz–Wielandt bounds are textbook Perron–Frobenius theory, used for
example in wireless power control (Friedland). So neither the certificate nor the sensitivity formula is new.
What was not found, in searches of chip electrothermal, 3D-IC leakage, power-device and multi-finger HBT work, is
their use for leakage–temperature runaway on a chip's tile grid: certifying runaway without an eigendecomposition,
and ranking the tiles that set the leakage margin. The claim is limited to that transfer.

**Amendment 2 (15 Nov 2026, during the run, before scoring; review fix, no threshold changed).**
- Bar (c) now states its implicit premise explicitly: the Perron set's drop must exceed the tie, 2e-4. A drop within
  the bisection tolerance is no measurable effect, and the ratio |drop - pred| / drop is then meaningless: negative,
  or a division by zero.
- In `evaluate.py`, the separate "iterations <= 10,000" test is removed. It was always true, because `perron` stops
  at 10,000. A bracket still open at the stop is what fails (a).
