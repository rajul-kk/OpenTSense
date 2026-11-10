"""G92c post-run check (not scored): do the 25 °C settling misses close with a longer continuation?
Re-solves chosen cells at 25 °C only, with the continuation lengthened from 10 ms to CONT_S seconds (max step CONT_S/100).
Usage: probe_cont.py <kit> <cells,comma> <CONT_S>"""
import sys, glob, time, os
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "gates/g92c")
import leaklib_g92c as L          # G92c's generator, frozen; opentsense/power/leaklib.py has moved on to G92d
kit, want, T = sys.argv[1], sys.argv[2].split(","), float(sys.argv[3])
L.CONT = (T, T / 100)
L.TEMPS = [25]
libs = sorted(glob.glob(f"gates/g92b/runs/main/{kit}/lib/ship/*"))
_, cells, jobs = L.build(kit, libs)
pick = [j for j in jobs if j[0] in want and L.is_capture(j[6]["info"], j[3])]
t0 = time.time()
with ThreadPoolExecutor(int(os.environ.get("J", "2"))) as ex:
    for cell, key, r in ex.map(L.solve, pick):
        st = cells[cell]["states"][key[0]]
        a = r.get("settle_agree", {}).get(25)
        print(cell, st["when"], "ok" if r["ok"] else "FAIL", "tran", round(r["tran_pW"].get(25, float("nan")), 2),
              "cont", round(r["cont_pW"].get(25, float("nan")), 2), "dc", round(r["spice_pW"].get(25, float("nan")), 2),
              "agree", None if a is None else round(a, 5), "v", r.get("v"), flush=True)
print("wall", round(time.time() - t0, 1), "s,", len(pick), "plans, CONT", L.CONT)
