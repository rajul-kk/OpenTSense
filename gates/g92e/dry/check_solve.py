"""G92e dry check (not scored): the refactored solve() on chosen plans, against G92d's stored part values.
With TAIL=0 (G92d's last point) every value must equal G92d's; prints outcome and settle_status.
env: TAIL, TEMPS, STAGES, FLAT, FLOOR_A, J. Usage: check_solve.py <kit> <g92d kit dir> <cell> [when-substring;...]"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from opentsense.power import leaklib as L

kit, R, cell = sys.argv[1:4]
whens = sys.argv[4].split(";") if len(sys.argv) > 4 else None
for k in ("TAIL", "FLAT", "FLOOR_A"):
    if k in os.environ: setattr(L, k, float(os.environ[k]))
if "TEMPS" in os.environ: L.TEMPS = tuple(int(x) for x in os.environ["TEMPS"].split(","))
if "STAGES" in os.environ: L.STAGES = tuple(float(x) for x in os.environ["STAGES"].split(","))
J = json.load(open(f"{R}/lib/leak_states.json"))
_, cells, jobs = L.build(kit, J["libs"])
pick = [j for j in jobs if j[0] == cell and (whens is None or any(w in (cells[cell]["states"][j[1][0]]["when"] or "") for w in whens))]
print("TAIL", L.TAIL, "TEMPS", L.TEMPS, "STAGES", L.STAGES, flush=True)
worst = 0.0
with ThreadPoolExecutor(int(os.environ.get("J", "2"))) as ex:
    for c, key, r in ex.map(L.solve, pick):
        k, j, i = key
        st0 = J["cells"][c]["states"][k]
        pt0 = next(p for p in st0["parts"] if p["minterm"] == j and p["sub"] == i)
        rel = {t: r["spice_pW"][t] / pt0["spice_pW"][str(t)] - 1 for t in r["spice_pW"] if pt0.get("spice_pW", {}).get(str(t))}
        worst = max([worst] + [abs(x) for x in rel.values()])
        print(c, st0["when"], key, r["outcome"], r.get("settle_status"), "rel to G92d", {t: f"{x:+.2e}" for t, x in rel.items()},
              "tail" if "tail" in r else "", (r.get("tail") or "")[:120], flush=True)
print("max |rel| to G92d", f"{worst:.3e}", flush=True)
