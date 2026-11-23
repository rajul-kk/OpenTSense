"""Each solver against itself from floor.py's units: per stack, die and solver, the change of the peak rise and of the
spread from the gated mesh (x1) to the refined one (x2), relative to x1. No number that compares two solvers is
printed or written. With <image_units_dir>: the parity check of a Kaggle build against the image (A18), the same x1
unit in the same solver, largest relative difference of peak and spread over the dies; it needs all three S2 units
on both sides, equal `inputs` hashes, and at most PARITY_REL.
Units that are missing are listed, so a floor taken over fewer stacks is visible.

Usage (repo root): python gates/g93/dry/floor_summary.py <units_dir> <out.json> [<image_units_dir>]
"""
import glob
import json
import os
import sys

STACKS, SOLVERS = ("s1", "s2", "s4"), ("ice", "hs", "pact")
PARITY_REL = 1e-3
METRICS = ("peak_rise_K", "spread_K")
PARITY_UNITS = [("s2", 1, s) for s in SOLVERS]


def rel(a, b):
    """|a - b| / |b|; inf when b is 0 and a is not (a zero reference cannot set a relative floor)."""
    return abs(a - b) / abs(b) if b else (0.0 if a == b else float("inf"))


def load(d):
    return {(r["stack"], r["factor"], r["solver"]): r
            for r in (json.load(open(p)) for p in sorted(glob.glob(os.path.join(d, "*_x*_*.json"))))}


def parity(u, v):
    """{unit: (largest relative peak difference, same inputs)} for units in both."""
    out = {}
    for k, r in u.items():
        if k in v:
            w = v[k]["dies"]
            out[f"{k[0]}_x{k[1]}_{k[2]}"] = {
                "rel": max(rel(r["dies"][d][m], w[d][m]) for d in w for m in METRICS),
                "same_inputs": r["inputs"] == v[k]["inputs"]}
    return out


def main(units, out, image=None):
    u = load(units)
    floor = {}
    for name in STACKS:
        for solver in SOLVERS:
            c, f = u.get((name, 1, solver)), u.get((name, 2, solver))
            if c and f:
                for die, a in c["dies"].items():
                    floor.setdefault(name, {}).setdefault(die, {})[solver] = {
                        m: rel(f["dies"][die][m], a[m]) for m in METRICS}
    res = {"floor_rel": floor,
           "missing": [f"{n}_x{x}_{s}" for n in STACKS for x in (1, 2) for s in SOLVERS if (n, x, s) not in u],
           "wall_s": {f"{n}_x{x}_{s}": r["wall_s"] for (n, x, s), r in sorted(u.items())}}
    if image:
        v = load(image)
        p = parity(u, v)
        res["parity"] = p
        res["parity_ok"] = (all(k in u and k in v for k in PARITY_UNITS)
                            and all(x["same_inputs"] and x["rel"] <= PARITY_REL for x in p.values()))
    with open(out + ".tmp", "w") as fh:
        json.dump(res, fh, indent=1)
    os.replace(out + ".tmp", out)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
