"""Data for the stages 1-3 demo (cells -> activity -> power), from G72 and G81b outputs.

Per program (19 Embench + idle) and per power window (20 each, 1,000 cycles):
  - per-instance total power, averaged over the program's windows (log10, quantised to uint8, base64);
  - per-window 16 x 16 tile map (uW), group totals (sequential / combinational / clock, mW) and window start cycle;
  - the 4 x 4 region toggle timeline (binned).
Plus OpenSTA's default activity (no VCD, G72 ibex_def) as a comparison "program".

Usage: python docs/stage_demo/extract.py <opentsense repo> <out.json>
"""
import base64
import json
import os
import re
import sys

import numpy as np

R, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, R)
from opentsense.power import maps  # noqa: E402

G = os.path.join(R, "gates")
LO, HI, TG = -13.0, -4.0, 16
NUM = re.compile(r"^\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+(\S+)\s*$")
GROUP = re.compile(r"^(Sequential|Combinational|Clock)\s+\S+\s+\S+\s+\S+\s+(\S+)", re.M)

box, pos = maps.read_locations(os.path.join(G, "g72/runs/main/power/ibex_loc.csv"))
names = sorted(pos)
index = {n: i for i, n in enumerate(names)}
xy = np.array([pos[n] for n in names])
ti = np.minimum(TG - 1, (xy[:, 1] - box[1]) / (box[3] - box[1]) * TG).astype(int)
tj = np.minimum(TG - 1, (xy[:, 0] - box[0]) / (box[2] - box[0]) * TG).astype(int)


def read(path):
    p = np.zeros(len(names))
    txt = open(path, errors="replace").read()
    for line in txt.splitlines():
        m = NUM.match(line)
        if m and m.group(5) in index:
            p[index[m.group(5)]] = float(m.group(4))
    groups = {g: float(v) * 1e3 for g, v in GROUP.findall(txt)}
    return p, groups


def tiles(p):
    M = np.zeros((TG, TG))
    np.add.at(M, (ti, tj), p)
    return np.round(M * 1e6, 3).tolist()                # uW, row = y from the lower edge


def q(p):
    l = np.log10(np.maximum(p, 10 ** LO))
    return base64.b64encode(np.round((np.clip(l, LO, HI) - LO) / (HI - LO) * 255).astype(np.uint8).tobytes()).decode()


res = json.load(open(os.path.join(G, "g81b/record/result.json")))["programs"]
progs = sorted(p for p in res if p != "idle_pass1" and os.path.isdir(os.path.join(G, f"g81b/runs/main/{p}/power")))
out = {"box": box, "x10": np.round(xy[:, 0] * 10).astype(int).tolist(), "y10": np.round(xy[:, 1] * 10).astype(int).tolist(),
       "logq": {"lo": LO, "hi": HI}, "tile_grid": TG, "programs": {}}
allp = []
for p in progs:
    wins = [int(l) for l in open(os.path.join(G, f"g81b/runs/main/windows/{p}.txt")).read().split()]
    files = sorted(f for f in os.listdir(os.path.join(G, f"g81b/runs/main/{p}/power")) if re.fullmatch(r"w\d+\.txt", f))
    acc, W = np.zeros(len(names)), []
    for k, f in enumerate(files):
        pw, grp = read(os.path.join(G, f"g81b/runs/main/{p}/power/{f}"))
        acc += pw
        W.append({"start": wins[k] if k < len(wins) else None, "total_mW": round(pw.sum() * 1e3, 4), "groups_mW": grp, "tiles_uW": tiles(pw)})
    mean = acc / max(1, len(files))
    allp.append(mean)
    X = np.loadtxt(os.path.join(G, f"g81b/runs/main/{p}/timeline.csv"), delimiter=",")
    idx = np.array_split(np.arange(len(X)), min(200, len(X)))
    out["programs"][p] = {"cells": q(mean), "windows": W, "cycles": int(res[p]["run"]["cycles"]),
                          "timeline": {"cycle": [int(X[i[-1], 0]) for i in idx], "regions": [np.round(X[i, 1:].mean(0)).astype(int).tolist() for i in idx]}}
    print(p, len(files), "windows", round(mean.sum() * 1e3, 3), "mW", flush=True)
suite = np.mean([a for p, a in zip(progs, allp) if p != "idle"], axis=0)
out["suite_mean"] = q(suite)
pd, gd = read(os.path.join(G, "g72/runs/main/power/ibex_def.txt"))
out["default"] = {"cells": q(pd), "total_mW": round(pd.sum() * 1e3, 4), "groups_mW": gd, "tiles_uW": tiles(pd)}
json.dump(out, open(OUT, "w"), separators=(",", ":"), allow_nan=False)
print(OUT, os.path.getsize(OUT) // 1024, "KB")
