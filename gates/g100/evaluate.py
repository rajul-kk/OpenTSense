"""G100 bars (a)-(c) for one design, and the reported comparison with G72 (old layout at its old clock).
Usage: python gates/g100/evaluate.py <run dir> <ibex|tpu> <layout dir>
Writes <run dir>/result.json, maps.npz and manifest.json.
"""
import glob
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from opentsense import manifest  # noqa: E402
from opentsense.power import maps  # noqa: E402

WINDOWS = {"ibex": ["def", "k0", "k1", "k2", "k3", "k4"], "tpu": ["def", "W1", "W2", "W3"]}
BAR = {"annotation": 0.99, "tile_rel": 0.001, "tpu_rows": 616}
G72 = os.path.join(HERE, "..", "g72", "record", "result.json")


def checksums_ok(d, sim):
    if d == "ibex":
        return all(sim[f"ibex_k{k}"]["done"] == 1 and sim[f"ibex_k{k}"]["checksum"] == sim[f"ibex_k{k}"]["expected"]
                   for k in range(4))
    return all(sim[f"tpu_{k}"]["rows"] == BAR["tpu_rows"] == sim[f"tpu_{k}"]["rows_match"] for k in ("W1", "W2")) \
        and sim["tpu_W3"]["rows"] == 0


def main(run, d, layout):
    sim = json.load(open(os.path.join(run, "sim.json")))
    old = json.load(open(G72))[d]
    box, pos = maps.read_locations(os.path.join(run, "power", f"{d}_loc.csv"))
    area = (box[2] - box[0]) * (box[3] - box[1]) * 1e-6
    out, fields = {"design": d, "bar": BAR, "sim": sim, "die_um": box, "die_mm2": area, "g72_die_mm2": old["die_mm2"]}, {}
    for w in WINDOWS[d]:
        inst, total = maps.read_power(os.path.join(run, "power", f"{d}_{w}.txt"))
        M, missing = maps.tile_map(inst, box, pos, (32, 32))
        ann = maps.read_annotation(os.path.join(run, "power", f"{d}_{w}.txt"))
        out[w] = {"total_W": total, "density_W_mm2": total / area, "leak_share": sum(v[2] for n, v in inst.items() if n in pos) / total,
                  "n_inst": sum(n in pos for n in inst), "missing_loc": missing, "tile_rel": abs(M.sum() - total) / total,
                  "annotation": None if ann is None else ann[0] / (ann[0] + ann[1]),
                  "peak_over_mean": float(M.max() / M.mean()),
                  "g72_total_W": old[w]["total_W"], "power_vs_g72": total / old[w]["total_W"]}
        fields[w] = M
    wins = [out[w] for w in WINDOWS[d]]
    crit = {"a_checksums": checksums_ok(d, sim),
            "b_annotation": min(e["annotation"] or 0 for e in wins[1:]) >= BAR["annotation"],
            "c_tiles": bool(max(e["tile_rel"] for e in wins) <= BAR["tile_rel"])}
    out["summary"] = {"criteria": crit, "verdict": "PASS" if all(crit.values()) else "FAIL",
                      "min_annotation": min(e["annotation"] or 0 for e in wins[1:]), "max_tile_rel": max(e["tile_rel"] for e in wins),
                      "power_vs_g72": {w: out[w]["power_vs_g72"] for w in WINDOWS[d]}}
    np.savez_compressed(os.path.join(run, "maps.npz"), die_um=box, **fields)
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1, default=float)
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()  # noqa: E731
    inputs = {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(layout, "results", "asap7", d, "base", "6_final.*")))
              if p.endswith((".v", ".odb", ".sdc", ".spef"))}
    inputs.update({f"ibex_hex/{os.path.basename(p)}": sha(p) for p in sorted(glob.glob(os.path.join(HERE, "..", "g72", "inputs", "ibex_hex", "*.hex")))})
    inputs.update({f"tpu/{os.path.basename(p)}": sha(p) for p in sorted(glob.glob(os.path.join(run, "sim", "tpu", "stim_*.hex")))})
    inputs.update({f"stdcell/{os.path.basename(p)}": sha(p) for p in sorted(glob.glob(os.path.join(run, "stdcell", "*.v")))})
    manifest.write(os.path.join(run, "manifest.json"), {"gate": "G100", "design": d, "inputs_sha256": inputs})
    print(json.dumps(out["summary"], indent=1, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:4])
