"""G81b: score whole-program power windows and activity timelines (registration.md, Amendment 1).
Usage: evaluate.py <run dir>
<run dir>/sw/build.log         (expected idle checksum)
<run dir>/windows/<prog>.txt   (window starts)
<run dir>/<prog>/run.log, timeline.csv, power/w###.txt
"""
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402
from opentsense.power import maps  # noqa: E402

RUN = sys.argv[1]
G72 = os.path.join(ROOT, "gates", "g72", "runs", "main")
box, pos = maps.read_locations(os.path.join(G72, "power", "ibex_loc.csv"))
NUM = r"[-+0-9.eE]+"
G30_SPREAD = 1.11
QUAD = [[(iy // 2) * 2 + ix // 2 for ix in range(4)] for iy in range(4)]   # region r = iy*4+ix -> 2 x 2 quadrant


def group_total(path):
    """(internal, switching, leakage, total) W of the design from OpenSTA's 'Total' group line."""
    m = re.search(r"^Total\s+(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM + ")", open(path, errors="replace").read(), re.M)
    return tuple(float(m.group(i)) for i in range(1, 5)) if m else None


def timeline(path):
    rows = {}
    for l in open(path):
        p = [int(v) for v in l.strip().split(",")]
        if p[0] > 0:                        # negative cycle: the final partial interval, never a window's row
            rows[p[0]] = np.array(p[1:], float)
    return rows


def result(log):
    m = re.search(r"RESULT result=(\w+) done=(\d+) done_cycle=(-?\d+) start=(-?\d+) stop=(-?\d+) cycles=(\d+)", open(log).read())
    return dict(result=m.group(1), done=int(m.group(2)), start=int(m.group(4)), stop=int(m.group(5)), cycles=int(m.group(6))) if m else None


progs = sorted(f[:-4] for f in os.listdir(os.path.join(RUN, "windows")) if f.endswith(".txt"))
idle_expected = re.search(r"idle npass=\d+ expected=(\w+)", open(os.path.join(RUN, "sw", "build.log")).read()).group(1)
out, ok_a, ok_b, ok_c = {"programs": {}}, True, True, True
for p in progs:
    D = os.path.join(RUN, p)
    starts = [int(v) for v in open(os.path.join(RUN, "windows", p + ".txt")).read().split()]
    r = result(os.path.join(D, "run.log"))
    a = bool(r) and r["done"] == 1 and (r["result"] == (idle_expected if p == "idle" else "00000000"))
    tl = timeline(os.path.join(D, "timeline.csv"))
    W = []
    for i, s in enumerate(starts):
        f = os.path.join(D, "power", f"w{i:03d}.txt")
        g = group_total(f) if os.path.exists(f) else None
        ann = maps.read_annotation(f) if g else None
        inst, _ = maps.read_power(f) if g else ({}, None)
        R = maps.tile_map(inst, box, pos, (4, 4))[0] if g else None
        W.append(dict(start=s, pw=g, frac=ann[0] / (ann[0] + ann[1]) if ann else None, tog=tl.get(s + 1000), regions=R,
                      in_loop=(r is not None and r["start"] <= s and s + 1000 <= r["stop"]) if p != "idle" else None))
    b = all(w["frac"] is not None and w["frac"] >= 0.99 for w in W)
    good = [w for w in W if w["pw"] is not None and w["tog"] is not None]
    pear, rms = None, None
    if len(good) == len(W) and len(W) >= 10:
        X = np.array([[1.0] + [sum(w["tog"][iy * 4 + ix] for iy in range(4) for ix in range(4) if QUAD[iy][ix] == q) for q in range(4)] for w in W])
        y = np.array([w["pw"][0] + w["pw"][1] for w in W])          # dynamic = internal + switching
        tr, te = np.arange(0, len(W), 2), np.arange(1, len(W), 2)
        coef = np.linalg.lstsq(X[tr], y[tr], rcond=None)[0]
        pred = X[te] @ coef
        if np.std(y[te]) > 0 and np.std(pred) > 0:
            pear = float(np.corrcoef(pred, y[te])[0, 1])
        rms = float(np.sqrt(np.mean((pred - y[te]) ** 2)) / np.mean(y[te]))
    c = pear is not None and pear >= 0.95
    ok_a &= a; ok_b &= b; ok_c &= c
    dyn = [w["pw"][0] + w["pw"][1] for w in good]
    reg = np.sum([w["regions"] for w in good], axis=0) if good else None
    o = dict(a=a, b=b, c=c, run=r, windows=len(W), windows_powered=len(good),
             windows_outside_loop=[w["start"] for w in W if w["in_loop"] is False],
             min_annotated=min((w["frac"] for w in W if w["frac"] is not None), default=None),
             pearson_test=pear, rel_rms_test=rms,
             dyn_W=dict(mean=float(np.mean(dyn)), min=float(min(dyn)), max=float(max(dyn))) if dyn else None,
             leak_share=float(np.mean([w["pw"][2] / w["pw"][3] for w in good])) if good else None,
             region_share=(reg / reg.sum()).round(4).tolist() if reg is not None else None)
    if p == "idle" and good:
        mk = [int(v) for v in re.findall(r"MARK phase=\d+ cycle=(\d+)", open(os.path.join(D, "run.log")).read())]
        def phase(s):   # phase index of a window lying wholly inside one phase, else None (boundary window)
            k = [i for i in range(len(mk) - 1) if mk[i] <= s and s + 1000 <= mk[i + 1]]
            return k[0] if k else None
        comp = [w for w in good if phase(w["start"]) is not None and phase(w["start"]) % 2 == 0]
        slp = [w for w in good if phase(w["start"]) is not None and phase(w["start"]) % 2 == 1]
        f = lambda ws, j: float(np.mean([w["pw"][j] for w in ws])) if ws else None  # noqa: E731
        o["idle"] = dict(compute_total_W=f(comp, 3), sleep_total_W=f(slp, 3),
                         sleep_over_compute=f(slp, 3) / f(comp, 3) if comp and slp else None,
                         sleep_leak_share=float(np.mean([w["pw"][2] / w["pw"][3] for w in slp])) if slp else None,
                         n_compute=len(comp), n_sleep=len(slp), n_boundary=len(good) - len(comp) - len(slp))
    out["programs"][p] = o
    print(p, json.dumps({k: o[k] for k in ("a", "b", "c", "pearson_test", "rel_rms_test", "min_annotated", "dyn_W", "windows_outside_loop")}, default=float), flush=True)
emb = {p: o for p, o in out["programs"].items() if p != "idle" and o["dyn_W"]}
means = [o["dyn_W"]["mean"] for o in emb.values()]
out["reported"] = dict(
    suite_spread_program_means=max(means) / min(means) if means else None,
    suite_spread_windows=max(o["dyn_W"]["max"] for o in emb.values()) / min(o["dyn_W"]["min"] for o in emb.values()) if emb else None,
    g30_spread=G30_SPREAD)
out["reported"]["prediction_wider_than_g30"] = bool(out["reported"]["suite_spread_program_means"] and out["reported"]["suite_spread_program_means"] > G30_SPREAD)
out.update(a=bool(ok_a), b=bool(ok_b), c=bool(ok_c), verdict="PASS" if ok_a and ok_b and ok_c else "FAIL")
json.dump(out, open(os.path.join(RUN, "result.json"), "w"), indent=1, default=float)
manifest.write(os.path.join(RUN, "manifest.json"), {"gate": "G81b"})
print("reported", json.dumps(out["reported"], default=float))
print("G81b:", out["verdict"], {x: out[x] for x in ("a", "b", "c")})
