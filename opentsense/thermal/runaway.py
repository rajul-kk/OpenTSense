"""Runaway boundary of the leakage-temperature loop (goal U4): monotone Newton with a spectral-radius test.

The steady loop is F(T) = T - T_amb - R (P_dyn + P_leak(T)) = 0 on the tile operator R (`electrothermal`). Following
Thermo's report 9.37 (Newton-PCG on the full field with Jacobian A - E D W, and a spectral-radius stability test along
the monotone iteration; 150 of 150 cases classified there), this uses Newton steps with the Jacobian
J = I - R diag(dP_leak/dT), solved densely since R is a tile operator, and checks rho = spectral radius of
R diag(dP_leak/dT) at every iterate.

Starting from T = T_amb, with R >= 0 and leakage increasing and convex in T, the Newton iterates rise monotonically
towards the lowest fixed point and never pass it, and rho rises with them. So:
- rho reaching 1 before convergence means there is no fixed point below: runaway;
- the step falling under `tol` with rho < 1: converged (a stable fixed point);
- neither within `max_it`: not converged (reported separately, unlike G74's inner solve).
The log-linear leakage tables are exactly exponential within each segment; if a table is not convex across a knot,
monotonicity can fail, and `classify` reports whether every step was non-negative.
"""
from dataclasses import dataclass

import numpy as np

from .electrothermal import rho as _rho


@dataclass
class Outcome:
    status: str            # "converged", "runaway" or "not_converged"
    T: np.ndarray          # last iterate, K
    rho: float             # spectral radius at the last iterate
    iterations: int
    monotone: bool         # every Newton step was >= 0 in every tile (to round-off)
    rho_path: list         # rho at each iterate


def classify(R, dyn, leak, T_amb, tol=1e-9, max_it=100, h=0.5):
    R = np.asarray(R, float)
    n = len(dyn)
    T = np.full(n, float(T_amb))
    path, monotone = [], True
    for it in range(1, max_it + 1):
        r, D = _rho(R, leak, T, h)
        path.append(r)
        if r >= 1.0:
            return Outcome("runaway", T, r, it, monotone, path)
        F = T - T_amb - R @ (dyn + leak.tiles(T))
        step = np.linalg.solve(np.eye(n) - R * D[None, :], -F)
        if not np.all(np.isfinite(step)):
            return Outcome("runaway", T, r, it, monotone, path)
        monotone &= bool(step.min() >= -1e-9 * max(1.0, np.abs(T).max()))
        T = T + step
        if np.abs(step).max() < tol:
            r, _ = _rho(R, leak, T, h)
            path.append(r)
            return Outcome("converged", T, r, it, monotone, path)
    return Outcome("not_converged", T, path[-1], max_it, monotone, path)


def critical_scale_1tile(r_KW, dyn_W, c_W, a_perK, T_amb_K):
    """Analytic boundary for one tile with leakage c exp(a (T - 273.15)), T in K: a fixed point exists while
    c <= exp(-a (T_c - 273.15)) / (r a), with T_c = T_amb + r dyn + 1/a (where the loop's line touches the leakage
    curve). Returns that largest c."""
    Tc = T_amb_K + r_KW * dyn_W + 1.0 / a_perK
    return np.exp(-a_perK * (Tc - 273.15)) / (r_KW * a_perK)
