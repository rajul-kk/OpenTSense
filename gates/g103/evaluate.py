"""Score G103 from runs/<name>/<kit>/<corner>/ against registration.md.

Usage (repo root): python gates/g103/evaluate.py <run dir>
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense.power.leak import CORNERS as ALL_CORNERS  # noqa: E402
from opentsense.power.leaklib import literals  # noqa: E402

KITS, WINS = ("ihp", "asap7", "asap7_lvt"), [f"k{k}" for k in range(4)]
CORNERS = tuple(c for c in ALL_CORNERS if c != "tt")          # TT is G95's record
CHECK_T = ("25", "50", "75", "100")
IHP_CELLS = {"inv_1": ("sg13g2_inv_1", ["A"]), "nand2_1": ("sg13g2_nand2_1", ["A", "B"]),
             "nor2_1": ("sg13g2_nor2_1", ["A", "B"])}


def state(S, cell, want):
    hits = [s for s in S[cell]["states"] if s["when"] and all(literals(s["when"]).get(p) == v for p, v in want.items())]
    if len(hits) != 1:
        raise ValueError(f"{cell} {want}: {len(hits)} matching states")
    return hits[0]["spice_pW"]


def cross_check(kit, S, ref):
    """{case: {T: library / leak.py - 1}} for the registered cases (G92e's pairing)."""
    out = {}
    if kit == "ihp":
        for key, v in ref.items():
            base, st = key.rsplit("_", 1)
            if base not in IHP_CELLS:
                continue                                      # dfrbp_1: not rerun at corners
            cell, pins = IHP_CELLS[base]
            bits = st[1:] if st.startswith("A") else st
            g = state(S, cell, {p: int(b) for p, b in zip(pins, bits)})
            out[key] = None if "failed" in v else {t: g[t] / v[t] - 1 for t in CHECK_T}
    else:
        vt = "L" if kit == "asap7_lvt" else "R"
        for cell, pins in (("INVx1", ["A"]), ("NAND2x1", ["A", "B"])):
            v = ref[f"{cell}_{vt}"]
            a = state(S, f"{cell}_ASAP7_75t_{vt}", {p: 0 for p in pins})
            b = state(S, f"{cell}_ASAP7_75t_{vt}", {p: 1 for p in pins})
            out[cell] = None if "failed" in v else {t: (a[t] + b[t]) / 2 / (v[t] * 1e12) - 1 for t in CHECK_T}
    return out


def corner(kit, d):
    LS = json.load(open(os.path.join(d, "lib", "leak_states.json")))
    S = LS["cells"]
    solved = all(s.get("ok") and len(s["spice_pW"]) == 5 for c in S.values() if "skip" not in c for s in c["states"])
    xc = cross_check(kit, S, json.load(open(os.path.join(d, "leak_ref.json"))))
    sta = all(re.search(r"^Total\s", open(os.path.join(d, "power", f"{w}_{t}.txt")).read(), re.M)
              for w in WINS for t in (25, 50, 75, 100, 125))
    M = json.load(open(os.path.join(d, "margin.json")))
    v = {"v1_library": solved and not LS.get("kept_shipped"),
         "v2_cross_check": all(x is not None and all(abs(e) <= 0.01 for e in x.values()) for x in xc.values()),
         "v3_power_and_loop": sta and all(M["windows"][w]["real_status"] == "converged" for w in WINS)}
    return {"valid": v, "cross_check": xc, "kept_shipped": LS.get("kept_shipped", []),
            "margin": {w: M["windows"][w]["margin"] for w in WINS},
            "leak_at_358K_W": {w: M["windows"][w]["leak_at_ambient_W"] for w in WINS}}


def scored(kit, d):
    """corner(), or an invalid entry naming the missing or broken output (that kit is then INCONCLUSIVE)."""
    try:
        return corner(kit, d)
    except (OSError, KeyError, ValueError) as e:
        return {"valid": {"outputs": False}, "error": f"{type(e).__name__}: {e}"}


def control(run, kit, tt):
    """v4: margin.py on G92e's TT run reproduces G95's margins (same operator and bisection: to round-off)."""
    try:
        m = json.load(open(os.path.join(run, kit, "tt_control", "margin.json")))["windows"]
        return {w: m[w]["margin"] / tt[w] - 1 for w in WINS}
    except (OSError, KeyError) as e:
        return {"error": f"{type(e).__name__}: {e}"}


def main(run):
    g95 = json.load(open(os.path.join(ROOT, "gates", "g95", "record", "result.json")))["kits"]
    out = {"kits": {}}
    for kit in KITS:
        tt = {w: 1 / g95[kit][w]["f_nominal"] for w in WINS}
        ctl = control(run, kit, tt)
        r = {c: scored(kit, os.path.join(run, kit, c)) for c in CORNERS if os.path.isdir(os.path.join(run, kit, c))}
        ctl_ok = "error" not in ctl and all(abs(x) <= 1e-6 for x in ctl.values())
        valid = ctl_ok and set(r) == set(CORNERS) and all(all(x["valid"].values()) for x in r.values())
        order = valid and all(r["ff"]["margin"][w] < tt[w] < r["ss"]["margin"][w] for w in WINS)
        out["kits"][kit] = {"valid": valid, "a": order if valid else None, "tt_margin": tt, "tt_control": ctl,
                            "corners": r, "ratio_to_tt": {c: {w: x["margin"][w] / tt[w] for w in WINS}
                                                          for c, x in r.items() if "margin" in x}}
    kits = out["kits"].values()
    out["verdict"] = ("FAIL" if any(k["valid"] and not k["a"] for k in kits) else
                      "PASS" if all(k["valid"] for k in kits) else "INCONCLUSIVE")
    out["inconclusive_kits"] = [k for k, x in out["kits"].items() if not x["valid"]]
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1)
    print(out["verdict"], {k: (x["valid"], x["a"]) for k, x in out["kits"].items()})


if __name__ == "__main__":
    main(sys.argv[1])
