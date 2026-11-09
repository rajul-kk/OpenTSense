"""G81c: real program power levels (G81b) in the guard-margin testbed (G44 plant, G66/G69 margins). registration.md.
Usage: g81c.py <out dir> [--dry]
  1. (v) runs experiments/code/sens/g69.py's whole chain unchanged (its own result file is not rewritten) and compares
     with g69_res.json; --dry stops here.
  2. Builds family F4 (G44's phase structure, tiles running G81b programs) and scores (a) and (b).
"""
import json
import os
import re
import sys
import time

import numpy as np

SENS = "D:/Work/FYP-search/experiments/code/sens"
A7 = "D:/Work/FYP-search/_build/asap7"
G81B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "g81b", "runs", "main")
S_CAL = ["aha-mont64", "depthconv", "huffbench", "md5sum", "nettle-sha256", "picojpeg", "sglib-combined", "statemate", "ud", "xgboost"]
S_TEST = ["crc32", "edn", "matmult-int", "nettle-aes", "nsichneu", "qrduino", "slre", "tarfind", "wikisort"]
OUT = os.path.abspath(sys.argv[1]); DRY = "--dry" in sys.argv; os.makedirs(OUT, exist_ok=True); t0 = time.time()
NUM = r"[-+0-9.eE]+"


def close(x, y, tol=1e-9):
    if isinstance(x, dict):
        return set(x) == set(y) and all(close(x[k], y[k], tol) for k in x)
    if x is None or y is None:
        return x is y
    return abs(float(x) - float(y)) <= tol


# ---------- 1. G69 chain, unchanged; only its json.dump line is dropped so g69_res.json is not rewritten
src = open(os.path.join(SENS, "g69.py")).read()
dump = [l for l in src.splitlines() if l.startswith("json.dump(")]
assert len(dump) == 1, "g69.py: expected one json.dump line"
ns = {"__file__": os.path.join(SENS, "g69.py"), "__name__": "g81c_chain"}
os.chdir(SENS)
exec(src.replace(dump[0], "pass"), ns)
ref = json.load(open(os.path.join(SENS, "g69_res.json")))
v_checks = dict(limits=close(ns["LIM"], ref["limits"]), oracle_cal=close(ns["orc"], ref["oracle_cal"]),
                a=close(ns["a"], ref["a"]), b=close(ns["b"], ref["b"]), verdicts=(ns["va"], ns["vb"]) == (ref["G69a"], ref["G69b"]))
v = all(v_checks.values())
print("(v) reproduces G69:", v, v_checks, f"{time.time() - t0:.0f}s", flush=True)
out = dict(v=v, v_checks=v_checks)
if DRY or not v:
    out["verdict"] = "DRY" if DRY else "INCONCLUSIVE"
    json.dump(out, open(os.path.join(OUT, "result.json"), "w"), indent=1, default=float)
    print("G81c:", out["verdict"]); sys.exit(0 if v else 1)

# ---------- 2. F4: tile maps from G81b program powers
def total(f):
    m = re.search(r"^Total\s+" + NUM + r"\s+" + NUM + r"\s+" + NUM + r"\s+(" + NUM + ")", open(f, errors="replace").read(), re.M)
    return float(m.group(1))


r81 = json.load(open(os.path.join(G81B, "result.json")))
P_kcrc, P_sleep = r81["programs"]["idle"]["idle"]["compute_total_W"], r81["programs"]["idle"]["idle"]["sleep_total_W"]
P = {p: float(np.mean([total(os.path.join(G81B, p, "power", f)) for f in sorted(os.listdir(os.path.join(G81B, p, "power")))]))
     for p in S_CAL + S_TEST}
M34 = np.load(os.path.join(A7, "g34_maps.npz"))
MAPS = {p: M34["TT_k1"] * P[p] / P_kcrc for p in P}
MAPS["sleep"] = M34["TT_k4"] * P_sleep / M34["TT_k4"].sum()
print("program tile power (mW):", {p: round(m.sum() * 1e3, 3) for p, m in MAPS.items()}, flush=True)
ns.update(MAPS81=MAPS)
exec('''
def phase_maps4(seed, progs):
    """phase_maps (g42.py) with each active tile running a G81b program instead of a G30 kernel"""
    r = np.random.default_rng(seed); dark = np.full((NG, NG), DARK * CELL * CELL)
    ph_c = r.choice(["busy", "cluster", "half", "sleep"]); ph_t = r.choice(["dense", "mixed", "partial", "idle"])
    on = np.zeros((13, 13), bool)
    if ph_c == "busy": on[:] = True
    elif ph_c == "cluster": h, w = r.integers(3, 10, 2); a, b = r.integers(0, 13 - h + 1), r.integers(0, 13 - w + 1); on[a:a + h, b:b + w] = True
    elif ph_c == "half": on = r.random((13, 13)) < 0.5
    cpu = {(i, j): (MAPS81[r.choice(progs)] if on[i, j] else MAPS81["sleep"]) for i in range(13) for j in range(13)}
    tp = np.full((10, 10), "W3", dtype=object)
    if ph_t == "dense": tp[:] = "W1"
    elif ph_t == "mixed": tp = np.where(r.random((10, 10)) < 0.5, "W1", "W2")
    elif ph_t == "partial": h, w = r.integers(2, 9, 2); a, b = r.integers(0, 10 - h + 1), r.integers(0, 10 - w + 1); tp[a:a + h, b:b + w] = "W1"
    tpu = {(i, j): CPUT[tp[i, j]] for i in range(10) for j in range(10)}
    blk = (slice(20, 40), slice(20, 40)); C = dark.copy(); C[blk] = 0; place(C, cpu, 13, 1000, 1000, 1000 / 13); T = dark.copy(); T[blk] = 0; place(T, tpu, 10, 1000, 1000, 100.0)
    return C, T
def seq4(q, progs):
    """seq (g44.py) with phase_maps4 and seeds 81000 + q"""
    rs = np.random.default_rng(81000 + q); P = np.zeros((NST, 202))
    for die in (0, 1):
        t = 0
        while t < NST:
            dn = max(2, int(round(np.exp(rs.uniform(np.log(1e-3), np.log(0.2))) / DT))); C, T = phase_maps4(int(rs.integers(10 ** 6, 2 * 10 ** 6)), progs)
            P[t:t + dn, die * 101:(die + 1) * 101] = bin101(T if die == 0 else C); t += dn
    return P
''', ns)
F4 = [ns["seq4"](q, S_CAL) for q in range(20)] + [ns["seq4"](q, S_TEST) for q in range(20, 40)]
FAM, at, simulate_P, margin, test = ns["FAM"], ns["at"], ns["simulate_P"], ns["margin"], ns["test"]
bs, Kg, Mg, calv, orc, up = ns["bs"], ns["Kg"], ns["Mg"], ns["calv"], ns["orc"], ns["up"]
FAM["F4"] = F4
ns["LIM"]["F4"] = float(np.quantile(up(F4[:20]), 0.7))
at("F4"); orc["F4"] = float(simulate_P(F4[:20], "O", [0.0], bs)[0][0])
for pol in ("R", "E"):
    calv[pol]["F4"] = simulate_P(F4[:20], pol, Mg, bs, Kg)[0]
print("F4 built and calibrated", f"{time.time() - t0:.0f}s", "limit", round(ns["LIM"]["F4"], 3), flush=True)
# (a) margins from F1+F2+F3 (G69(b)'s rule), tested on F4test
a = {pol: dict(margin=margin(pol, ("F1", "F2", "F3"))) for pol in ("R", "E")}
for pol in a:
    a[pol]["F4"] = test(pol, a[pol]["margin"], "F4") if a[pol]["margin"] is not None else None
# (b) margins from F4cal (S_cal programs), tested on F4test (S_test programs) and reported on F1-F3
b = {pol: dict(margin=margin(pol, ("F4",))) for pol in ("R", "E")}
for pol in b:
    if b[pol]["margin"] is not None:
        for f in ("F4", "F1", "F2", "F3"):
            b[pol][f] = test(pol, b[pol]["margin"], f)
        b[pol]["freq_cost_pct"] = round(0.064 * b[pol]["margin"], 3)
ok_a = a["E"]["F4"] is not None and a["E"]["F4"]["excess"] <= 0.005
ok_b = (b["E"]["margin"] is not None and b["R"]["margin"] is not None and b["E"]["F4"]["excess"] <= 0.005
        and b["E"]["F4"]["throughput"] >= b["R"]["F4"]["throughput"])
# reported: power spread and uncontrolled peaks, F4 against F1
kern = {k: float(ns["CPUK"][k].sum()) for k in ("matmul", "crc32", "sort", "idle", "sleep")}
pk1, pk4 = up(FAM["F1"][:20]), up(F4[:20])
out.update(a=a, b=b, a_pass=bool(ok_a), b_pass=bool(ok_b), limits=ns["LIM"], oracle_cal=orc,
           program_tile_W={p: float(m.sum()) for p, m in MAPS.items()}, kernel_tile_W=kern,
           uncontrolled_peak_quantiles=dict(F1=np.quantile(pk1, [0.1, 0.5, 0.9]).tolist(), F4=np.quantile(pk4, [0.1, 0.5, 0.9]).tolist()),
           sets=dict(cal=S_CAL, test=S_TEST), runtime_s=time.time() - t0)
out["verdict"] = "PASS" if ok_a and ok_b else "FAIL"
json.dump(out, open(os.path.join(OUT, "result.json"), "w"), indent=1, default=float)
print("(a)", json.dumps(a, default=float)); print("(b)", json.dumps(b, default=float))
print("G81c:", out["verdict"], dict(v=v, a=ok_a, b=ok_b))
