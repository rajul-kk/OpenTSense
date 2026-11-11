"""G81a: score Verilator power windows against G72's Icarus windows (registration.md, Amendment 1).
Usage: evaluate.py <run dir> <G72 run dir>"""
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from opentsense import manifest  # noqa: E402
from opentsense.power import maps, workloads  # noqa: E402

RUN, G72 = sys.argv[1:3]
GRID = (32, 32)                                   # G72's grid
WINS = [0, 1, 2, 3, 4]
box, pos = maps.read_locations(os.path.join(G72, "power", "ibex_loc.csv"))
exp = workloads.ibex_expected()
g72sim = json.load(open(os.path.join(G72, "sim.json")))
out, ok_a, ok_b, ok_c = {"windows": {}}, True, True, True
for k in WINS:
    rv, ri = os.path.join(RUN, "power", f"ibex_k{k}.txt"), os.path.join(G72, "power", f"ibex_k{k}.txt")
    ann = maps.read_annotation(rv)
    frac = ann[0] / (ann[0] + ann[1]) if ann else None
    iv, tv = maps.read_power(rv)
    ii, ti = maps.read_power(ri)
    Mv, _ = maps.tile_map(iv, box, pos, GRID)
    Mi, _ = maps.tile_map(ii, box, pos, GRID)
    rel_total = tv / ti - 1 if (tv and ti) else None
    l2 = float(np.linalg.norm(Mv - Mi) / np.linalg.norm(Mi))
    common = set(iv) & set(ii)
    d = np.array([abs(iv[n][3] - ii[n][3]) for n in common])
    big = [n for n in common if ii[n][3] > 1e-7]
    rel = np.array([abs(iv[n][3] / ii[n][3] - 1) for n in big])
    got = workloads.ibex_result(os.path.join(RUN, "sim", f"k{k}_fun.log"))
    if k == 4:                                    # sleep: runs to its cycle limit, as G72
        func = bool(got) and got[3] >= 2600
    else:
        func = bool(got) and got[1] == 1 and got[0] == exp.get(k)
    a = frac is not None and frac >= 0.99
    b = rel_total is not None and abs(rel_total) <= 0.01 and l2 <= 0.01
    ok_a &= a; ok_b &= b; ok_c &= func
    t = json.load(open(os.path.join(RUN, "sim", f"k{k}_timing.json")))
    icarus_s = g72sim.get(f"ibex_k{k}", {}).get("wall_s")
    out["windows"][f"k{k}"] = dict(
        dry_run_window=(k == 0), annotated=ann, annotated_frac=frac, a=bool(a),
        total_W=tv, g72_total_W=ti, rel_total=rel_total, tile_rel_l2=l2, b=bool(b),
        checksum=got and got[0], done=got and got[1], cycles=got and got[3], expected=exp.get(k), c=bool(func),
        inst_common=len(common), inst_max_abs_diff_W=float(d.max()) if len(d) else None,
        inst_rel_diff_median=float(np.median(rel)) if len(rel) else None, inst_rel_diff_p99=float(np.percentile(rel, 99)) if len(rel) else None,
        verilator_function_s=t["function_s"], icarus_s=icarus_s,
        speedup_function_run=(icarus_s / t["function_s"]) if icarus_s and t["function_s"] else None)
    print(f"k{k}", json.dumps({x: out["windows"][f"k{k}"][x] for x in ("annotated_frac", "rel_total", "tile_rel_l2", "checksum", "c", "speedup_function_run")}), flush=True)
out.update(a=bool(ok_a), b=bool(ok_b), c=bool(ok_c))
out["verdict"] = "PASS" if ok_a and ok_b and ok_c else "FAIL"
unseen = [out["windows"][f"k{k}"] for k in (1, 2, 3, 4)]
out["k1_k4_only"] = dict(max_abs_rel_total=max(abs(w["rel_total"]) for w in unseen), max_tile_rel_l2=max(w["tile_rel_l2"] for w in unseen))
json.dump(out, open(os.path.join(RUN, "result.json"), "w"), indent=1, default=float)
manifest.write(os.path.join(RUN, "manifest.json"), {"gate": "G81a"})
print("G81a:", out["verdict"], {x: out[x] for x in ("a", "b", "c")})
