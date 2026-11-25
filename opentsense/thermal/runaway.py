"""Runaway boundary of the leakage-temperature loop (goal U4): Newton with a spectral-radius test, and every runaway
verdict confirmed by fixed-point iteration.

The steady loop is F(T) = T - T_amb - R (P_dyn + P_leak(T)) = 0 on the tile operator R (`electrothermal`). Following
Thermo's report 9.37 (Newton-PCG on the full field with Jacobian A - E D W, and a spectral-radius stability test along
the monotone iteration; 150 of 150 cases classified there), this uses Newton steps with the Jacobian
J = I - R diag(dP_leak/dT), solved densely since R is a tile operator, and checks rho = spectral radius of
R diag(dP_leak/dT) at every iterate:
- the step falling under `tol` with rho < 1: converged (a stable fixed point, whatever the table);
- rho reaching 1, a step that is not finite or lands where the leakage overflows (`rho` returns inf; c6 v2), or a
  fixed point with rho >= 1: Newton's runaway, which then has to be confirmed (below);
- neither within `max_it`: not converged (reported separately, unlike G74's inner solve).

Newton's runaway exits rely on its iterates staying below the lowest fixed point, which holds only for leakage convex
in T. The log-linear tables are exponential within each segment but not convex across a knot where the log slope
falls, and Liberty-derived tables mostly are not (G92e's: most instances; c6's SVT). There a step can overshoot a
stable fixed point into rho >= 1 with `monotone` still True (C6-3: one tile, R = 30 K/W, a stable root at 319.80 K
with rho 0.952; Newton steps to 320.91 K, rho 1.006). So a runaway verdict stands only once `lowest_fixed_point`,
which needs R >= 0, dyn >= 0 and leakage increasing in T but no convexity, passes `T_cap` too. Every verdict
is relative to T_cap (default 1000 K): "runaway" means no operating point at or below it.

Limit: the certificates compare floating-point evaluations of the loop map H, with a margin for the rounding of the
matrix product only (not of the per-tile leakage sum or the interpolation). A boundary within about 1e-10 K of a
probe's H(U) - U, or a root within that of T_cap, can be classified on the wrong side (Sol, RF-5/RF-6: built with
thousands of summed instances or a cap set to 2^-36 K; endpoints off by ~1e-13 relative). That is about nine orders
below critical_scale's rtol (1e-4), so brackets hold to their tolerance; exact enclosures would need interval
arithmetic on every evaluation.
"""
from dataclasses import dataclass

import numpy as np

from . import electrothermal as _et
from .electrothermal import rho as _rho


@dataclass
class Outcome:
    status: str            # "converged", "runaway" or "not_converged"
    T: np.ndarray          # last iterate, K
    rho: float             # spectral radius at T (central difference; reported, not the verdict after picard_it > 0)
    iterations: int        # Newton iterations
    monotone: bool         # every Newton step was >= 0 in every tile (to round-off)
    rho_path: list         # rho at each iterate
    picard_it: int = 0     # fixed-point iterations run to check a Newton runaway (0: none needed)


def operator(R):
    """R as the loop uses it: >= 0. R = A^-1 B of a conduction matrix is >= 0 exactly; solves can leave round-off
    negatives (down to 1e-12 of the largest entry), which are set to 0 here once, so every verdict refers to that
    projected operator. Larger negatives are refused: the monotone arguments below need R >= 0."""
    R = np.asarray(R, float)
    if R.min() < -1e-12 * np.abs(R).max():
        raise ValueError("R has negative entries beyond round-off; the runaway tests need R >= 0")
    return np.maximum(R, 0.0)


def upper_solution(R, dyn, leak, T_amb, T, T_cap, h=0.5):
    """True if a point U >= T at or below T_cap has H(U) <= U in every tile, H(U) = T_amb + R (dyn + P_leak(U)), with a
    margin for the rounding of H. H is monotone and H(T_amb) >= T_amb, so H then maps [T_amb, U] into itself and a
    fixed point exists there (Tarski); a small final step alone does not show that (it also happens just past the
    fold). U = T + d x, x the Perron vector of R diag(dP/dT) at T (ones where it has none), d from 1e-6 to 1 K."""
    _, D = _et.rho(R, leak, T, h)
    M = R * D[None, :]
    got = _et.perron(M) if np.all(np.isfinite(M)) and M.min() >= 0 and (M > 0).any(axis=1).all() else None
    x = got[2] / got[2].max() if got is not None else np.ones(len(T))
    with np.errstate(over="ignore", invalid="ignore"):
        for d in (1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0):
            U = T + d * x
            if U.max() > T_cap:
                return False
            P = dyn + leak.tiles(U)
            HU = T_amb + R @ P
            slack = 64 * np.finfo(float).eps * (T_amb + R @ np.abs(P))     # rounding bound of H's sum
            if np.all(np.isfinite(HU)) and np.all(HU + slack <= U):
                return True
    return False


def lowest_fixed_point(R, dyn, leak, T_amb, tol=1e-9, max_it=100_000, T_cap=1000.0, h=0.5):
    """Fixed-point iteration T <- T_amb + R (dyn + P_leak(T)) from T_amb. With R >= 0 (`operator`), dyn >= 0 and
    leakage increasing in T, T_amb is below every fixed point and the iterates rise monotonically without passing the
    lowest one; convexity is not needed. Returns (status, T, iterations):
    - "converged": a step under tol and an upper solution at or below T_cap (`upper_solution`): a fixed point exists
      at or below T_cap, and T approximates the lowest one, where the loop settles from T_amb (no rho test: a
      finite-difference rho there misreads a point just below the fold as rho >= 1);
    - "runaway": a finite iterate above T_cap, K (a lower bound of every fixed point: none at or below T_cap);
    - "not_converged": max_it reached (near the boundary the iteration slows like 1 / (1 - rho)), a small step with
      no upper solution found (just past the fold, or too close to it to tell), or an iterate that overflowed before
      passing T_cap (it bounds nothing)."""
    R = operator(R)
    if np.min(dyn) < 0 or np.any(np.diff(leak.ln[leak.pos], axis=1) < 0):
        raise ValueError("lowest_fixed_point needs dyn >= 0 and every leakage table non-decreasing in T")
    T = np.full(len(dyn), float(T_amb))
    with np.errstate(over="ignore", invalid="ignore"):
        for it in range(1, max_it + 1):
            Tn = T_amb + R @ (dyn + leak.tiles(T))
            finite = np.isfinite(Tn)
            if (Tn[finite] > T_cap).any():
                return "runaway", Tn, it
            if not finite.all():
                return "not_converged", Tn, it
            step = float(np.abs(Tn - T).max())
            T = Tn
            if step < tol:
                ok = upper_solution(R, dyn, leak, T_amb, T, T_cap, h)
                return ("converged" if ok else "not_converged"), T, it
    return "not_converged", T, max_it


def classify(R, dyn, leak, T_amb, tol=1e-9, max_it=100, h=0.5, picard_it=100_000, T_cap=1000.0):
    R = operator(R)
    n = len(dyn)
    T = np.full(n, float(T_amb))
    path, monotone = [], True

    def by_fixed_point(T, r, it):
        """Newton gave no certified operating point: the fixed-point iteration decides. Its rho is reported only
        (`electrothermal.rho` itself, not the `_rho` G101 swaps in to record Newton's)."""
        st, Tp, k = lowest_fixed_point(R, dyn, leak, T_amb, tol, picard_it, T_cap, h)
        if st == "converged":
            rp, _ = _et.rho(R, leak, Tp, h)
            return Outcome("converged", Tp, rp, it, monotone, path, k)
        return Outcome(st, T, r, it, monotone, path, k)

    for it in range(1, max_it + 1):
        r, D = _rho(R, leak, T, h)
        path.append(r)
        if r >= 1.0:
            return by_fixed_point(T, r, it)
        F = T - T_amb - R @ (dyn + leak.tiles(T))
        step = np.linalg.solve(np.eye(n) - R * D[None, :], -F)
        if not np.all(np.isfinite(step)):
            return by_fixed_point(T, r, it)
        monotone &= bool(step.min() >= -1e-9 * max(1.0, np.abs(T).max()))
        T = T + step
        if np.abs(step).max() < tol:
            r, _ = _rho(R, leak, T, h)
            path.append(r)
            # converged only with rho < 1 and an upper solution at or below T_cap; otherwise (the fold, a point above
            # a stable one Newton stepped over, one above T_cap, or no certificate) the fixed-point iteration decides
            if r < 1.0 and T.max() <= T_cap and upper_solution(R, dyn, leak, T_amb, T, T_cap, h):
                return Outcome("converged", T, r, it, monotone, path)
            return by_fixed_point(T, r, it)
    r = _rho(R, leak, T, h)[0] if np.all(np.isfinite(T)) else float("nan")
    path.append(r)
    return Outcome("not_converged", T, r, max_it, monotone, path)


def critical_scale_1tile(r_KW, dyn_W, c_W, a_perK, T_amb_K):
    """Analytic boundary for one tile with leakage c exp(a (T - 273.15)), T in K: a fixed point exists while
    c <= exp(-a (T_c - 273.15)) / (r a), with T_c = T_amb + r dyn + 1/a (where the loop's line touches the leakage
    curve). Returns that largest c."""
    Tc = T_amb_K + r_KW * dyn_W + 1.0 / a_perK
    return np.exp(-a_perK * (Tc - 273.15)) / (r_KW * a_perK)


def critical_scale(R, dyn, make_leak, T_amb, lo=1e-3, hi=1e3, rtol=1e-4, **kw):
    """Largest leakage scale s with an operating point (a stable fixed point, or the lowest fixed point the loop
    reaches from T_amb when Newton's runaway had to be checked) at or below T_cap (classify's, 1000 K unless passed
    in kw), by bisection in log s on `classify`'s status.
    make_leak(s) -> LeakModel with every instance's leakage times s. Needs classify(lo) converged and classify(hi)
    runaway. Returns (s_lo, s_hi, n_classified): s_lo converged, s_hi runaway, s_hi / s_lo - 1 <= rtol.
    Raises RuntimeError if the bracket is wrong or any probe is not converged (the boundary is then not located)."""
    if not 0 < lo < hi:
        raise ValueError(f"need 0 < lo < hi, got lo={lo:g}, hi={hi:g}")

    def status(s):
        st = classify(R, dyn, make_leak(s), T_amb, **kw).status
        if st == "not_converged":
            raise RuntimeError(f"scale {s:.6g}: not converged; raise max_it (Newton) or picard_it")
        return st
    if status(lo) != "converged" or status(hi) != "runaway":
        raise RuntimeError(f"bracket [{lo:g}, {hi:g}] does not contain the boundary")
    n = 2
    while hi / lo - 1 > rtol:
        mid = np.sqrt(lo * hi)
        if status(mid) == "converged":
            lo = mid
        else:
            hi = mid
        n += 1
    return lo, hi, n
