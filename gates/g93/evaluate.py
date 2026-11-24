"""G93 verdict from run.py's units (registration.md): for every stack, die (S3: region) and solver pair,
(a) |peak_a - peak_b| and (b) |spread_a - spread_b| within dry/bars.json's bar of the pair's mean, and (c) the RMS of
the difference of the two rise maps over the die's powered silicon within RMS_BAR of the pair's mean rise there.
S3 is compared in 3D-ICE and PACT only (registration Amendment 1, GATED).

A unit counts as missing when its JSON is absent, it ran out of time, its inputs differ from this code's, its regions
differ, or its maps are unreadable (load). A pair is INCONCLUSIVE when a unit is missing, when its two units come
from different builds (`image`), or when neither loop settled; one solver settling and the other not (ran away, or
still moving after run.MAX_IT solves) is a FAIL of that pair. Verdict: FAIL if any pair fails, else INCONCLUSIVE if
any is inconclusive, else PASS. With --dry: which units are present, nothing else.

Usage (repo root): python gates/g93/evaluate.py <runs_dir> <result.json> [--dry]
"""
import itertools
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "dry"), os.path.join(HERE, "sens")]
from common import stacks  # noqa: E402
import run as g93run  # noqa: E402
from opentsense import manifest  # noqa: E402
from opentsense.manifest import write_json  # noqa: E402

SOLVERS = ("ice", "hs", "pact")
# Amendment 1 (registration.md): S3 is compared in 3D-ICE and PACT only
GATED = {"s1": SOLVERS, "s2": SOLVERS, "s4": SOLVERS, "s3": ("ice", "pact")}
STACKS = tuple(GATED)
RMS_BAR = 0.02
METRICS = ("peak_rise_K", "spread_K")


def regions(name):
    """{label: (die, rows, cols)} as common.summary labels them: a die, or a die's powered rectangle in S3."""
    st, P = stacks.build(name, g93run.CELL_UM)
    out = {}
    for l in st.dies:
        rects = stacks.powered(st, l, P)
        for rect in rects:
            j0, j1, i0, i1 = st.cells(rect)
            out[l.name if len(rects) == 1 else f"{l.name}@{rect[0]:.0f},{rect[1]:.0f}"] = (l.name, slice(i0, i1),
                                                                                           slice(j0, j1))
    return out, st.ambient_K


BURIED = {"s1": "ccd", "s2": "base", "s4": "mid"}      # reported apart (registration), gated like every die


def load(runs, name, solver, code, labels, dry):
    """(record, {die: map} or None, note). The record is None (the unit counts as missing) when the JSON is missing,
    the unit ran out of time, its inputs differ from this code's (the regions below are rebuilt from it), its regions
    differ, or a settled unit's maps are missing or unreadable. With dry, the maps are not opened."""
    p = os.path.join(runs, f"{name}_{solver}.json")
    if not os.path.exists(p):
        return None, None, "missing"
    r = json.load(open(p))
    if r.get("settled") is None:
        return None, None, r.get("why", "not finished")
    if r["inputs"] != code:
        return None, None, f"inputs {r['inputs']} differ from this code's {code}"
    if r["settled"] and set(r["dies"]) != labels:
        return None, None, f"regions {sorted(r['dies'])} differ from {sorted(labels)}"
    if dry or not r["settled"]:
        return r, None, r.get("why", "")
    try:
        with np.load(p[:-5] + ".npz") as z:
            return r, {d: z[d] for d in z.files}, ""
    except (OSError, ValueError, EOFError) as e:
        return None, None, f"maps unreadable ({e})"


def pair(ra, rb, ma, mb, bar, reg, amb):
    """One pair on every region of a stack: the metrics, the bars they meet and the pair's status."""
    if not (ra and rb):
        return {"status": "INCONCLUSIVE", "why": "missing unit"}
    if ra["image"] != rb["image"]:
        return {"status": "INCONCLUSIVE", "why": f"different builds ({ra['image']}, {rb['image']})"}
    if not (ra["settled"] or rb["settled"]):
        return {"status": "INCONCLUSIVE", "why": "neither settled"}
    if ra["settled"] != rb["settled"]:
        return {"status": "FAIL", "why": "one settled, the other did not"}
    out, ok = {}, True
    for label, (die, rows, cols) in reg.items():
        a, b = ra["dies"][label], rb["dies"][label]
        m = {}
        for k in METRICS:
            mean = (a[k] + b[k]) / 2
            m[k] = {"diff_rel": abs(a[k] - b[k]) / mean, "bar_rel": bar(label)[k]}
        ta, tb = ma[die][rows, cols] - amb, mb[die][rows, cols] - amb
        m["rms"] = {"diff_rel": float(np.sqrt(((ta - tb) ** 2).mean()) / ((ta + tb) / 2).mean()), "bar_rel": RMS_BAR}
        m["pass"] = all(v["diff_rel"] <= v["bar_rel"] for v in m.values())
        ok &= m["pass"]
        out[label] = m
    return {"status": "PASS" if ok else "FAIL", "regions": out}


def reported(r, note):
    """What the registration reports per unit, not gated."""
    if r is None:
        return {"present": False, "note": note}
    keep = ("settled", "iterations", "power_ratio", "wall_s", "image")
    return {"present": True, "note": note, **{k: r.get(k) for k in keep},
            "max_gradient_K_per_mm": {d: v["max_gradient_K_per_mm"] for d, v in r.get("dies", {}).items()}}


def main(runs, out, flag=None):
    if flag not in (None, "--dry"):
        sys.exit(f"unknown option {flag}")
    dry = flag == "--dry"
    bars = json.load(open(os.path.join(HERE, "dry", "bars.json")))["bars_rel"]
    code = g93run.inputs()
    res, units = {}, {}
    for name in STACKS:
        reg, amb = regions(name)
        u = {s: load(runs, name, s, code, set(reg), dry) for s in GATED[name]}
        units[name] = {s: {"present": r is not None} if dry else reported(r, note) for s, (r, _, note) in u.items()}
        if dry:
            continue
        for a, b in itertools.combinations(GATED[name], 2):
            def bar(label, p=f"{a}-{b}"):
                per = bars[name]["*" if name == "s3" else label]
                return {k: per[k][p] for k in METRICS}
            res[f"{name}:{a}-{b}"] = pair(u[a][0], u[b][0], u[a][1], u[b][1], bar, reg, amb)
    if dry:
        verdict, buried = "DRY (presence only, no verdict)", {}
    else:
        st = [p["status"] for p in res.values()]
        verdict = "FAIL" if "FAIL" in st else "INCONCLUSIVE" if "INCONCLUSIVE" in st else "PASS"
        buried = {f"{k}:{die}": (v["regions"][die] if "regions" in v else v["status"])
                  for k, v in res.items() for s, die in BURIED.items() if k.startswith(s + ":")}
    write_json({"verdict": verdict, "inputs": code, "units": units, "buried": buried, "pairs": res}, out)
    manifest.write(os.path.join(os.path.dirname(os.path.abspath(out)), "manifest.json"),
                   {"gate": "G93", "inputs": code, "units_dir": runs})
    print(verdict)


if __name__ == "__main__":
    main(*sys.argv[1:])
