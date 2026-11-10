"""G92: score the leakage library, the OpenSTA plumbing and the gate-level loop.
Usage: evaluate.py <run dir> <inst_loc.csv> <g75 power dir>"""
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import brentq

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402
from opentsense.power import maps  # noqa: E402
from opentsense.power.leaklib import TEMPS, literals  # noqa: E402
from opentsense.stack import model  # noqa: E402
from opentsense.thermal import electrothermal as et, response  # noqa: E402
from opentsense.thermal.run import run_pact  # noqa: E402

RUN, LOC, G75P = sys.argv[1:4]
WINS = [f"k{k}" for k in range(4)]
t_start = time.time()
out = {}

# ---------- (a) library equals SPICE ----------
S = json.load(open(os.path.join(RUN, "lib", "leak_states.json")))["cells"]
states = [(c, s) for c, v in S.items() if "skip" not in v for s in v["states"]]
seq_states = [(c, s) for c, s in states if s.get("q_expect") is not None]
g53 = json.load(open(os.path.join(RUN, "leak_g53.json")))
G53MAP = {"inv_1": "sg13g2_inv_1", "nand2_1": "sg13g2_nand2_1", "nor2_1": "sg13g2_nor2_1", "dfrbp_1": "sg13g2_dfrbp_1"}


def g53_state(key):
    base, st = key.rsplit("_", 1)
    cell = S[G53MAP[base]]
    if base == "dfrbp_1":                                   # leak.py: CLK low after one capture, D = Q, RESET_B high
        q = int(st[1]); want = {"CLK": 0, "D": q, "RESET_B": 1, "Q": q}
    else:
        bits = st[1:] if st.startswith("A") else st
        pins = ["A"] if base == "inv_1" else ["A", "B"]
        want = {p: int(b) for p, b in zip(pins, bits)}
    hits = [s for s in cell["states"] if all(literals(s["when"]).get(p) == v for p, v in want.items())]
    assert len(hits) == 1, (key, len(hits))
    return hits[0]


cmp = {}
for key, v in g53.items():
    s = g53_state(key)
    cmp[key] = {t: s["spice_pW"][t] / v[t] - 1 for t in ("25", "50", "75", "100")} if "failed" not in v else None
a_ok = all(s.get("ok") for _, s in states) and all(c is not None and all(abs(x) <= 0.01 for x in c.values()) for c in cmp.values())
ratio25 = np.array([s["lib_pW"] / s["spice_pW"]["25"] for _, s in states if s.get("ok") and s["spice_pW"]["25"] > 0 and s["lib_pW"] > 0])
out["a"] = dict(ok=bool(a_ok), cells=sum("skip" not in v for v in S.values()), skipped=[c for c, v in S.items() if "skip" in v],
                states=len(states), sequential_states=len(seq_states), not_ok=[(c, s["when"]) for c, s in states if not s.get("ok")],
                g53_rel_diff_max=max(abs(x) for c in cmp.values() if c for x in c.values()), g53_rel_diff=cmp,
                lib_over_spice_25C=dict(min=float(ratio25.min()), median=float(np.median(ratio25)), max=float(ratio25.max()), n=int(len(ratio25)),
                                        share_outside_10pct=float(np.mean(np.abs(ratio25 - 1) > 0.1))))
print("a", out["a"]["ok"], out["a"]["states"], out["a"]["g53_rel_diff_max"], flush=True)

# ---------- (b) OpenSTA plumbing ----------
box, pos = maps.read_locations(LOC)
P = {(w, t): maps.read_power(os.path.join(RUN, "power", f"{w}_{t}.txt")) for w in WINS for t in ["ship"] + [str(T) for T in TEMPS]}
ref = {w: maps.read_power(os.path.join(G75P, f"ihp_{w}.txt")) for w in WINS}
b = {}
for w in WINS:
    ship_leak = sum(v[2] for v in P[(w, "ship")][0].values()); g75_leak = sum(v[2] for v in ref[w][0].values())
    names = sorted(n for n in P[(w, "25")][0] if n in pos)
    dyn = {t: np.array([P[(w, t)][0][n][0] + P[(w, t)][0][n][1] for n in names]) for t in map(str, TEMPS)}
    tot = [sum(v[2] for v in P[(w, str(T))][0].values()) for T in TEMPS]
    b[w] = dict(ship_leak_W=ship_leak, g75_leak_W=g75_leak, ship_matches_g75=bool(f"{ship_leak:.6g}" == f"{g75_leak:.6g}"),
                dyn_identical=bool(all(np.array_equal(dyn["25"], dyn[str(T)]) for T in TEMPS)),
                design_leak_W=dict(zip(map(str, TEMPS), tot)), leak_strictly_rising=bool(all(np.diff(tot) > 0)))
out["b"] = dict(ok=bool(all(v["ship_matches_g75"] and v["dyn_identical"] and v["leak_strictly_rising"] for v in b.values())), windows=b)
print("b", out["b"]["ok"], flush=True)

# ---------- (c) loop ----------
stack = model.load(os.path.join(ROOT, "configs/stacks/g92_ihp.yaml"))
nx, ny = stack.grid; NT = nx * ny
x0, y0, x1, y1 = box


def tile_of(names):
    return np.array([min(ny - 1, int((pos[n][1] - y0) / (y1 - y0) * ny)) * nx + min(nx - 1, int((pos[n][0] - x0) / (x1 - x0) * nx)) for n in names])


basis = [{"die0": np.eye(NT)[k].reshape(ny, nx)} for k in range(NT)]
R = response.build(stack, basis, os.path.join(RUN, "operator"))[:, 0].reshape(NT, NT).T     # R[:, k] = rise for 1 W in tile k


def window(w):
    names = sorted(n for n in P[(w, "25")][0] if n in pos)
    L = np.array([[P[(w, str(T))][0][n][2] for T in TEMPS] for n in names])
    d = np.array([P[(w, "25")][0][n][0] + P[(w, "25")][0][n][1] for n in names])
    tl = tile_of(names)
    return names, L, np.bincount(tl, weights=d, minlength=NT), tl


cases, c_ok = {}, True
for w in WINS:
    names, L, dyn, tl = window(w)
    for case, amb, scale in (("nominal", 300.0, 1.0), ("hot", 358.15, 1.0)):
        lk = et.LeakModel(TEMPS, L, tl, NT, scale)
        T, it, conv, _ = et.solve(R, dyn, lk, amb)
        r, _ = et.rho(R, lk, T)
        amp, Tu, T1, p = et.amplification(R, dyn, lk, amb, T)
        pred = 1 / (1 - r)
        ok = conv and abs(pred / amp - 1) <= 0.25
        c_ok &= ok
        cases[f"{w}_{case}"] = dict(converged=conv, iters=it, rho=r, amp_measured=amp, amp_predicted=pred, ok=bool(ok), peak_K=float(T.max()),
                                    peak_shift_vs_fixed25_K=float(T.max() - Tu.max()), leak_W=float(lk.tiles(T).sum()), leak25_W=float(lk.at(25).sum()),
                                    leak_share=float(lk.tiles(T).sum() / (dyn.sum() + lk.tiles(T).sum())), ship_lib_leak_W=b[w]["ship_leak_W"])
        print(w, case, cases[f"{w}_{case}"], flush=True)
    # stress: bisect the leakage scale s (log space) for rho at the fixed point in 0.5 +- 0.05
    lo, hi, found = 0.0, 8.0, None
    for _ in range(60):
        mid = (lo + hi) / 2; lk = et.LeakModel(TEMPS, L, tl, NT, 10 ** mid)
        T, it, conv, _ = et.solve(R, dyn, lk, 300.0, max_it=5000)
        r = et.rho(R, lk, T)[0] if conv else np.inf
        if conv and abs(r - 0.5) <= 0.05:
            found = (10 ** mid, lk, T, it, r); break
        lo, hi = (mid, hi) if r < 0.5 else (lo, mid)
    if found is None:
        c_ok = False; cases[f"{w}_stress"] = dict(ok=False, note="no scale gave rho in 0.45 to 0.55"); continue
    s, lk, T, it, r = found
    amp, Tu, T1, p = et.amplification(R, dyn, lk, 300.0, T)
    pred = 1 / (1 - r); ok = abs(pred / amp - 1) <= 0.25; c_ok &= ok
    cases[f"{w}_stress"] = dict(scale=s, converged=True, iters=it, rho=r, amp_measured=amp, amp_predicted=pred, ok=bool(ok), peak_K=float(T.max()),
                                peak_shift_vs_fixed25_K=float(T.max() - Tu.max()))
    print(w, "stress", cases[f"{w}_stress"], flush=True)

# 1 x 1 grid against an independent scalar root-find (window k0, nominal)
names, L, dyn, tl = window("k0")
s1 = model.load(os.path.join(ROOT, "configs/stacks/g92_ihp.yaml")); s1.grid = (1, 1)
R1 = response.build(s1, [{"die0": np.ones((1, 1))}], os.path.join(RUN, "operator_1x1"))[0, 0].reshape(1, 1)
lk1 = et.LeakModel(TEMPS, L, np.zeros(len(names), int), 1)
T_loop, it1, conv1, _ = et.solve(R1, np.array([dyn.sum()]), lk1, 300.0)
T_root = brentq(lambda T: 300.0 + R1[0, 0] * (dyn.sum() + lk1.tiles(np.array([T]))[0]) - T, 300.0, 600.0, xtol=1e-13, rtol=1e-15)
scalar = dict(T_loop=float(T_loop[0]), T_root=float(T_root), diff_K=float(abs(T_loop[0] - T_root)), R_K_per_W=float(R1[0, 0]), ok=bool(conv1 and abs(T_loop[0] - T_root) <= 1e-9))

# full PACT solve at the converged power (window k0, nominal)
names, L, dyn, tl = window("k0"); lk = et.LeakModel(TEMPS, L, tl, NT)
T, *_ = et.solve(R, dyn, lk, 300.0)
Pt = (dyn + lk.tiles(T)).reshape(ny, nx)
Tp = run_pact(stack, {"die0": Pt}, os.path.join(RUN, "pact_check"))["die0"]
pact = dict(operator_peak_K=float(T.max()), pact_peak_K=float(Tp.max()), diff_K=float(abs(Tp.max() - T.max())), max_tile_diff_K=float(np.abs(Tp.ravel() - T).max()))
pact["ok"] = bool(pact["diff_K"] <= 0.02)
out["c"] = dict(ok=bool(c_ok and scalar["ok"] and pact["ok"]), cases=cases, scalar_1x1=scalar, pact_full_solve=pact)
out["verdict"] = "PASS" if out["a"]["ok"] and out["b"]["ok"] and out["c"]["ok"] else "FAIL"
out["wall_s"] = time.time() - t_start
json.dump(out, open(os.path.join(RUN, "result.json"), "w"), indent=1, default=float)
manifest.write(os.path.join(RUN, "manifest.json"), {"gate": "G92"})
print(json.dumps({k: (v["ok"] if isinstance(v, dict) and "ok" in v else v) for k, v in out.items()}, default=float))
