"""G75 shortcut (3): fixed 25 C leakage against the coupled loop on the clean G71 3D stack, in PACT.
Usage: stack.py <g74 inputs.npz> <run dir>"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense.stack import model  # noqa: E402
from opentsense.thermal.run import run_pact  # noqa: E402

Z = np.load(sys.argv[1]); RUN = sys.argv[2]
M = np.load(os.path.join(ROOT, "gates/g71/inputs/maps.npz"))
stack = model.load(os.path.join(ROOT, "configs/stacks/g71_3d.yaml"))
AMB = stack.ambient_K if hasattr(stack, "ambient_K") else 300.0
TT, CT, CC = Z["a7_T"], np.log(Z["a7_curve_tpu"]), np.log(Z["a7_curve_R"])
SHARE = {"top": 0.004, "bot": 0.00035}


def f(ln, T):
    y = np.interp(T, TT, ln)
    return np.exp(np.where(T > TT[-1], ln[-1] + (T - TT[-1]) * (ln[-1] - ln[-2]) / (TT[-1] - TT[-2]), y))


res = {}
for s in range(4):
    P = {"top": M[f"tpu_s{s}"], "bot": M[f"cpu_s{s}"]}
    L25 = {d: P[d] * SHARE[d] for d in P}; dyn = {d: P[d] - L25[d] for d in P}
    t0 = time.time()
    T = run_pact(stack, P, os.path.join(RUN, f"stack/s{s}/i0"))
    T0 = {d: float(T[d].max() - AMB) for d in T}; peaks = [max(T0.values())]
    Tk = T
    for it in range(1, 9):
        Pn = {d: dyn[d] + L25[d] * (f(CT if d == "top" else CC, 25 + Tk[d] - AMB)) for d in P}
        Tk = run_pact(stack, Pn, os.path.join(RUN, f"stack/s{s}/i{it}"))
        peaks.append(max(float(Tk[d].max() - AMB) for d in Tk))
        print(s, it, round(peaks[-1], 3), flush=True)
        if abs(peaks[-1] - peaks[-2]) < 0.02:
            break
    res[s] = dict(uncoupled_rise_K=T0, coupled_rise_K={d: float(Tk[d].max() - AMB) for d in Tk}, peak_shift_K=peaks[-1] - peaks[0], iters=it, leak_ratio=float(sum((Pn[d] - dyn[d]).sum() for d in P) / sum(L25[d].sum() for d in P)), wall_s=time.time() - t0)
json.dump(res, open(os.path.join(RUN, "stack.json"), "w"), indent=1)
print(json.dumps({k: round(v["peak_shift_K"], 3) for k, v in res.items()}))
