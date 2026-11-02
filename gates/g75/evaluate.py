"""G75 evaluation: default/real ratios, per-tile errors, library half of (2), stack shift, verdict.
Usage: evaluate.py <run dir> <g52 dir> <g53 dir> <g72 run> <g53_leak.json> <ihp typ lib>"""
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from opentsense import manifest  # noqa: E402
from opentsense.power import maps  # noqa: E402

RUN, G52, G53, G72, LEAK, LIB = sys.argv[1:7]
GRID = (32, 32)
BAND = {"cva6": (1.89, 2.42), "ihp": (1.558, 1.904)}


def tiles(real, deff):
    k = real.sum() / deff.sum()
    return dict(rel_l2=float(np.linalg.norm(deff - real) / np.linalg.norm(real)), pattern_rel_l2=float(np.linalg.norm(k * deff - real) / np.linalg.norm(real)),
                worst_tile_ratio=float((deff / np.where(real > 0, real, np.inf)).max()), median_tile_ratio=float(np.median((deff / np.where(real > 0, real, np.nan))[real > 0])))


def design(prefix, loc, wins):
    box, pos = maps.read_locations(loc)
    R = {}
    for w in ["def"] + wins:
        p = os.path.join(RUN, "power", f"{prefix}_{w}.txt")
        if not os.path.exists(p):
            continue
        inst, total = maps.read_power(p); m, miss = maps.tile_map(inst, box, pos, GRID); ann = maps.read_annotation(p)
        R[w] = dict(total=total, map=m, ann=None if ann is None else ann[0] / sum(ann), tile_rel=abs(m.sum() - total) / total, missing=miss, rc_ok=total is not None)
    return R


out = {}
ihp = design("ihp", os.path.join(G53, "ihp-sg13g2-ibex/inst_loc.csv"), [f"k{k}" for k in range(5)])
cva = design("cva6", os.path.join(G52, "asap7-cva6/inst_loc.csv"), [f"k{k}" for k in range(5)])
Z = np.load(os.path.join(G72, "maps.npz")); r72 = json.load(open(os.path.join(G72, "result.json")))

if all(f"k{k}" in ihp for k in range(4)) and "def" in ihp:
    v = ihp["def"]["total"] / np.mean([ihp[f"k{k}"]["total"] for k in range(4)])
    out["ihp"] = dict(ratio=float(v), band=BAND["ihp"], ok=bool(BAND["ihp"][0] <= v <= BAND["ihp"][1]), recorded=1.7314, annotation=min(ihp[f"k{k}"]["ann"] for k in range(5)),
                      max_tile_rel=max(e["tile_rel"] for e in ihp.values()), tiles={w: tiles(ihp[w]["map"], ihp["def"]["map"]) for w in ihp if w != "def"})
if all(f"k{k}" in cva for k in range(3)) and "def" in cva:
    v = {f"k{k}": cva["def"]["total"] / cva[f"k{k}"]["total"] for k in range(3)}
    out["cva6"] = dict(ratios=v, band=BAND["cva6"], ok=bool(all(BAND["cva6"][0] <= x <= BAND["cva6"][1] for x in v.values())), totals_W={w: e["total"] for w, e in cva.items()},
                       annotation=min(e["ann"] for w, e in cva.items() if e["ann"] is not None), max_tile_rel=max(e["tile_rel"] for e in cva.values()), corner="FF",
                       tiles={w: tiles(cva[w]["map"], cva["def"]["map"]) for w in cva if w != "def"})
else:
    out["cva6"] = dict(ok=None, note="COULD NOT RUN: windows missing", have=sorted(cva))
for d, wins in (("ibex", ["k0", "k1", "k2", "k3"]), ("tpu", ["W1", "W2"])):
    tot = {w: r72[d][w]["total_W"] for w in ["def"] + wins}
    out[f"asap7_{d}"] = dict(ratio_to_mean_real=float(tot["def"] / np.mean([tot[w] for w in wins])), corner="TT", tiles={w: tiles(Z[f"{d}_{w}"], Z[f"{d}_def"]) for w in wins})

leak = json.load(open(LEAK))["cases"]; txt = open(LIB).read(); lib = {}
for name, c in leak.items():
    cell = name.rsplit("_", 1)[0]; i = txt.index(f"cell (sg13g2_{cell})"); j = txt.index("\n  cell (", i + 10); blk = txt[i:j]
    val = [float(v) for v, _ in re.findall(r'value : ([-0-9.eE]+);\s*when : "([^"]+)"', blk)]
    lib[name] = dict(recorded_lib_pW=c["lib25_pW"], present_in_pinned_lib=any(abs(v - c["lib25_pW"]) < 1e-3 for v in val))
unchanged = all(v["present_in_pinned_lib"] for v in lib.values())
spath = os.path.join(RUN, "spice_ihp.json")
if os.path.exists(spath):
    sp = json.load(open(spath)); solved = all("failed" not in sp[n] for n in leak)
    r = {n: {t: lib[n]["recorded_lib_pW"] / sp[n][t] for t in ("25", "75", "100")} for n in leak} if solved else {}
    rng = [min(x["25"] for x in r.values()), max(x["25"] for x in r.values())] if solved else None
    ok = bool(solved and unchanged and abs(rng[0] / 0.893 - 1) <= 0.1 and abs(rng[1] / 4.233 - 1) <= 0.1)
    out["shortcut2"] = dict(status="RUN", ok=ok, library_values_unchanged=unchanged, range_25C=rng, recorded_range=[0.893, 4.233], lib25_over_spice=r,
                            max_rel_diff_from_G53=max(abs(sp[n][t] / leak[n]["spice_pW"][t] - 1) for n in leak for t in sp[n]) if solved else None)
else:
    out["shortcut2"] = dict(status="COULD NOT RUN", ok=None, library_values_unchanged=unchanged, recorded_range=[0.893, 4.233])
out["shortcut3"] = json.load(open(os.path.join(RUN, "stack.json"))) if os.path.exists(os.path.join(RUN, "stack.json")) else None

bars = [out["ihp"]["ok"] if "ihp" in out else None, out["cva6"]["ok"], out["shortcut2"]["ok"]]
out["verdict"] = "FAIL" if any(b is False for b in bars) else "PASS" if all(bars) else "INCONCLUSIVE"     # Amendment 2
json.dump(out, open(os.path.join(RUN, "result.json"), "w"), indent=1, default=float)
manifest.write(os.path.join(RUN, "manifest.json"), {"gate": "G75"})
print(json.dumps({k: v for k, v in out.items() if k in ("verdict", "shortcut2")} | {k: {a: b for a, b in out[k].items() if a in ("ratio", "ratios", "ok", "annotation", "max_tile_rel", "ratio_to_mean_real", "note")} for k in ("ihp", "cva6", "asap7_ibex", "asap7_tpu") if k in out}, indent=1, default=float))
