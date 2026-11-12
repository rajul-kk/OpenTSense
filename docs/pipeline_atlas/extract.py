"""Pull compact per-stage data from OpenTSense gate outputs into one JSON for the pipeline visual page.
Usage: python docs/pipeline_atlas/extract.py . data.json, then build.py inlines it into page.src.html -> atlas.html"""
import glob
import json
import math
import os
import sys

import numpy as np
import yaml

R, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, R)
from opentsense.power import maps  # noqa: E402

G = os.path.join(R, "gates")
d = {}

# 1. Physical layout: every placed ibex cell with its power in kernel k0 (G72, ASAP7)
box, pos = maps.read_locations(os.path.join(G, "g72/runs/main/power/ibex_loc.csv"))
inst, tot = maps.read_power(os.path.join(G, "g72/runs/main/power/ibex_k0.txt"))
xs, ys, ps = [], [], []
for name, (x, y) in pos.items():
    if name in inst and inst[name][3] > 0:
        xs.append(round(x * 10)); ys.append(round(y * 10)); ps.append(round(math.log10(inst[name][3]) * 100))
d["layout"] = {"box": box, "x10": xs, "y10": ys, "log10P100": ps, "n": len(xs), "total_W": tot,
               "src": "gates/g72/runs/main/power/ibex_{loc.csv,k0.txt}"}

# 2. Activity: G81b toggle timelines, 4x4 regions, every program, binned to <=160 samples
act = {}
for f in sorted(glob.glob(os.path.join(G, "g81b/runs/main/*/timeline.csv"))):
    prog = os.path.basename(os.path.dirname(f))
    a = np.loadtxt(f, delimiter=",")
    if a.ndim != 2 or a.shape[1] != 17:
        continue
    t, r = a[:, 0], a[:, 1:]
    nb = min(160, len(t))
    idx = np.array_split(np.arange(len(t)), nb)
    rb = np.array([r[i].mean(0) for i in idx])
    act[prog] = {"cycles": [int(t[i[-1]]) for i in idx], "regions": np.round(rb).astype(int).tolist(),
                 "total_cycles": int(t[-1])}
d["activity"] = {"programs": act, "grid": [4, 4], "interval_cycles": 1000, "src": "gates/g81b/runs/main/*/timeline.csv"}
res81b = json.load(open(os.path.join(G, "g81b/record/result.json")))
d["activity"]["dyn_mW"] = {p: round(v["dyn_W"]["mean"] * 1e3, 4) for p, v in res81b["programs"].items() if "dyn_W" in v}

# 3. Power maps: G72 per-tile maps, mW
z = np.load(os.path.join(G, "g72/runs/main/maps.npz"))
d["maps"] = {k: np.round(z[k] * 1e3, 5).tolist() for k in z.files if not k.endswith("_um")}
d["maps_die_um"] = {k: z[k].tolist() for k in z.files if k.endswith("_um")}

# 4. Stack cross-sections
d["stacks"] = {}
for s in ("g71_3d", "g93a_3d_bottom", "g71_25d", "g93a_25d_regions"):
    y = yaml.safe_load(open(os.path.join(R, "configs/stacks", s + ".yaml")))
    d["stacks"][s] = {"size_um": y.get("size_um"), "heat_sink": y.get("heat_sink"), "layers": y.get("layers"),
                      "materials": y.get("materials"), "dies": y.get("dies")}

# 5. Temperature fields: G93a, seed 0, three solvers (already degrees C)
th = {}
for stack, keys in (("3d", ("top", "bot")), ("25d_regions", ("chiplets",))):
    f = np.load(os.path.join(G, f"g93a/runs/main/{stack}_fields.npz"))
    for k in keys:
        for s in ("ice", "pact", "hs"):
            th[f"{stack}/{k}/{s}"] = np.round(f[f"s0_{k}_{s}"], 3).tolist()
d["thermal"] = th

# 6. Electro-thermal loop: G92d (c) measured vs predicted amplification; G74 rho map
c = json.load(open(os.path.join(G, "g92d/record/asap7/result.json")))["c"]["cases"]
d["electro"] = {k: {kk: v.get(kk) for kk in ("rho", "amp_measured", "amp_predicted", "peak_shift_vs_fixed25_K", "leak_share", "iters")}
                for k, v in c.items()}
g74 = json.load(open(os.path.join(G, "g74/record/result.json")))
d["runaway"] = {k: {"group": v["group"], "measured": v["measured"], "rho": v.get("rho_tangent", v.get("rho_const")), "amp": v.get("amp_meas"), "peak_C": v.get("peak_C", v.get("peak_u_C"))} for k, v in g74["cases"].items()}

# 7. Estimation: G73 identifiability rows; G81d2 CPU/accelerator timelines
d["g73"] = json.load(open(os.path.join(G, "g73/record/result.json")))["rows"]
tl = np.load(os.path.join(G, "g81d2/runs/main/timelines.npz"))
d["offload"] = {k: [None if not np.isfinite(v) else round(float(v), 4) for v in tl[k]] for k in tl.files}  # NaN: window without a sample

json.dump(d, open(OUT, "w"), separators=(",", ":"), allow_nan=False)
print(OUT, os.path.getsize(OUT) // 1024, "KB;", d["layout"]["n"], "cells;", len(act), "programs")
