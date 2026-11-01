"""G72 step 4 (opentsense image): checksums, annotation, density and tile conservation -> result.json, maps.npz, manifest.json.
Usage: python gates/g72/evaluate.py <run dir> <build dir>
Also compares each window with the exploratory G34/G36 outputs in <build dir> when they are there (recorded, not a bar).
"""
import glob
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from opentsense import manifest  # noqa: E402
from opentsense.power import maps  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = (32, 32)
WINDOWS = {"ibex": ["def", "k0", "k1", "k2", "k3", "k4"], "tpu": ["def", "W1", "W2", "W3"]}
BAR = {"annotation": 0.99, "density_rel": 0.03, "tile_rel": 0.001, "ibex_density": 1.27, "tpu_density": 8.9, "tpu_rows": 616}
OLD = {"ibex": "pw_{w}_TT.txt", "tpu": "tpw_{w}_TT.txt"}  # exploratory reports (G34, G36)
OLD_TAG = {"def": "def", "W1": "W1", "W2": "W2", "W3": "W3", **{f"k{k}": f"k{k}" for k in range(5)}}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main(run, build):
    sim = json.load(open(os.path.join(run, "sim.json")))
    out, fields = {"bar": BAR, "sim": sim}, {}
    for d, wins in WINDOWS.items():
        box, pos = maps.read_locations(os.path.join(run, "power", f"{d}_loc.csv"))
        area = (box[2] - box[0]) * (box[3] - box[1]) * 1e-6
        old_maps = np.load(os.path.join(build, "g34_maps.npz")) if d == "ibex" and os.path.exists(os.path.join(build, "g34_maps.npz")) else None
        r = {"die_um": box, "die_mm2": area}
        for w in wins:
            rep = os.path.join(run, "power", f"{d}_{w}.txt")
            if not os.path.exists(rep):  # shortened plumbing runs
                continue
            inst, total = maps.read_power(rep)
            M, missing = maps.tile_map(inst, box, pos, GRID)
            ann = maps.read_annotation(rep)
            leak = sum(v[2] for v in inst.values())
            e = {"total_W": total, "density_W_mm2": total / area, "leak_share": leak / total, "n_inst": len(inst),
                 "missing_loc": missing, "tile_sum_W": float(M.sum()), "tile_rel": abs(M.sum() - total) / total,
                 "annotation": None if ann is None else ann[0] / (ann[0] + ann[1]), "pins": ann,
                 "peak_over_mean": float(M.max() / M.mean())}
            p = os.path.join(build, OLD[d].format(w=OLD_TAG[w]))
            if os.path.exists(p):
                old_inst, old_total = maps.read_power(p)
                e["exploratory_total_W"] = old_total
                common = set(old_inst) & set(inst)
                e["exploratory_inst_max_abs_W"] = max(abs(old_inst[n][3] - inst[n][3]) for n in common) if common else None
                e["exploratory_inst_common"] = [len(common), len(old_inst), len(inst)]
            if old_maps is not None and f"TT_{w}" in old_maps:
                e["exploratory_map_max_abs_W"] = float(np.abs(old_maps[f"TT_{w}"] - M).max())
            r[w] = e
            fields[f"{d}_{w}"] = M
        out[d] = r
    ib, tp = out["ibex"], out["tpu"]
    if not all(w in out[d] for d, wins in WINDOWS.items() for w in wins):
        json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1, default=float)
        print("incomplete run: no verdict"); return
    exp_ok = all(sim[f"ibex_k{k}"]["checksum"] == sim[f"ibex_k{k}"]["expected"] and sim[f"ibex_k{k}"]["done"] == 1 for k in range(4))
    tpu_ok = all(sim[f"tpu_{k}"]["rows"] == BAR["tpu_rows"] == sim[f"tpu_{k}"]["rows_match"] for k in ("W1", "W2")) \
        and sim["tpu_W3"]["rows"] == 0
    anns = [e["annotation"] for d in ("ibex", "tpu") for w, e in out[d].items() if isinstance(e, dict) and w != "def" and "annotation" in e]
    ib_dens = float(np.mean([ib[f"k{k}"]["density_W_mm2"] for k in range(3)]))
    tp_dens = tp["W1"]["density_W_mm2"]
    tiles = [e["tile_rel"] for d in ("ibex", "tpu") for w, e in out[d].items() if isinstance(e, dict) and "tile_rel" in e]
    crit = {
        "a_checksums": exp_ok and tpu_ok,
        "b_annotation": min(anns) >= BAR["annotation"],
        "c_density": abs(ib_dens / BAR["ibex_density"] - 1) <= BAR["density_rel"] and abs(tp_dens / BAR["tpu_density"] - 1) <= BAR["density_rel"],
        "d_tiles": max(tiles) <= BAR["tile_rel"],
    }
    out["summary"] = {"ibex_compute_density": ib_dens, "ibex_density_rel": ib_dens / BAR["ibex_density"] - 1,
                      "tpu_W1_density": tp_dens, "tpu_density_rel": tp_dens / BAR["tpu_density"] - 1,
                      "min_annotation": min(anns), "max_tile_rel": max(tiles), "criteria": crit,
                      "verdict": "PASS" if all(crit.values()) else "FAIL"}
    np.savez_compressed(os.path.join(run, "maps.npz"), ibex_die_um=ib["die_um"], tpu_die_um=tp["die_um"], **fields)
    json.dump(out, open(os.path.join(run, "result.json"), "w"), indent=1, default=float)
    inputs = {os.path.relpath(p, build).replace("\\", "/"): sha(p) for d in ("ibex", "tpu") for p in
              sorted(glob.glob(os.path.join(build, f"asap7-{d}", "results", "asap7", d, "base", "6_final.*")))
              if p.endswith((".v", ".odb", ".sdc", ".spef"))}
    inputs.update({f"ibex_hex/{os.path.basename(p)}": sha(p) for p in sorted(glob.glob(os.path.join(HERE, "inputs", "ibex_hex", "*.hex")))})
    inputs.update({f"tpu/{os.path.basename(p)}": sha(p) for p in sorted(glob.glob(os.path.join(run, "sim", "tpu", "stim_*.hex")))})
    inputs.update({f"stdcell/{os.path.basename(p)}": sha(p) for p in sorted(glob.glob(os.path.join(run, "stdcell", "*.v")))})
    manifest.write(os.path.join(run, "manifest.json"), {"gate": "G72", "inputs_sha256": inputs})
    print(json.dumps(out["summary"], indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
