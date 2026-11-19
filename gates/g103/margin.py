"""G103: the leakage margin s* (leakage scale at which the loop runs away) of every window of one kit at one corner,
at G95's hot ambient (358.15 K), with G95's operator, solver settings and bisection (sweep.load, runaway.critical_scale).
G95's check against G92e's recorded peaks is not run: corners have no G92e record.

Usage (in the image, repo root): python gates/g103/margin.py <kit run dir> <inst_loc.csv> <stack yaml> <out.json>
"""
import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("g95_sweep", os.path.join(ROOT, "gates", "g95", "sweep.py"))
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
from opentsense.thermal import electrothermal as et, runaway  # noqa: E402

T_AMB = sweep.AMBIENT["hot"]


def main(run, loc, stack, out):
    R, NT, cases = sweep.load(run, loc, stack, os.path.dirname(out))
    res = {"T_amb_K": T_AMB, "windows": {}}
    for w, (L, dyn, tl) in cases.items():
        def mk(s):
            return et.LeakModel(sweep.TEMPS, L, tl, NT, s)
        real = runaway.classify(R, dyn, mk(1.0), T_AMB, **sweep.NEWTON)
        # bracket as G95's sweep_window (frozen; v4's TT control checks the two agree)
        s_lo, s_hi, n = runaway.critical_scale(R, dyn, mk, T_AMB, lo=1e-2, hi=1e6, rtol=sweep.RTOL, **sweep.NEWTON)
        res["windows"][w] = {"margin": float(np.sqrt(s_lo * s_hi)), "s_lo": s_lo, "s_hi": s_hi, "probes": n,
                             "real_status": real.status,
                             "real_peak_K": float(real.T.max()) if real.status == "converged" else None,
                             "leak_at_ambient_W": float(mk(1.0).at(T_AMB - 273.15).sum()), "dyn_W": float(dyn.sum())}
        print(w, res["windows"][w]["margin"], real.status, flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
