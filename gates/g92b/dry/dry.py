import glob, json, collections
from opentsense.power import leaklib as L
res = {}
for kit, pat in (("ihp", "sg13g2*.lib"), ("asap7", "asap7*")):
    libs = sorted(glob.glob(f"gates/g92b/dry/lib/{pat}"))
    texts, cells, jobs = L.build(kit, libs)
    live = [(n, s) for n, c in cells.items() if "skip" not in c for s in c["states"]]
    unr = [(n, s["when"]) for n, s in live if all(p.get("unreachable") for p in s["parts"])]
    free = [(n, s["when"]) for n, s in live if any(p.get("free") for p in s["parts"])]
    seqn = sum(1 for n, s in live if cells[n]["seq"])
    print(kit, "cells", len(cells), "skipped", [n for n, c in cells.items() if "skip" in c], "states", len(live), "seq", seqn, "solves", len(jobs))
    print(" unreachable", len(unr)); [print("  ", u) for u in unr]
    print(" free", len(free), free[:10])
    res[kit] = dict(unreachable=unr, free=free, states=len(live), solves=len(jobs), seq=seqn)
    # write libs with dummy values to confirm the writer preserves group counts
    for c in cells.values():
        if "skip" not in c:
            for s in c["states"]: s["spice_pW"] = {T: 1.0 for T in L.TEMPS}
            c["solved"] = True; c["cell_leak_new"] = {T: 1.0 for T in L.TEMPS}
    for lib, txt in texts.items():
        out = L.write_lib(txt, {n: c for n, c in cells.items() if c["lib"] == lib.split("/")[-1]}, 25)
        assert out.count("leakage_power") == txt.count("leakage_power") and len(out.splitlines()) == len(txt.splitlines()), lib
g92 = json.load(open("gates/g92/runs/main/result.json"))["a"]["not_ok"]
u = set(map(tuple, res["ihp"]["unreachable"]))
print("G92 refusals classed unreachable:", [tuple(x) in u for x in g92])
json.dump(res, open("gates/g92b/dry/plan.json", "w"), indent=1)
