"""G96 bars (a)-(c) and the measured glitch share for one design (registration.md).
Usage: python gates/g96/evaluate.py <run dir> <work dir> <ibex|tpu>
Dynamic power is OpenSTA internal + switching, summed over placed (leaf) instances. "delay" is OpenSTA on the view of
the delay-aware VCD (delay_netlist.sta_view, Amendment 1); "delay_raw", on the simulator's own VCD, is reported only.
"""
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from opentsense import manifest  # noqa: E402
from opentsense.power import maps  # noqa: E402

BAR = {"annotation": 0.99, "decision_share": 0.05, "tile_min_frac": 0.001}


def toggles(vcd):
    """Value changes after the header (scalar and vector)."""
    n, body = 0, False
    with open(vcd) as fh:
        for line in fh:
            if body:
                n += line[:1] in "01xzbB"
            elif line.startswith("$enddefinitions"):
                body = True
    return n


def main(run, work, d):
    sim = json.load(open(os.path.join(run, "sim.json")))
    conv = open(os.path.join(run, "convert.log")).read()
    m = re.search(r"SDF instances not in the netlist (\d+).*outputs not parsed (\d+)", conv)
    cut = re.search(r"outputs cut (\d+)", conv)
    view = re.search(r"output pins re-pointed (\d+)", open(os.path.join(run, "view.log")).read())
    box, pos = maps.read_locations(os.path.join(run, "power", "loc.csv"))
    out, M = {"design": d, "bar": BAR, "sim": sim, "converter": conv.strip()}, {}
    for v in ("zero", "delay", "delay_raw"):
        rep = os.path.join(run, "power", f"{v}.txt")
        inst, total = maps.read_power(rep)
        dyn = {n: (p[0] + p[1],) for n, p in inst.items()}
        M[v], _ = maps.tile_map(dyn, box, pos, (32, 32), col=0)
        ann = maps.read_annotation(rep)
        out[v] = {"total_W": total, "dynamic_W": float(M[v].sum()), "toggles": toggles(os.path.join(work, f"{v.replace('_raw', '')}.vcd")) if v != "delay" else None,
                  "annotation": None if ann is None else ann[0] / (ann[0] + ann[1])}
    share = 1 - out["zero"]["dynamic_W"] / out["delay"]["dynamic_W"]
    big = M["delay"] >= BAR["tile_min_frac"] * M["delay"].sum()
    tile_share = np.where(big, 1 - M["zero"] / np.where(big, M["delay"], 1), np.nan)
    crit = {"a_reference": sim["zero"]["ok"] and sim["delay"]["ok"],
            "b_converter": bool(m and cut and view) and m.group(1) == "0" and m.group(2) == "0"
                           and view.group(1) == cut.group(1),     # every delayed output re-pointed for OpenSTA
            "c_annotation": min(out[v]["annotation"] or 0 for v in ("zero", "delay")) >= BAR["annotation"]}
    out["summary"] = {"criteria": crit, "valid": all(crit.values()), "glitch_share": share,
                      "below_decision_threshold": share < BAR["decision_share"],
                      "raw_glitch_share": 1 - out["zero"]["dynamic_W"] / out["delay_raw"]["dynamic_W"],
                      "toggle_ratio_sim": out["delay_raw"]["toggles"] / out["zero"]["toggles"],
                      "tile_share_median": float(np.nanmedian(tile_share)), "tile_share_max": float(np.nanmax(tile_share)),
                      "tiles_counted": int(big.sum())}
    np.savez_compressed(os.path.join(run, "maps.npz"), die_um=box, zero=M["zero"], delay=M["delay"], tile_share=tile_share)
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1, default=float)
    manifest.write(os.path.join(run, "manifest.json"), {"gate": "G96", "design": d})
    print(json.dumps(out["summary"], indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
