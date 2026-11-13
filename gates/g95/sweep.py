"""G95 sweep: leakage margin and runaway boundary on G92e's designs, at G92e's nominal (300 K) or hot (358.15 K) ambient.

Per kit and power window, from G92e's run directory (power per temperature, instance locations, stack):
1. the critical leakage scale s* (`runaway.critical_scale`, bisection to rtol 1e-4 on Newton's status);
2. the real design's margin f_nominal = 1 / s* (s = 1 is the real leakage) (leakage as a fraction of the runaway leakage);
3. a grid of f = s / s* around 1: status, iterations, monotone flag, rho at T_amb (cold) and at the fixed point
   (hot), measured amplification A against 1/(1 - rho_cold) and 1/(1 - rho_hot), and on the converged side the
   difference from a long Picard solve (`electrothermal.solve`, 1e5 iterations);
4. the saddle-node check: rho at the last converged scale against 1 - sqrt(2 (1 - f)).
A (`amp_ambient`) is G74's ratio with the no-feedback baseline at leakage evaluated at the ambient, which is what
1/(1 - rho) predicts at any ambient; G74's own A (baseline at 25 C, `electrothermal.amplification`) is kept as A_25C.
The case construction copies G92e's evaluate.py (part c), which runs at import and so cannot be imported. The copy
is checked instead: each window's fixed point at the real leakage (s = 1, at the case's ambient) must reproduce the peak
G92e recorded for it (`result.json`, c.cases.<window>_<case>.peak_K), or the sweep stops. It runs in the OpenTSense image
because the tile operator comes from PACT (`response.build`).

Usage: sweep.py <kit> <G92e run dir> <inst_loc.csv> <stack yaml> <out dir> [nominal|hot]
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense.power import maps  # noqa: E402
from opentsense.power.leaklib import TEMPS  # noqa: E402
from opentsense.stack import model  # noqa: E402
from opentsense.thermal import electrothermal as et, response, runaway  # noqa: E402

F_GRID = [0.5, 0.8, 0.9, 0.95, 0.99, 0.999, 1.001, 1.01, 1.1, 1.5]
AMBIENT = {"nominal": 300.0, "hot": 358.15}   # G92e's two cases (evaluate.py part c), K
WINS = [f"k{k}" for k in range(4)]
NEWTON = dict(max_it=400)
RTOL = 1e-4               # bisection tolerance on s*
SAME_AS_G92E_K = 1e-6     # largest peak difference from G92e's recorded case


def amp_ambient(R, dyn, leak, t_amb, T_star):
    """(T* - T_u) / (T_1 - T_u) on the peak tile, with T_u at every instance's leakage at the ambient temperature."""
    Tu = t_amb + R @ (dyn + leak.at(t_amb - 273.15))
    T1 = t_amb + R @ (dyn + leak.tiles(Tu))
    p = int(np.argmax(T_star))
    return float((T_star[p] - Tu[p]) / (T1[p] - Tu[p]))


def check_against_g92e(run, R, NT, cases, case):
    """Raise if any window's fixed point at the real leakage differs from the peak G92e recorded for that case."""
    rec = json.load(open(os.path.join(run, "result.json")))["c"]["cases"]
    for w, (L, dyn, tl) in cases.items():
        o = runaway.classify(R, dyn, et.LeakModel(TEMPS, L, tl, NT, 1.0), AMBIENT[case], **NEWTON)
        want = rec[f"{w}_{case}"]["peak_K"]
        if o.status != "converged" or abs(o.T.max() - want) > SAME_AS_G92E_K:
            raise RuntimeError(f"{w}: {case} case gives {o.status} peak {o.T.max():.9f} K, G92e recorded {want:.9f} K; "
                               "this copy of G92e's case construction has drifted")


def load(run, loc, stack_path, out):
    box, pos = maps.read_locations(loc)
    P = {(w, str(T)): maps.read_power(os.path.join(run, "power", f"{w}_{T}.txt")) for w in WINS for T in TEMPS}
    stack = model.load(stack_path)
    nx, ny = stack.grid
    NT = nx * ny
    x0, y0, x1, y1 = box

    def tile_of(names):
        return np.array([min(ny - 1, int((pos[n][1] - y0) / (y1 - y0) * ny)) * nx
                         + min(nx - 1, int((pos[n][0] - x0) / (x1 - x0) * nx)) for n in names])

    eye = np.eye(NT)                       # one shared matrix: np.eye(NT)[k] per k would keep NT copies alive
    basis = [{"die0": eye[k].reshape(ny, nx)} for k in range(NT)]
    R = response.build(stack, basis, os.path.join(out, "operator"))[:, 0].reshape(NT, NT).T
    cases = {}
    for w in WINS:
        names = sorted(n for n in P[(w, "25")][0] if n in pos)
        L = np.array([[P[(w, str(T))][0][n][2] for T in TEMPS] for n in names])
        d = np.array([P[(w, "25")][0][n][0] + P[(w, "25")][0][n][1] for n in names])
        tl = tile_of(names)
        cases[w] = (L, np.bincount(tl, weights=d, minlength=NT), tl)
    return R, NT, cases


def sweep_window(R, NT, L, dyn, tl, t_amb):
    def mk(s):
        return et.LeakModel(TEMPS, L, tl, NT, s)

    lo, hi = 1e-2, 1e6
    s_lo, s_hi, n = runaway.critical_scale(R, dyn, mk, t_amb, lo=lo, hi=hi, rtol=RTOL, **NEWTON)
    s_star = np.sqrt(s_lo * s_hi)
    rows = []
    for f in F_GRID:
        lk = mk(f * s_star)
        o = runaway.classify(R, dyn, lk, t_amb, **NEWTON)
        rho_cold, _ = et.rho(R, lk, np.full(NT, t_amb))
        row = dict(f=f, status=o.status, iterations=o.iterations, monotone=o.monotone, rho_cold=float(rho_cold),
                   rho_end=float(o.rho))
        if o.status == "converged":
            A = amp_ambient(R, dyn, lk, t_amb, o.T)
            A25 = et.amplification(R, dyn, lk, t_amb, o.T)[0]
            Tp, itp, okp, _ = et.solve(R, dyn, lk, t_amb, max_it=100000)
            row.update(peak_K=float(o.T.max()), A=float(A), A_25C=float(A25), pred_cold=float(1 / (1 - rho_cold)),
                       pred_hot=float(1 / (1 - o.rho)), picard_converged=bool(okp), picard_iters=int(itp),
                       picard_diff_K=float(np.abs(Tp - o.T).max()) if okp else None,
                       saddle_node=float(1 - np.sqrt(2 * (1 - f))) if f < 1 else None)
        rows.append(row)
    o_lo = runaway.classify(R, dyn, mk(s_lo), t_amb, **NEWTON)
    return dict(s_lo=s_lo, s_hi=s_hi, probes=n, f_nominal=float(1 / s_star), rho_at_s_lo=float(o_lo.rho),
                rho_bound_b=float(1 - np.sqrt(2 * 2 * RTOL)), grid=rows)


def main(kit, run, loc, stack_path, out, case="nominal"):
    if case not in AMBIENT:
        raise SystemExit(f"case must be one of {sorted(AMBIENT)}, got {case!r}")
    os.makedirs(out, exist_ok=True)
    R, NT, cases = load(run, loc, stack_path, out)
    check_against_g92e(run, R, NT, cases, case)
    res = {"kit": kit, "case": case, "T_amb_K": AMBIENT[case], "windows": {}}
    for w, (L, dyn, tl) in cases.items():
        res["windows"][w] = r = sweep_window(R, NT, L, dyn, tl, AMBIENT[case])
        print(kit, w, "f_nominal", r["f_nominal"], "rho at s_lo", r["rho_at_s_lo"], flush=True)
    json.dump(res, open(os.path.join(out, f"sweep_{kit}.json"), "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:7])
