"""G101: certified spectral radius (Collatz–Wielandt bracket by power iteration) and the left-Perron ranking of the
tiles that set the runaway margin, on G95's cases. Bars: `registration.md`.

`runaway.classify` runs unchanged (eigvals); `Recorder` replaces the `_rho` it calls with one that also brackets rho
by power iteration and records both, so every Newton iterate of every bisection probe is compared.

Usage: run.py <kit> <G92e run dir> <inst_loc.csv> <stack yaml> <out dir>
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "g95"))
import sweep  # noqa: E402  (G95's case construction, unchanged)
from opentsense.power.leaklib import TEMPS  # noqa: E402
from opentsense.thermal import electrothermal as et, runaway  # noqa: E402

CASE = "hot"
K = 51                   # 5% of 1,024 tiles
SCALE = 1.1              # leakage factor on a tile set
CLOSE, MAX_IT = 1e-12, 10000


def perron(M):
    """Collatz–Wielandt bracket [lo, hi] of the Perron root of M >= 0 (no zero rows) by power iteration from x = 1.
    Returns lo, hi, iterations, x (the right Perron vector)."""
    x = np.ones(len(M))
    for it in range(1, MAX_IT + 1):
        y = M @ x
        r = y / x
        lo, hi = r.min(), r.max()
        x = y / y.max()
        if hi - lo <= CLOSE * hi:
            break
    return float(lo), float(hi), it, x


class Recorder:
    """Stands in for runaway._rho: returns eigvals' rho (so classify is unchanged) and records the bracket."""

    def __init__(self):
        self.rows = []

    def __call__(self, R, leak, T, h=0.5):
        D = (leak.tiles(T + h) - leak.tiles(T - h)) / (2 * h)   # as et.rho
        M = R * D[None, :]
        t0 = time.perf_counter()
        r = float(np.abs(np.linalg.eigvals(M)).max())
        t1 = time.perf_counter()
        lo, hi, it, _ = perron(M)
        t2 = time.perf_counter()
        self.rows.append((r, lo, hi, it, float(D.min()), t1 - t0, t2 - t1))
        return r, D


def driving_sets(R, dyn, lk, t_amb):
    """At the converged fixed point: w = (R^T y) * P_leak with y the left Perron vector of M = R diag(D), and the four
    tile sets. z = R^T y is taken directly as the right Perron vector of R^T diag(D) (M^T y = rho y gives
    R^T diag(D) z = rho z); M^T itself has zero rows on tiles without leakage."""
    o = runaway.classify(R, dyn, lk, t_amb, **sweep.NEWTON)
    assert o.status == "converged", o.status
    T = o.T
    _, D = et.rho(R, lk, T)
    _, _, _, z = perron(R.T * D[None, :])
    _, _, _, x = perron(R * D[None, :])
    P = lk.tiles(T)
    w = z * P
    top = lambda v: np.argsort(-v, kind="stable")[:K]  # noqa: E731
    sets = {"perron": top(w), "hot": top(T), "leak": top(P), "slope": top(D)}
    return w, sets, dict(peak_T_tile=int(np.argmax(T)), peak_x_tile=int(np.argmax(x)))


def run_window(R, NT, L, dyn, tl, t_amb):
    mk = lambda s, f=1.0: et.LeakModel(TEMPS, L * f, tl, NT, s)  # noqa: E731
    s_lo, s_hi, n = runaway.critical_scale(R, dyn, mk, t_amb, lo=1e-2, hi=1e6, rtol=sweep.RTOL, **sweep.NEWTON)
    s_star = np.sqrt(s_lo * s_hi)
    w, sets, peaks = driving_sets(R, dyn, mk(s_lo), t_amb)
    out = dict(s_star=float(s_star), probes=n, **peaks, sets={})
    for name, S in sets.items():
        f = np.where(np.isin(tl, S), SCALE, 1.0)[:, None]
        a, b, m = runaway.critical_scale(R, dyn, lambda s: mk(s, f), t_amb, lo=0.5 * s_star, hi=1.5 * s_star,
                                         rtol=sweep.RTOL, **sweep.NEWTON)
        phi = float(w[S].sum() / w.sum())
        out["sets"][name] = dict(tiles=[int(j) for j in S], s_star=float(np.sqrt(a * b)), probes=m,
                                 drop=float(1 - np.sqrt(a * b) / s_star), phi=phi,
                                 pred=float(1 - 1 / (1 + (SCALE - 1) * phi)))
    return out


def main(kit, run, loc, stack_path, out):
    os.makedirs(out, exist_ok=True)
    R, NT, cases = sweep.load(run, loc, stack_path, out)
    sweep.check_against_g92e(run, R, NT, cases, CASE)
    t_amb = sweep.AMBIENT[CASE]
    rec = Recorder()
    runaway._rho = rec                     # classify looks _rho up at call time
    res = {"kit": kit, "case": CASE, "T_amb_K": t_amb, "R_min": float(R.min()), "windows": {}}
    for w, (L, dyn, tl) in cases.items():
        rec.rows = []
        r = run_window(R, NT, L, dyn, tl, t_amb)
        r["calls"] = np.array(rec.rows).tolist()   # rho_eig, lo, hi, iterations, D_min, t_eig, t_power
        res["windows"][w] = r
        print(kit, w, "calls", len(rec.rows), {k: round(v["drop"], 5) for k, v in r["sets"].items()}, flush=True)
    json.dump(res, open(os.path.join(out, f"g101_{kit}.json"), "w"))


if __name__ == "__main__":
    main(*sys.argv[1:6])
