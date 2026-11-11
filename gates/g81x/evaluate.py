"""G81x: score Verilator (hold testbench) against Icarus (hold testbench); control Icarus (original) against G72.
Usage: evaluate.py <run dir> <G72 run dir>   (registration.md)"""
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
G81A = os.path.join(ROOT, "gates", "g81a", "runs", "main")
GRID = (32, 32)
box, pos = maps.read_locations(os.path.join(G72, "power", "ibex_loc.csv"))
exp = workloads.ibex_expected()


def load(path):
    inst, tot = maps.read_power(path)
    M, _ = maps.tile_map(inst, box, pos, GRID)
    ann = maps.read_annotation(path)
    return dict(inst=inst, tot=tot, M=M, frac=ann[0] / (ann[0] + ann[1]) if ann else None)


def cmp(a, b):
    """a against reference b."""
    common = [n for n in set(a["inst"]) & set(b["inst"]) if b["inst"][n][3] > 1e-7]
    rel = np.array([abs(a["inst"][n][3] / b["inst"][n][3] - 1) for n in common])
    return dict(rel_total=a["tot"] / b["tot"] - 1, tile_rel_l2=float(np.linalg.norm(a["M"] - b["M"]) / np.linalg.norm(b["M"])),
                inst_rel_median=float(np.median(rel)), inst_rel_p99=float(np.percentile(rel, 99)))


def x_changes(vcd):
    """Value changes that set any bit to x/z, after the header."""
    n, body = 0, False
    with open(vcd, "rb") as f:
        for line in f:
            if not body:
                body = line.lstrip().startswith(b"$enddefinitions")
                continue
            c = line[:1]
            if c in b"xXzZ" and c:
                n += 1
            elif c in b"bB" and re.search(rb"[xXzZ]", line.split(b" ")[0]):
                n += 1
    return n


out, ok_v, ok_a, ok_b, ok_c = {"windows": {}}, True, True, True, True
for k in range(5):
    P = lambda v: load(os.path.join(RUN, "power", f"{v}_k{k}.txt"))  # noqa: E731
    vl, ivh, ivx = P("vl"), P("ivh"), P("ivx")
    g72 = load(os.path.join(G72, "power", f"ibex_k{k}.txt"))
    g81a = load(os.path.join(G81A, "power", f"ibex_k{k}.txt"))
    v = abs(ivx["tot"] / g72["tot"] - 1) <= 1e-6
    a = all(x["frac"] is not None and x["frac"] >= 0.99 for x in (vl, ivh))
    b_ = cmp(vl, ivh)
    b = abs(b_["rel_total"]) <= 0.01 and b_["tile_rel_l2"] <= 0.01
    got = workloads.ibex_result(os.path.join(RUN, "sim", "vl", f"k{k}_fun.log"))
    c = (bool(got) and got[3] >= 2600) if k == 4 else (bool(got) and got[1] == 1 and got[0] == exp.get(k))
    ok_v &= v; ok_a &= a; ok_b &= b; ok_c &= c
    xc = cmp(ivh, g72)                                  # X component of G72's reference (hold vs original)
    gap_tot, gap_l2 = g81a["tot"] - g72["tot"], np.linalg.norm(g81a["M"] - g72["M"])
    w = dict(
        v_control=dict(ivx_vs_g72_rel_total=ivx["tot"] / g72["tot"] - 1, ok=bool(v)),
        a=bool(a), annotated_frac=dict(vl=vl["frac"], ivh=ivh["frac"]),
        b=bool(b), vl_vs_ivh=b_,
        c=bool(c), checksum=got and got[0], done=got and got[1], cycles=got and got[3], expected=exp.get(k),
        totals_W=dict(vl_hold=vl["tot"], icarus_hold=ivh["tot"], icarus_orig=ivx["tot"], g72=g72["tot"], g81a_vl=g81a["tot"]),
        x_component_ivh_vs_g72=xc,
        gap_closed=dict(total=(ivh["tot"] - g72["tot"]) / gap_tot if gap_tot else None,
                        tile_l2=1 - float(np.linalg.norm(g81a["M"] - ivh["M"]) / gap_l2) if gap_l2 else None),
        vl_hold_vs_g81a=cmp(vl, g81a),
        g72_x_value_changes=x_changes(os.path.join(G72, "sim", "ibex", f"k{k}.vcd")),
        ivh_x_value_changes=x_changes(os.path.join(RUN, "sim", "ivh", f"k{k}.vcd")))
    out["windows"][f"k{k}"] = w
    print(f"k{k}", json.dumps(dict(v=v, a=a, b=b, c=c, vl_vs_ivh=b_, x_component=xc, gap_closed=w["gap_closed"],
                                   x_changes=(w["g72_x_value_changes"], w["ivh_x_value_changes"])), default=float), flush=True)
out.update(v=bool(ok_v), a=bool(ok_a), b=bool(ok_b), c=bool(ok_c))
out["verdict"] = "INCONCLUSIVE" if not ok_v else ("PASS" if ok_a and ok_b and ok_c else "FAIL")
json.dump(out, open(os.path.join(RUN, "result.json"), "w"), indent=1, default=float)
manifest.write(os.path.join(RUN, "manifest.json"), {"gate": "G81x"})
print("G81x:", out["verdict"], {x: out[x] for x in ("v", "a", "b", "c")})
